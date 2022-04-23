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
"""
Source step code for darcs
"""


from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log

from buildbot.config import ConfigErrors
from buildbot.interfaces import WorkerSetupError
from buildbot.process import buildstep
from buildbot.process import remotecommand
from buildbot.process import results
from buildbot.process.results import SUCCESS
from buildbot.steps.source.base import Source


class Darcs(Source):

    """ Class for Darcs with all smarts """

    name = 'darcs'

    renderables = ['repourl']
    possible_methods = ('clobber', 'copy')

    def __init__(self, repourl=None, mode='incremental',
                 method=None, **kwargs):

        self.repourl = repourl
        self.method = method
        self.mode = mode
        super().__init__(**kwargs)
        errors = []

        if not self._hasAttrGroupMember('mode', self.mode):
            errors.append(f"mode {self.mode} is not one of {self._listAttrGroupMembers('mode')}")
        if self.mode == 'incremental' and self.method:
            errors.append("Incremental mode does not require method")

        if self.mode == 'full':
            if self.method is None:
                self.method = 'copy'
            elif self.method not in self.possible_methods:
                errors.append(f"Invalid method for mode == {self.mode}")

        if repourl is None:
            errors.append("you must provide repourl")

        if errors:
            raise ConfigErrors(errors)

    @defer.inlineCallbacks
    def run_vc(self, branch, revision, patch):
        self.revision = revision
        self.stdio_log = yield self.addLogForRemoteCommands("stdio")

        installed = yield self.checkDarcs()
        if not installed:
            raise WorkerSetupError("Darcs is not installed on worker")

        patched = yield self.sourcedirIsPatched()

        if patched:
            yield self.copy()

        yield self._getAttrGroupMember('mode', self.mode)()

        if patch:
            yield self.patch(patch)
        yield self.parseGotRevision()
        return results.SUCCESS

    @defer.inlineCallbacks
    def checkDarcs(self):
        cmd = remotecommand.RemoteShellCommand(self.workdir, ['darcs', '--version'],
                                               env=self.env,
                                               logEnviron=self.logEnviron,
                                               timeout=self.timeout)
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)
        return cmd.rc == 0

    @defer.inlineCallbacks
    def mode_full(self):
        if self.method == 'clobber':
            yield self.clobber()
            return
        elif self.method == 'copy':
            yield self.copy()
            return

    @defer.inlineCallbacks
    def mode_incremental(self):
        updatable = yield self._sourcedirIsUpdatable()
        if not updatable:
            yield self._checkout()
        else:
            command = ['darcs', 'pull', '--all', '--verbose']
            yield self._dovccmd(command)

    @defer.inlineCallbacks
    def copy(self):
        cmd = remotecommand.RemoteCommand('rmdir', {'dir': self.workdir,
                                                    'logEnviron': self.logEnviron,
                                                    'timeout': self.timeout, })
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)

        self.workdir = 'source'
        yield self.mode_incremental()

        cmd = remotecommand.RemoteCommand('cpdir',
                                          {'fromdir': 'source',
                                           'todir': 'build',
                                           'logEnviron': self.logEnviron,
                                           'timeout': self.timeout, })
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)

        self.workdir = 'build'

    @defer.inlineCallbacks
    def clobber(self):
        yield self.runRmdir(self.workdir)
        yield self._checkout()

    @defer.inlineCallbacks
    def _clone(self, abandonOnFailure=False):
        command = ['darcs', 'get', '--verbose',
                   '--lazy', '--repo-name', self.workdir]

        if self.revision:
            yield self.downloadFileContentToWorker('.darcs-context', self.revision)
            command.append('--context')
            command.append('.darcs-context')

        command.append(self.repourl)
        yield self._dovccmd(command, abandonOnFailure=abandonOnFailure, wkdir='.')

    @defer.inlineCallbacks
    def _checkout(self):

        if self.retry:
            abandonOnFailure = (self.retry[1] <= 0)
        else:
            abandonOnFailure = True

        res = yield self._clone(abandonOnFailure)

        if self.retry:
            if self.stopped or res == 0:
                return res
            delay, repeats = self.retry
            if repeats > 0:
                log.msg(f"Checkout failed, trying {repeats} more times after {delay} seconds")
                self.retry = (delay, repeats - 1)
                df = defer.Deferred()
                df.addCallback(lambda _: self.runRmdir(self.workdir))
                df.addCallback(lambda _: self._checkout())
                reactor.callLater(delay, df.callback, None)
                res = yield df
        return res

    @defer.inlineCallbacks
    def parseGotRevision(self):
        revision = yield self._dovccmd(['darcs', 'changes', '--max-count=1'], collectStdout=True)
        self.updateSourceProperty('got_revision', revision)

    @defer.inlineCallbacks
    def _dovccmd(self, command, collectStdout=False, initialStdin=None, decodeRC=None,
                 abandonOnFailure=True, wkdir=None):
        if not command:
            raise ValueError("No command specified")

        if decodeRC is None:
            decodeRC = {0: SUCCESS}
        workdir = wkdir or self.workdir
        cmd = remotecommand.RemoteShellCommand(workdir, command,
                                               env=self.env,
                                               logEnviron=self.logEnviron,
                                               timeout=self.timeout,
                                               collectStdout=collectStdout,
                                               initialStdin=initialStdin,
                                               decodeRC=decodeRC)
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)

        if abandonOnFailure and cmd.didFail():
            log.msg(f"Source step failed while running command {cmd}")
            raise buildstep.BuildStepFailed()
        if collectStdout:
            return cmd.stdout
        return cmd.rc

    def _sourcedirIsUpdatable(self):
        return self.pathExists(self.build.path_module.join(self.workdir, '_darcs'))
