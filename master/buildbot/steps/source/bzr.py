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

from buildbot.interfaces import BuildSlaveTooOldError
from buildbot.process import buildstep
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
        Source.__init__(self, **kwargs)
        if repourl and baseURL:
            raise ValueError("you must provide exactly one of repourl and"
                             " baseURL")

        if repourl is None and baseURL is None:
            raise ValueError("you must privide at least one of repourl and"
                             " baseURL")

        if baseURL is not None and defaultBranch is None:
            raise ValueError("you must provide defaultBranch with baseURL")

        assert self.mode in ['incremental', 'full']

        if self.mode == 'full':
            assert self.method in ['clean', 'fresh', 'clobber', 'copy', None]

    def startVC(self, branch, revision, patch):
        if branch:
            self.branch = branch
        self.revision = revision
        self.method = self._getMethod()
        self.stdio_log = self.addLogForRemoteCommands("stdio")

        if self.repourl is None:
            self.repourl = os.path.join(self.baseURL, self.branch)

        d = self.checkBzr()

        def checkInstall(bzrInstalled):
            if not bzrInstalled:
                raise BuildSlaveTooOldError("bzr is not installed on slave")
            return 0
        d.addCallback(checkInstall)

        d.addCallback(lambda _: self.sourcedirIsPatched())

        def checkPatched(patched):
            if patched:
                return self._dovccmd(['clean-tree', '--ignored', '--force'])
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

    @defer.inlineCallbacks
    def incremental(self):
        updatable = yield self._sourcedirIsUpdatable()
        if updatable:
            command = ['update']
            if self.revision:
                command.extend(['-r', self.revision])
            yield self._dovccmd(command)
        else:
            yield self._doFull()

    @defer.inlineCallbacks
    def full(self):
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

    def clobber(self):
        d = self.runRmdir(self.workdir)
        d.addCallback(lambda _: self._doFull())
        return d

    def copy(self):
        d = self.runRmdir('build', abandonOnFailure=False)
        d.addCallback(lambda _: self.incremental())

        def copy(_):
            cmd = buildstep.RemoteCommand('cpdir',
                                          {'fromdir': 'source',
                                           'todir': 'build',
                                           'logEnviron': self.logEnviron, })
            cmd.useLog(self.stdio_log, False)
            d = self.runCommand(cmd)
            return d
        d.addCallback(copy)
        return d

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

    def _doFull(self):
        command = ['checkout', self.repourl, '.']
        if self.revision:
            command.extend(['-r', self.revision])

        if self.retry:
            abandonOnFailure = (self.retry[1] <= 0)
        else:
            abandonOnFailure = True
        d = self._dovccmd(command, abandonOnFailure=abandonOnFailure)

        def _retry(res):
            if self.stopped or res == 0:
                return res
            delay, repeats = self.retry
            if repeats > 0:
                log.msg("Checkout failed, trying %d more times after %d seconds"
                        % (repeats, delay))
                self.retry = (delay, repeats - 1)
                df = defer.Deferred()
                df.addCallback(lambda _: self.clobber())
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

    def _sourcedirIsUpdatable(self):
        return self.pathExists(self.build.path_module.join(self.workdir, '.bzr'))

    def computeSourceRevision(self, changes):
        if not changes:
            return None
        lastChange = max([int(c.revision) for c in changes])
        return lastChange

    def _dovccmd(self, command, abandonOnFailure=True, collectStdout=False):
        cmd = buildstep.RemoteShellCommand(self.workdir, ['bzr'] + command,
                                           env=self.env,
                                           logEnviron=self.logEnviron,
                                           timeout=self.timeout,
                                           collectStdout=collectStdout)
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

    def checkBzr(self):
        d = self._dovccmd(['--version'])

        def check(res):
            if res == 0:
                return True
            return False
        d.addCallback(check)
        return d

    def _getMethod(self):
        if self.method is not None and self.mode != 'incremental':
            return self.method
        elif self.mode == 'incremental':
            return None
        elif self.method is None and self.mode == 'full':
            return 'fresh'

    def parseGotRevision(self, _):
        d = self._dovccmd(["version-info", "--custom", "--template='{revno}"],
                          collectStdout=True)

        def setrev(stdout):
            revision = stdout.strip("'")
            try:
                int(revision)
            except ValueError:
                log.msg("Invalid revision number")
                raise buildstep.BuildStepFailed()

            log.msg("Got Git revision %s" % (revision, ))
            self.updateSourceProperty('got_revision', revision)
            return 0
        d.addCallback(setrev)
        return d
