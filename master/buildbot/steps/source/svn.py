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
                 depth=None, **kwargs):

        self.repourl = repourl
        self.username = username
        self.password = password
        self.extra_args = extra_args
        self.keep_on_purge = keep_on_purge or []
        self.depth = depth
        self.method=method
        self.mode = mode
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
        self.stdio_log = self.addLog("stdio")

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
            yield self._rmdir(self.workdir)

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
            yield self._rmdir(self.workdir)

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
        cmd = buildstep.RemoteCommand('rmdir', {'dir': self.workdir,
                                                'logEnviron': self.logEnviron,})
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)
        if cmd.didFail():
            raise buildstep.BuildStepFailed()
        
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
        cmd = buildstep.RemoteCommand('rmdir', {'dir': self.workdir,
                                                'logEnviron': self.logEnviron,})
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)

        if cmd.didFail():
            raise buildstep.BuildStepFailed()

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

    @defer.inlineCallbacks
    def _rmdir(self, dir):
        cmd = buildstep.RemoteCommand('rmdir',
                {'dir': dir, 'logEnviron': self.logEnviron })
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)
        if cmd.didFail():
            raise buildstep.BuildStepFailed()

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
        cmd = buildstep.RemoteCommand('stat', {'file': self.workdir + '/.svn',
                                               'logEnviron': self.logEnviron,})
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)

        if cmd.didFail():
            defer.returnValue(False)
            return

        # then run 'svn info' to check that the URL matches our repourl
        stdout = yield self._dovccmd(['info'], collectStdout=True)

        # extract the URL, handling whitespace carefully so that \r\n works
        # is a line terminator
        mo = re.search('^URL:\s*(.*?)\s*$', stdout, re.M)
        defer.returnValue(mo and mo.group(1) == self.repourl)
        return

    def parseGotRevision(self, _):
        # if this was a full/export, then we need to check svnversion in the
        # *source* directory, not the build directory
        svnversion_dir = self.workdir
        if self.mode == 'full' and self.method == 'export':
            svnversion_dir = 'source'

        cmd = buildstep.RemoteShellCommand(svnversion_dir, ['svnversion'],
                                           env=self.env,
                                           logEnviron=self.logEnviron,
                                           timeout=self.timeout,
                                           collectStdout=True)
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)
        def _setrev(_):
            stdout = cmd.stdout.strip()
            revision = stdout.rstrip('MSP')
            revision = revision.split(':')[-1]
            try:
                int(revision)
            except ValueError:
                msg =("SVN.parseGotRevision unable to parse output "
                      "of svnversion: '%s'" % stdout)
                log.msg(msg)
                raise buildstep.BuildStepFailed()

            log.msg("Got SVN revision %s" % (revision, ))
            self.updateSourceProperty('got_revision', revision)
            return 0
        d.addCallback(lambda _: _setrev(cmd.rc))
        return d

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
                    cmd = buildstep.RemoteCommand('rmdir', {'dir': files,
                                                            'logEnviron':
                                                            self.logEnviron,})
                    cmd.useLog(self.stdio_log, False)
                    d = self.runCommand(cmd)
                    d.addCallback(lambda _: cmd.rc)
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
            cmd = buildstep.RemoteCommand('rmdir', {'dir': filename,
                                                    'logEnviron': self.logEnviron,})
            cmd.useLog(self.stdio_log, False)
            yield self.runCommand(cmd)
            if cmd.rc != 0:
                defer.returnValue(cmd.rc)
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

