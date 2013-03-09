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

import xml.dom.minidom
import xml.parsers.expat

from twisted.python import log
from twisted.internet import defer

from buildbot.process import buildstep
from buildbot.steps.source.base import Source
from buildbot.interfaces import BuildSlaveTooOldError
from buildbot.config import ConfigErrors

class SVN(Source):
    """I perform Subversion checkout/update operations."""

    name = 'svn'

    renderables = [ 'repourl' ]
    possible_modes = ('incremental', 'full')
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
        Source.__init__(self, **kwargs)
        errors = []
        if self.mode not in self.possible_modes:
            errors.append("mode %s is not one of %s" % (self.mode, self.possible_modes))
        if self.method not in self.possible_methods:
            errors.append("method %s is not one of %s" % (self.method, self.possible_methods))

        if repourl is None:
            errors.append("you must provide repourl")

        if errors:
            raise ConfigErrors(errors)

    def startVC(self, branch, revision, patch):
        self.revision = revision
        self.method = self._getMethod()
        self.stdio_log = self.addLogForRemoteCommands("stdio")

        d = self.checkSvn()
        def checkInstall(svnInstalled):
            if not svnInstalled:
                raise BuildSlaveTooOldError("SVN is not installed on slave")
            return 0
        d.addCallback(checkInstall)

        if self.mode == 'full':
            d.addCallback(self.full)
        elif self.mode == 'incremental':
            d.addCallback(self.incremental)
        d.addCallback(self.parseGotRevision)
        d.addCallback(self.finish)
        d.addErrback(self.failed)
        return d

    @defer.inlineCallbacks
    def full(self, _):
        if self.method == 'clobber':
            yield self.clobber()
            return
        elif self.method in ['copy', 'export']:
            yield self.copy()
            return

        updatable = yield self._sourcedirIsUpdatable()
        if not updatable:
            # blow away the old (un-updatable) directory
            yield self.runRmdir(self.workdir)

            # then do a checkout
            checkout_cmd = ['checkout', self.repourl, '.']
            if self.revision:
                checkout_cmd.extend(["--revision", str(self.revision)])
            yield self._dovccmd(checkout_cmd)
        elif self.method == 'clean':
            yield self.clean()
        elif self.method == 'fresh':
            yield self.fresh()

    @defer.inlineCallbacks
    def incremental(self, _):
        updatable = yield self._sourcedirIsUpdatable()

        if not updatable:
            # blow away the old (un-updatable) directory
            yield self.runRmdir(self.workdir)

            # and plan to do a checkout
            command = ['checkout', self.repourl, '.']
        else:
            # otherwise, do an update
            command = ['update']

        if self.revision:
            command.extend(['--revision', str(self.revision)])

        yield self._dovccmd(command)

    @defer.inlineCallbacks
    def clobber(self):
        yield self.runRmdir(self.workdir)

        checkout_cmd = ['checkout', self.repourl, '.']
        if self.revision:
            checkout_cmd.extend(["--revision", str(self.revision)])

        yield self._dovccmd(checkout_cmd)

    def fresh(self):
        d = self.purge(True)
        cmd = ['update']
        if self.revision:
            cmd.extend(['--revision', str(self.revision)])
        d.addCallback(lambda _: self._dovccmd(cmd))
        return d

    def clean(self):
        d = self.purge(False)
        cmd = ['update']
        if self.revision:
            cmd.extend(['--revision', str(self.revision)])
        d.addCallback(lambda _: self._dovccmd(cmd))
        return d

    @defer.inlineCallbacks
    def copy(self):
        yield self.runRmdir(self.workdir)

        # temporarily set workdir = 'source' and do an incremental checkout
        try:
            old_workdir = self.workdir
            self.workdir = 'source'
            yield self.incremental(None)
        except: # finally doesn't work in python-2.4
            self.workdir = old_workdir
            raise
        self.workdir = old_workdir

        # if we're copying, copy; otherwise, export from source to build
        if self.method == 'copy':
            cmd = buildstep.RemoteCommand('cpdir',
                    { 'fromdir': 'source', 'todir':self.workdir,
                      'logEnviron': self.logEnviron })
        else:
            export_cmd = ['svn', 'export']
            if self.revision:
                export_cmd.extend(["--revision", str(self.revision)])
            export_cmd.extend(['source', self.workdir])

            cmd = buildstep.RemoteShellCommand('', export_cmd,
                    env=self.env, logEnviron=self.logEnviron, timeout=self.timeout)
        cmd.useLog(self.stdio_log, False)

        yield self.runCommand(cmd)

        if cmd.didFail():
            raise buildstep.BuildStepFailed()

    def finish(self, res):
        d = defer.succeed(res)
        def _gotResults(results):
            self.setStatus(self.cmd, results)
            return results
        d.addCallback(_gotResults)
        d.addCallbacks(self.finished, self.checkDisconnect)
        return d


    def _dovccmd(self, command, collectStdout=False):
        assert command, "No command specified"
        command.extend(['--non-interactive', '--no-auth-cache'])
        if self.username:
            command.extend(['--username', self.username])
        if self.password:
            command.extend(['--password', self.password])
        if self.depth:
            command.extend(['--depth', self.depth])
        if self.extra_args:
            command.extend(self.extra_args)

        cmd = buildstep.RemoteShellCommand(self.workdir, ['svn'] + command,
                                           env=self.env,
                                           logEnviron=self.logEnviron,
                                           timeout=self.timeout,
                                           collectStdout=collectStdout)
        cmd.useLog(self.stdio_log, False)
        log.msg("Starting SVN command : svn %s" % (" ".join(command), ))
        d = self.runCommand(cmd)
        def evaluateCommand(cmd):
            if cmd.didFail():
                log.msg("Source step failed while running command %s" % cmd)
                raise buildstep.BuildStepFailed()
            if collectStdout:
                return cmd.stdout
            else:
                return cmd.rc
        d.addCallback(lambda _: evaluateCommand(cmd))
        return d

    def _getMethod(self):
        if self.method is not None and self.mode != 'incremental':
            return self.method
        elif self.mode == 'incremental':
            return None
        elif self.method is None and self.mode == 'full':
            return 'fresh'

    @defer.inlineCallbacks
    def _sourcedirIsUpdatable(self):
        # first, perform a stat to ensure that this is really an svn directory
        res = yield self.pathExists(self.build.path_module.join(self.workdir, '.svn'))
        if not res:
            defer.returnValue(False)
            return

        # then run 'svn info --xml' to check that the URL matches our repourl
        stdout = yield self._dovccmd(['info', '--xml'], collectStdout=True)

        try:
            stdout_xml = xml.dom.minidom.parseString(stdout)
            extractedurl = stdout_xml.getElementsByTagName('url')[0].firstChild.nodeValue
        except xml.parsers.expat.ExpatError:
            msg = "Corrupted xml, aborting step"
            self.stdio_log.addHeader(msg)
            raise buildstep.BuildStepFailed()
        defer.returnValue(extractedurl == self.repourl)
        return

    @defer.inlineCallbacks
    def parseGotRevision(self, _):
        # if this was a full/export, then we need to check svnversion in the
        # *source* directory, not the build directory
        svnversion_dir = self.workdir
        if self.mode == 'full' and self.method == 'export':
            svnversion_dir = 'source'
        cmd = buildstep.RemoteShellCommand(svnversion_dir, ['svn', 'info', '--xml'],
                                           env=self.env,
                                           logEnviron=self.logEnviron,
                                           timeout=self.timeout,
                                           collectStdout=True)
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)

        stdout = cmd.stdout
        try:
            stdout_xml = xml.dom.minidom.parseString(stdout)
        except xml.parsers.expat.ExpatError:
            msg = "Corrupted xml, aborting step"
            self.stdio_log.addHeader(msg)
            raise buildstep.BuildStepFailed()

        revision = None
        if self.preferLastChangedRev:
            try:
                revision = stdout_xml.getElementsByTagName('commit')[0].attributes['revision'].value
            except (KeyError, IndexError):
                msg =("SVN.parseGotRevision unable to detect Last Changed Rev in"
                      " output of svn info")
                log.msg(msg)
                # fall through and try to get 'Revision' instead

        if revision is None:
            try:
                revision = stdout_xml.getElementsByTagName('entry')[0].attributes['revision'].value
            except (KeyError, IndexError):
                msg =("SVN.parseGotRevision unable to detect revision in"
                      " output of svn info")
                log.msg(msg)
                raise buildstep.BuildStepFailed()

        msg = "Got SVN revision %s" % (revision, )
        self.stdio_log.addHeader(msg)
        self.updateSourceProperty('got_revision', revision)

        defer.returnValue(cmd.rc)


    def purge(self, ignore_ignores):
        """Delete everything that shown up on status."""
        command = ['status', '--xml']
        if ignore_ignores:
            command.append('--no-ignore')
        d = self._dovccmd(command, collectStdout=True)
        def parseAndRemove(stdout):
            files = []
            for filename in self.getUnversionedFiles(stdout, self.keep_on_purge):
                filename = self.workdir+'/'+str(filename)
                files.append(filename)
            if len(files) == 0:
                d = defer.succeed(0)
            else:
                if self.slaveVersionIsOlderThan('rmdir', '2.14'):
                    d = self.removeFiles(files)
                else:
                    d = self.runRmdir(files, abandonOnFailure=False)
            return d
        d.addCallback(parseAndRemove)
        def evaluateCommand(rc):
            if rc != 0:
                log.msg("Failed removing files")
                raise buildstep.BuildStepFailed()
            return rc
        d.addCallback(evaluateCommand)
        return d

    @staticmethod
    def getUnversionedFiles(xmlStr, keep_on_purge):
        try:
            result_xml = xml.dom.minidom.parseString(xmlStr)
        except xml.parsers.expat.ExpatError:
            log.err("Corrupted xml, aborting step")
            raise buildstep.BuildStepFailed()

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
            res = yield self.runRmdir(filename, abandonOnFailure=False)
            if res:
                defer.returnValue(res)
                return
        defer.returnValue(0)

    def checkSvn(self):
        cmd = buildstep.RemoteShellCommand(self.workdir, ['svn', '--version'],
                                           env=self.env,
                                           logEnviron=self.logEnviron,
                                           timeout=self.timeout)
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)
        def evaluate(cmd):
            if cmd.rc != 0:
                return False
            return True
        d.addCallback(lambda _: evaluate(cmd))
        return d

    def computeSourceRevision(self, changes):
        if not changes or None in [c.revision for c in changes]:
            return None
        lastChange = max([int(c.revision) for c in changes])
        return lastChange

