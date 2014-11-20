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

# Source step code for darcs

import StringIO

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log

from buildbot.config import ConfigErrors
from buildbot.interfaces import BuildSlaveTooOldError
from buildbot.process import buildstep
from buildbot.status.results import SUCCESS
from buildbot.steps.source.base import Source
from buildbot.steps.transfer import _FileReader


class Darcs(Source):

    """ Class for Darcs with all smarts """

    name = 'darcs'

    renderables = ['repourl']
    possible_modes = ('incremental', 'full')
    possible_methods = ('clobber', 'copy')

    def __init__(self, repourl=None, mode='incremental',
                 method=None, **kwargs):

        self.repourl = repourl
        self.method = method
        self.mode = mode
        Source.__init__(self, **kwargs)
        errors = []

        if self.mode not in self.possible_modes:
            errors.append("mode %s is not one of %s" % (self.mode, self.possible_modes))
        if self.mode == 'incremental' and self.method:
            errors.append("Incremental mode does not require method")

        if self.mode == 'full':
            if self.method is None:
                self.method = 'copy'
            elif self.method not in self.possible_methods:
                errors.append("Invalid method for mode == %s" % (self.mode))

        if repourl is None:
            errors.append("you must provide repourl")

        if errors:
            raise ConfigErrors(errors)

    def startVC(self, branch, revision, patch):
        self.revision = revision
        self.stdio_log = self.addLogForRemoteCommands("stdio")

        d = self.checkDarcs()

        def checkInstall(darcsInstalled):
            if not darcsInstalled:
                raise BuildSlaveTooOldError("Darcs is not installed on slave")
            return 0
        d.addCallback(checkInstall)
        d.addCallback(lambda _: self.sourcedirIsPatched())

        def checkPatched(patched):
            if patched:
                return self.copy()
            else:
                return 0

        d.addCallback(checkPatched)

        if self.mode == 'full':
            d.addCallback(lambda _: self.full())
        elif self.mode == 'incremental':
            d.addCallback(lambda _: self.incremental())

        if patch:
            d.addCallback(self.patch, patch)
        d.addCallback(self.parseGotRevision)
        d.addCallback(self.finish)
        d.addErrback(self.failed)
        return d

    def checkDarcs(self):
        cmd = buildstep.RemoteShellCommand(self.workdir, ['darcs', '--version'],
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

    @defer.inlineCallbacks
    def full(self):
        if self.method == 'clobber':
            yield self.clobber()
            return
        elif self.method == 'copy':
            yield self.copy()
            return

    @defer.inlineCallbacks
    def incremental(self):
        updatable = yield self._sourcedirIsUpdatable()
        if not updatable:
            yield self._checkout()
        else:
            command = ['darcs', 'pull', '--all', '--verbose']
            yield self._dovccmd(command)

    def copy(self):
        d = self.runRmdir(self.workdir, abandonOnFailure=False)
        self.workdir = 'source'
        d.addCallback(lambda _: self.incremental())

        def copy(_):
            cmd = buildstep.RemoteCommand('cpdir',
                                          {'fromdir': 'source',
                                           'todir': 'build',
                                           'logEnviron': self.logEnviron,
                                           'timeout': self.timeout, })
            cmd.useLog(self.stdio_log, False)
            d = self.runCommand(cmd)
            return d
        d.addCallback(copy)

        def resetWorkdir(_):
            self.workdir = 'build'
            return 0

        d.addCallback(resetWorkdir)
        return d

    def clobber(self):
        d = self.runRmdir(self.workdir)
        d.addCallback(lambda _: self._checkout())
        return d

    def _clone(self, abandonOnFailure=False):
        command = ['darcs', 'get', '--verbose', '--lazy', '--repo-name', self.workdir]
        d = defer.succeed(0)
        if self.revision:
            d.addCallback(lambda _: self._downloadFile(self.revision, '.darcs-context'))
            command.append('--context')
            command.append('.darcs-context')

        command.append(self.repourl)
        d.addCallback(lambda _: self._dovccmd(command, abandonOnFailure=abandonOnFailure,
                                              wkdir='.'))

        return d

    def _checkout(self):

        if self.retry:
            abandonOnFailure = (self.retry[1] <= 0)
        else:
            abandonOnFailure = True

        d = self._clone(abandonOnFailure)

        def _retry(res):
            if self.stopped or res == 0:
                return res
            delay, repeats = self.retry
            if repeats > 0:
                log.msg("Checkout failed, trying %d more times after %d seconds"
                        % (repeats, delay))
                self.retry = (delay, repeats - 1)
                df = defer.Deferred()
                df.addCallback(lambda _: self.runRmdir(self.workdir))
                df.addCallback(lambda _: self._checkout())
                reactor.callLater(delay, df.callback, None)
                return df
            return res

        if self.retry:
            d.addCallback(_retry)
        return d

    def finish(self, res):
        d = defer.succeed(res)

        def _gotResults(results):
            self.setStatus(self.cmd, results)
            log.msg("Closing log, sending result of the command %s " %
                    (self.cmd))
            return results
        d.addCallback(_gotResults)
        d.addCallback(self.finished)
        return d

    @defer.inlineCallbacks
    def parseGotRevision(self, _):
        revision = yield self._dovccmd(['darcs', 'changes', '--max-count=1'], collectStdout=True)
        self.updateSourceProperty('got_revision', revision)
        defer.returnValue(0)

    def _dovccmd(self, command, collectStdout=False, initialStdin=None, decodeRC={0: SUCCESS},
                 abandonOnFailure=True, wkdir=None):
        if not command:
            raise ValueError("No command specified")
        workdir = wkdir or self.workdir
        cmd = buildstep.RemoteShellCommand(workdir, command,
                                           env=self.env,
                                           logEnviron=self.logEnviron,
                                           timeout=self.timeout,
                                           collectStdout=collectStdout,
                                           initialStdin=initialStdin,
                                           decodeRC=decodeRC)
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)

        def evaluateCommand(cmd):
            if abandonOnFailure and cmd.didFail():
                log.msg("Source step failed while running command %s" % cmd)
                raise buildstep.BuildStepFailed()
            if collectStdout:
                return cmd.stdout
            else:
                return cmd.rc
        d.addCallback(lambda _: evaluateCommand(cmd))
        return d

    def _sourcedirIsUpdatable(self):
        return self.pathExists(self.build.path_module.join(self.workdir, '_darcs'))

    def _downloadFile(self, buf, filename):
        filereader = _FileReader(StringIO.StringIO(buf))
        args = {
            'slavedest': filename,
            'maxsize': None,
            'reader': filereader,
            'blocksize': 16 * 1024,
            'workdir': self.workdir,
            'mode': None
        }
        cmd = buildstep.RemoteCommand('downloadFile', args)
        cmd.useLog(self.stdio_log, False)
        log.msg("Downloading file: %s" % (filename))
        d = self.runCommand(cmd)

        def evaluateCommand(_):
            if cmd.didFail():
                raise buildstep.BuildStepFailed()
            return cmd.rc

        d.addCallback(evaluateCommand)
        return d
