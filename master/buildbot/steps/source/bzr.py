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


import os

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log

from buildbot.interfaces import WorkerSetupError
from buildbot.process import buildstep
from buildbot.process import remotecommand
from buildbot.process import results
from buildbot.steps.source.base import Source


class Bzr(Source):

    name = 'bzr'
    renderables = ['repourl', 'baseURL']

    def __init__(self, repourl=None, baseURL=None, mode='incremental',
                 method=None, defaultBranch=None, **kwargs):

        self.repourl = repourl
        self.baseURL = baseURL
        self.branch = defaultBranch
        self.mode = mode
        self.method = method
        super().__init__(**kwargs)
        if repourl and baseURL:
            raise ValueError("you must provide exactly one of repourl and"
                             " baseURL")

        if repourl is None and baseURL is None:
            raise ValueError("you must provide at least one of repourl and"
                             " baseURL")

        if baseURL is not None and defaultBranch is None:
            raise ValueError("you must provide defaultBranch with baseURL")

        if not self._hasAttrGroupMember('mode', self.mode):
            raise ValueError(f"mode {self.mode} is not one of {self._listAttrGroupMembers('mode')}")

        if self.mode == 'full':
            assert self.method in ['clean', 'fresh', 'clobber', 'copy', None]

    @defer.inlineCallbacks
    def run_vc(self, branch, revision, patch):
        if branch:
            self.branch = branch
        self.revision = revision
        self.method = self._getMethod()
        self.stdio_log = yield self.addLogForRemoteCommands("stdio")

        if self.repourl is None:
            self.repourl = os.path.join(self.baseURL, self.branch)

        installed = yield self.checkBzr()

        if not installed:
            raise WorkerSetupError("bzr is not installed on worker")

        patched = yield self.sourcedirIsPatched()

        if patched:
            yield self._dovccmd(['clean-tree', '--ignored', '--force'])

        yield self._getAttrGroupMember('mode', self.mode)()

        if patch:
            yield self.patch(patch)
        yield self.parseGotRevision()
        return results.SUCCESS

    @defer.inlineCallbacks
    def mode_incremental(self):
        updatable = yield self._sourcedirIsUpdatable()
        if updatable:
            command = ['update']
            if self.revision:
                command.extend(['-r', self.revision])
            yield self._dovccmd(command)
        else:
            yield self._doFull()

    @defer.inlineCallbacks
    def mode_full(self):
        if self.method == 'clobber':
            yield self.clobber()
            return
        elif self.method == 'copy':
            self.workdir = 'source'
            yield self.copy()
            return

        updatable = self._sourcedirIsUpdatable()
        if not updatable:
            log.msg("No bzr repo present, making full checkout")
            yield self._doFull()
        elif self.method == 'clean':
            yield self.clean()
        elif self.method == 'fresh':
            yield self.fresh()
        else:
            raise ValueError("Unknown method, check your configuration")

    @defer.inlineCallbacks
    def _clobber(self):
        cmd = remotecommand.RemoteCommand('rmdir', {'dir': self.workdir,
                                                    'logEnviron': self.logEnviron, })
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)

        if cmd.rc != 0:
            raise RuntimeError("Failed to delete directory")

    @defer.inlineCallbacks
    def clobber(self):
        yield self._clobber()
        yield self._doFull()

    @defer.inlineCallbacks
    def copy(self):
        cmd = remotecommand.RemoteCommand('rmdir', {'dir': 'build',
                                                    'logEnviron': self.logEnviron, })
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)
        yield self.mode_incremental()

        cmd = remotecommand.RemoteCommand('cpdir',
                                          {'fromdir': 'source',
                                           'todir': 'build',
                                           'logEnviron': self.logEnviron, })
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)

    def clean(self):
        d = self._dovccmd(['clean-tree', '--ignored', '--force'])
        command = ['update']
        if self.revision:
            command.extend(['-r', self.revision])
        d.addCallback(lambda _: self._dovccmd(command))
        return d

    def fresh(self):
        d = self._dovccmd(['clean-tree', '--force'])
        command = ['update']
        if self.revision:
            command.extend(['-r', self.revision])
        d.addCallback(lambda _: self._dovccmd(command))
        return d

    @defer.inlineCallbacks
    def _doFull(self):
        command = ['checkout', self.repourl, '.']
        if self.revision:
            command.extend(['-r', self.revision])

        if self.retry:
            abandonOnFailure = (self.retry[1] <= 0)
        else:
            abandonOnFailure = True

        res = yield self._dovccmd(command, abandonOnFailure=abandonOnFailure)

        if self.retry:
            if self.stopped or res == 0:
                return res
            delay, repeats = self.retry
            if repeats > 0:
                log.msg(f"Checkout failed, trying {repeats} more times after {delay} seconds")
                self.retry = (delay, repeats - 1)
                df = defer.Deferred()
                df.addCallback(lambda _: self._clobber())
                df.addCallback(lambda _: self._doFull())
                reactor.callLater(delay, df.callback, None)
                res = yield df

        return res

    def _sourcedirIsUpdatable(self):
        return self.pathExists(self.build.path_module.join(self.workdir, '.bzr'))

    def computeSourceRevision(self, changes):
        if not changes:
            return None
        lastChange = max(int(c.revision) for c in changes)
        return lastChange

    def _dovccmd(self, command, abandonOnFailure=True, collectStdout=False):
        cmd = remotecommand.RemoteShellCommand(self.workdir, ['bzr'] + command,
                                               env=self.env,
                                               logEnviron=self.logEnviron,
                                               timeout=self.timeout,
                                               collectStdout=collectStdout)
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)

        @d.addCallback
        def evaluateCommand(_):
            if abandonOnFailure and cmd.didFail():
                log.msg(f"Source step failed while running command {cmd}")
                raise buildstep.BuildStepFailed()
            if collectStdout:
                return cmd.stdout
            return cmd.rc
        return d

    def checkBzr(self):
        d = self._dovccmd(['--version'])

        @d.addCallback
        def check(res):
            return res == 0
        return d

    def _getMethod(self):
        if self.method is not None and self.mode != 'incremental':
            return self.method
        elif self.mode == 'incremental':
            return None
        elif self.method is None and self.mode == 'full':
            return 'fresh'
        return None

    @defer.inlineCallbacks
    def parseGotRevision(self):
        stdout = yield self._dovccmd(["version-info", "--custom", "--template='{revno}"],
                                     collectStdout=True)

        revision = stdout.strip("'")
        try:
            int(revision)
        except ValueError as e:
            log.msg("Invalid revision number")
            raise buildstep.BuildStepFailed() from e

        log.msg(f"Got Git revision {revision}")
        self.updateSourceProperty('got_revision', revision)
