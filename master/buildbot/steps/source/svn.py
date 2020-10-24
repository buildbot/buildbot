# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

import re
import xml.dom.minidom
import xml.parsers.expat
from urllib.parse import quote as urlquote
from urllib.parse import unquote as urlunquote
from urllib.parse import urlparse
from urllib.parse import urlunparse

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log

from buildbot.config import ConfigErrors
from buildbot.interfaces import WorkerSetupError
from buildbot.process import buildstep
from buildbot.process import remotecommand
from buildbot.steps.source.base import Source


class SVN(Source):

    """I perform Subversion checkout/update operations."""

    name = 'svn'

    renderables = ['repourl', 'password']
    possible_methods = ('clean', 'fresh', 'clobber', 'copy', 'export', None)

    def __init__(self, repourl=None, mode='incremental',
                 method=None, username=None,
                 password=None, extra_args=None, keep_on_purge=None,
                 depth=None, preferLastChangedRev=False, **kwargs):

        self.repourl = repourl
        self.username = username
        self.password = password
        self.extra_args = extra_args
        self.keep_on_purge = keep_on_purge or []
        self.depth = depth
        self.method = method
        self.mode = mode
        self.preferLastChangedRev = preferLastChangedRev
        super().__init__(**kwargs)
        errors = []
        if not self._hasAttrGroupMember('mode', self.mode):
            errors.append("mode {} is not one of {}".format(self.mode,
                                                            self._listAttrGroupMembers('mode')))
        if self.method not in self.possible_methods:
            errors.append("method {} is not one of {}".format(self.method, self.possible_methods))

        if repourl is None:
            errors.append("you must provide repourl")

        if errors:
            raise ConfigErrors(errors)

    @defer.inlineCallbacks
    def run_vc(self, branch, revision, patch):
        self.revision = revision
        self.method = self._getMethod()
        self.stdio_log = yield self.addLogForRemoteCommands("stdio")

        # if the version is new enough, and the password is set, then obfuscate
        # it
        if self.password is not None:
            if not self.workerVersionIsOlderThan('shell', '2.16'):
                self.password = ('obfuscated', self.password, 'XXXXXX')
            else:
                log.msg("Worker does not understand obfuscation; "
                        "svn password will be logged")

        installed = yield self.checkSvn()
        if not installed:
            raise WorkerSetupError("SVN is not installed on worker")

        patched = yield self.sourcedirIsPatched()
        if patched:
            yield self.purge(False)

        yield self._getAttrGroupMember('mode', self.mode)()

        if patch:
            yield self.patch(patch)
        res = yield self.parseGotRevision()
        return res

    @defer.inlineCallbacks
    def mode_full(self):
        if self.method == 'clobber':
            yield self.clobber()
            return
        elif self.method in ['copy', 'export']:
            yield self.copy()
            return

        updatable = yield self._sourcedirIsUpdatable()
        if not updatable:
            # blow away the old (un-updatable) directory and checkout
            yield self.clobber()
        elif self.method == 'clean':
            yield self.clean()
        elif self.method == 'fresh':
            yield self.fresh()

    @defer.inlineCallbacks
    def mode_incremental(self):
        updatable = yield self._sourcedirIsUpdatable()

        if not updatable:
            # blow away the old (un-updatable) directory and checkout
            yield self.clobber()
        else:
            # otherwise, do an update
            command = ['update']
            if self.revision:
                command.extend(['--revision', str(self.revision)])
            yield self._dovccmd(command)

    @defer.inlineCallbacks
    def clobber(self):
        yield self.runRmdir(self.workdir, timeout=self.timeout)
        yield self._checkout()

    @defer.inlineCallbacks
    def fresh(self):
        yield self.purge(True)
        cmd = ['update']
        if self.revision:
            cmd.extend(['--revision', str(self.revision)])
        yield self._dovccmd(cmd)

    @defer.inlineCallbacks
    def clean(self):
        yield self.purge(False)
        cmd = ['update']
        if self.revision:
            cmd.extend(['--revision', str(self.revision)])
        yield self._dovccmd(cmd)

    @defer.inlineCallbacks
    def copy(self):
        yield self.runRmdir(self.workdir, timeout=self.timeout)

        checkout_dir = 'source'
        if self.codebase:
            checkout_dir = self.build.path_module.join(
                checkout_dir, self.codebase)
        # temporarily set workdir = checkout_dir and do an incremental checkout
        try:
            old_workdir = self.workdir
            self.workdir = checkout_dir
            yield self.mode_incremental()
        finally:
            self.workdir = old_workdir
        self.workdir = old_workdir

        # if we're copying, copy; otherwise, export from source to build
        if self.method == 'copy':
            cmd = remotecommand.RemoteCommand('cpdir',
                                              {'fromdir': checkout_dir, 'todir': self.workdir,
                                               'logEnviron': self.logEnviron})
        else:
            export_cmd = ['svn', 'export']
            if self.revision:
                export_cmd.extend(["--revision", str(self.revision)])
            if self.username:
                export_cmd.extend(['--username', self.username])
            if self.password is not None:
                export_cmd.extend(['--password', self.password])
            if self.extra_args:
                export_cmd.extend(self.extra_args)
            export_cmd.extend([checkout_dir, self.workdir])

            cmd = remotecommand.RemoteShellCommand('', export_cmd,
                                                   env=self.env, logEnviron=self.logEnviron,
                                                   timeout=self.timeout)
        cmd.useLog(self.stdio_log, False)

        yield self.runCommand(cmd)

        if cmd.didFail():
            raise buildstep.BuildStepFailed()

    @defer.inlineCallbacks
    def _dovccmd(self, command, collectStdout=False, collectStderr=False, abandonOnFailure=True):
        assert command, "No command specified"
        command.extend(['--non-interactive', '--no-auth-cache'])
        if self.username:
            command.extend(['--username', self.username])
        if self.password is not None:
            command.extend(['--password', self.password])
        if self.depth:
            command.extend(['--depth', self.depth])
        if self.extra_args:
            command.extend(self.extra_args)

        cmd = remotecommand.RemoteShellCommand(self.workdir, ['svn'] + command,
                                               env=self.env,
                                               logEnviron=self.logEnviron,
                                               timeout=self.timeout,
                                               collectStdout=collectStdout,
                                               collectStderr=collectStderr)
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)

        if cmd.didFail() and abandonOnFailure:
            log.msg("Source step failed while running command {}".format(cmd))
            raise buildstep.BuildStepFailed()
        if collectStdout and collectStderr:
            return (cmd.stdout, cmd.stderr)
        elif collectStdout:
            return cmd.stdout
        elif collectStderr:
            return cmd.stderr
        return cmd.rc

    def _getMethod(self):
        if self.method is not None and self.mode != 'incremental':
            return self.method
        elif self.mode == 'incremental':
            return None
        elif self.method is None and self.mode == 'full':
            return 'fresh'
        return None

    @defer.inlineCallbacks
    def _sourcedirIsUpdatable(self):
        # first, perform a stat to ensure that this is really an svn directory
        res = yield self.pathExists(self.build.path_module.join(self.workdir, '.svn'))
        if not res:
            return False

        # then run 'svn info --xml' to check that the URL matches our repourl
        stdout, stderr = yield self._dovccmd(['info', '--xml'], collectStdout=True,
                                             collectStderr=True, abandonOnFailure=False)

        # svn: E155037: Previous operation has not finished; run 'cleanup' if
        # it was interrupted
        if 'E155037:' in stderr:
            return False

        try:
            stdout_xml = xml.dom.minidom.parseString(stdout)
            extractedurl = stdout_xml.getElementsByTagName(
                'url')[0].firstChild.nodeValue
        except xml.parsers.expat.ExpatError as e:
            yield self.stdio_log.addHeader("Corrupted xml, aborting step")
            raise buildstep.BuildStepFailed() from e
        return extractedurl == self.svnUriCanonicalize(self.repourl)

    @defer.inlineCallbacks
    def parseGotRevision(self):
        # if this was a full/export, then we need to check svnversion in the
        # *source* directory, not the build directory
        svnversion_dir = self.workdir
        if self.mode == 'full' and self.method == 'export':
            svnversion_dir = 'source'
        cmd = remotecommand.RemoteShellCommand(svnversion_dir, ['svn', 'info', '--xml'],
                                               env=self.env,
                                               logEnviron=self.logEnviron,
                                               timeout=self.timeout,
                                               collectStdout=True)
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)

        stdout = cmd.stdout
        try:
            stdout_xml = xml.dom.minidom.parseString(stdout)
        except xml.parsers.expat.ExpatError as e:
            yield self.stdio_log.addHeader("Corrupted xml, aborting step")
            raise buildstep.BuildStepFailed() from e

        revision = None
        if self.preferLastChangedRev:
            try:
                revision = stdout_xml.getElementsByTagName(
                    'commit')[0].attributes['revision'].value
            except (KeyError, IndexError):
                msg = ("SVN.parseGotRevision unable to detect Last Changed Rev in"
                       " output of svn info")
                log.msg(msg)
                # fall through and try to get 'Revision' instead

        if revision is None:
            try:
                revision = stdout_xml.getElementsByTagName(
                    'entry')[0].attributes['revision'].value
            except (KeyError, IndexError) as e:
                msg = ("SVN.parseGotRevision unable to detect revision in"
                       " output of svn info")
                log.msg(msg)
                raise buildstep.BuildStepFailed() from e

        yield self.stdio_log.addHeader("Got SVN revision {}".format(revision))
        self.updateSourceProperty('got_revision', revision)

        return cmd.rc

    @defer.inlineCallbacks
    def purge(self, ignore_ignores):
        """Delete everything that shown up on status."""
        command = ['status', '--xml']
        if ignore_ignores:
            command.append('--no-ignore')
        stdout = yield self._dovccmd(command, collectStdout=True)

        files = []
        for filename in self.getUnversionedFiles(stdout, self.keep_on_purge):
            filename = self.build.path_module.join(self.workdir, filename)
            files.append(filename)
        if files:
            if self.workerVersionIsOlderThan('rmdir', '2.14'):
                rc = yield self.removeFiles(files)
            else:
                rc = yield self.runRmdir(files, abandonOnFailure=False, timeout=self.timeout)
            if rc != 0:
                log.msg("Failed removing files")
                raise buildstep.BuildStepFailed()

    @staticmethod
    def getUnversionedFiles(xmlStr, keep_on_purge):
        try:
            result_xml = xml.dom.minidom.parseString(xmlStr)
        except xml.parsers.expat.ExpatError as e:
            log.err("Corrupted xml, aborting step")
            raise buildstep.BuildStepFailed() from e

        for entry in result_xml.getElementsByTagName('entry'):
            (wc_status,) = entry.getElementsByTagName('wc-status')
            if wc_status.getAttribute('item') == 'external':
                continue
            if wc_status.getAttribute('item') == 'missing':
                continue
            filename = entry.getAttribute('path')
            if filename in keep_on_purge or filename == '':
                continue
            yield filename

    @defer.inlineCallbacks
    def removeFiles(self, files):
        for filename in files:
            res = yield self.runRmdir(filename, abandonOnFailure=False, timeout=self.timeout)
            if res:
                return res
        return 0

    @defer.inlineCallbacks
    def checkSvn(self):
        cmd = remotecommand.RemoteShellCommand(self.workdir, ['svn', '--version'],
                                               env=self.env,
                                               logEnviron=self.logEnviron,
                                               timeout=self.timeout)
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)
        return cmd.rc == 0

    def computeSourceRevision(self, changes):
        if not changes or None in [c.revision for c in changes]:
            return None
        lastChange = max([int(c.revision) for c in changes])
        return lastChange

    @staticmethod
    def svnUriCanonicalize(uri):
        collapse = re.compile(r'([^/]+/\.\./?|/\./|//|/\.$|/\.\.$|^/\.\.)')
        server_authority = re.compile(r'^(?:([^@]+)@)?([^:]+)(?::(.+))?$')
        default_port = {'http': '80',
                        'https': '443',
                        'svn': '3690'}

        relative_schemes = ['http', 'https', 'svn']

        def quote(uri):
            return urlquote(uri, "!$&'()*+,-./:=@_~", encoding="latin-1")

        if not uri or uri == '/':
            return uri

        (scheme, authority, path, parameters, query, fragment) = urlparse(uri)
        scheme = scheme.lower()
        if authority:
            mo = server_authority.match(authority)
            if not mo:
                return uri  # give up
            userinfo, host, port = mo.groups()
            if host[-1] == '.':
                host = host[:-1]
            authority = host.lower()
            if userinfo:
                authority = "{}@{}".format(userinfo, authority)
            if port and port != default_port.get(scheme, None):
                authority = "{}:{}".format(authority, port)

        if scheme in relative_schemes:
            last_path = path
            while True:
                path = collapse.sub('/', path, 1)
                if last_path == path:
                    break
                last_path = path

        path = quote(urlunquote(path))
        canonical_uri = urlunparse(
            (scheme, authority, path, parameters, query, fragment))
        if canonical_uri == '/':
            return canonical_uri
        elif canonical_uri[-1] == '/' and canonical_uri[-2] != '/':
            return canonical_uri[:-1]
        return canonical_uri

    @defer.inlineCallbacks
    def _checkout(self):
        checkout_cmd = ['checkout', self.repourl, '.']
        if self.revision:
            checkout_cmd.extend(["--revision", str(self.revision)])
        if self.retry:
            abandonOnFailure = (self.retry[1] <= 0)
        else:
            abandonOnFailure = True
        res = yield self._dovccmd(checkout_cmd, abandonOnFailure=abandonOnFailure)

        if self.retry:
            if self.stopped or res == 0:
                return
            delay, repeats = self.retry
            if repeats > 0:
                log.msg("Checkout failed, trying %d more times after %d seconds"
                        % (repeats, delay))
                self.retry = (delay, repeats - 1)
                df = defer.Deferred()
                df.addCallback(lambda _: self.runRmdir(self.workdir, timeout=self.timeout))
                df.addCallback(lambda _: self._checkout())
                reactor.callLater(delay, df.callback, None)
                yield df
