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
Source step code for Monotone
"""

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log

from buildbot.config import ConfigErrors
from buildbot.interfaces import WorkerSetupError
from buildbot.process import buildstep
from buildbot.process import remotecommand
from buildbot.process.results import SUCCESS
from buildbot.steps.source.base import Source


class Monotone(Source):
    """Class for Monotone with all smarts"""

    name = 'monotone'

    renderables = ['repourl']
    possible_methods = ('clobber', 'copy', 'fresh', 'clean')

    def __init__(
        self, repourl=None, branch=None, progress=False, mode='incremental', method=None, **kwargs
    ):
        self.repourl = repourl
        self.method = method
        self.mode = mode
        self.branch = branch
        self.sourcedata = f"{self.repourl}?{self.branch}"
        self.database = 'db.mtn'
        self.progress = progress
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

        if branch is None:
            errors.append("you must provide branch")

        if errors:
            raise ConfigErrors(errors)

    async def run_vc(self, branch, revision, patch):
        self.revision = revision
        self.stdio_log = await self.addLogForRemoteCommands("stdio")

        try:
            monotoneInstalled = await self.checkMonotone()
            if not monotoneInstalled:
                raise WorkerSetupError("Monotone is not installed on worker")

            await self._checkDb()
            await self._retryPull()

            # If we're not throwing away the workdir, check if it's
            # somehow patched or modified and revert.
            if self.mode != 'full' or self.method not in ('clobber', 'copy'):
                patched = await self.sourcedirIsPatched()
                if patched:
                    await self.clean()

            # Call a mode specific method
            fn = self._getAttrGroupMember('mode', self.mode)
            await fn()

            if patch:
                await self.patch(patch)
            await self.parseGotRevision()
            return SUCCESS
        finally:
            pass  # FIXME: remove this try:raise block

    async def mode_full(self):
        if self.method == 'clobber':
            await self.clobber()
            return
        elif self.method == 'copy':
            await self.copy()
            return

        updatable = await self._sourcedirIsUpdatable()
        if not updatable:
            await self.clobber()
        elif self.method == 'clean':
            await self.clean()
            await self._update()
        elif self.method == 'fresh':
            await self.clean(False)
            await self._update()
        else:
            raise ValueError("Unknown method, check your configuration")

    async def mode_incremental(self):
        updatable = await self._sourcedirIsUpdatable()
        if not updatable:
            await self.clobber()
        else:
            await self._update()

    async def clobber(self):
        await self.runRmdir(self.workdir)
        await self._checkout()

    async def copy(self):
        cmd = remotecommand.RemoteCommand(
            'rmdir',
            {
                'dir': self.workdir,
                'logEnviron': self.logEnviron,
                'timeout': self.timeout,
            },
        )
        cmd.useLog(self.stdio_log, False)
        await self.runCommand(cmd)

        self.workdir = 'source'
        await self.mode_incremental()
        cmd = remotecommand.RemoteCommand(
            'cpdir',
            {
                'fromdir': 'source',
                'todir': 'build',
                'logEnviron': self.logEnviron,
                'timeout': self.timeout,
            },
        )
        cmd.useLog(self.stdio_log, False)
        await self.runCommand(cmd)

        self.workdir = 'build'
        return 0

    async def checkMonotone(self):
        cmd = remotecommand.RemoteShellCommand(
            self.workdir,
            ['mtn', '--version'],
            env=self.env,
            logEnviron=self.logEnviron,
            timeout=self.timeout,
        )
        cmd.useLog(self.stdio_log, False)
        await self.runCommand(cmd)
        return cmd.rc == 0

    async def clean(self, ignore_ignored=True):
        files = []
        commands = [['mtn', 'ls', 'unknown']]
        if not ignore_ignored:
            commands.append(['mtn', 'ls', 'ignored'])
        for cmd in commands:
            stdout = await self._dovccmd(cmd, workdir=self.workdir, collectStdout=True)
            if not stdout:
                continue
            for filename in stdout.strip().split('\n'):
                filename = self.workdir + '/' + str(filename)
                files.append(filename)

        if not files:
            rc = 0
        else:
            if self.workerVersionIsOlderThan('rmdir', '2.14'):
                rc = await self.removeFiles(files)
            else:
                rc = await self.runRmdir(files, abandonOnFailure=False)

        if rc != 0:
            log.msg("Failed removing files")
            raise buildstep.BuildStepFailed()

    async def removeFiles(self, files):
        for filename in files:
            res = await self.runRmdir(filename, abandonOnFailure=False)
            if res:
                return res
        return 0

    def _checkout(self, abandonOnFailure=False):
        command = ['mtn', 'checkout', self.workdir, '--db', self.database]
        if self.revision:
            command.extend(['--revision', self.revision])
        command.extend(['--branch', self.branch])
        return self._dovccmd(command, workdir='.', abandonOnFailure=abandonOnFailure)

    def _update(self, abandonOnFailure=False):
        command = ['mtn', 'update']
        if self.revision:
            command.extend(['--revision', self.revision])
        else:
            command.extend(['--revision', 'h:' + self.branch])
        command.extend(['--branch', self.branch])
        return self._dovccmd(command, workdir=self.workdir, abandonOnFailure=abandonOnFailure)

    def _pull(self, abandonOnFailure=False):
        command = ['mtn', 'pull', self.sourcedata, '--db', self.database]
        if self.progress:
            command.extend(['--ticker=dot'])
        else:
            command.extend(['--ticker=none'])
        d = self._dovccmd(command, workdir='.', abandonOnFailure=abandonOnFailure)
        return d

    async def _retryPull(self):
        if self.retry:
            abandonOnFailure = self.retry[1] <= 0
        else:
            abandonOnFailure = True

        res = await self._pull(abandonOnFailure)
        if self.retry:
            delay, repeats = self.retry
            if self.stopped or res == 0 or repeats <= 0:
                return res
            else:
                log.msg(f"Checkout failed, trying {repeats} more times after {delay} seconds")
                self.retry = (delay, repeats - 1)
                df = defer.Deferred()
                df.addCallback(lambda _: self._retryPull())
                reactor.callLater(delay, df.callback, None)
                await df
        return None

    async def parseGotRevision(self):
        stdout = await self._dovccmd(
            ['mtn', 'automate', 'select', 'w:'], workdir=self.workdir, collectStdout=True
        )
        revision = stdout.strip()
        if len(revision) != 40:
            raise buildstep.BuildStepFailed()
        log.msg(f"Got Monotone revision {revision}")
        self.updateSourceProperty('got_revision', revision)
        return 0

    async def _dovccmd(
        self,
        command,
        workdir,
        collectStdout=False,
        initialStdin=None,
        decodeRC=None,
        abandonOnFailure=True,
    ):
        if not command:
            raise ValueError("No command specified")

        if decodeRC is None:
            decodeRC = {0: SUCCESS}
        cmd = remotecommand.RemoteShellCommand(
            workdir,
            command,
            env=self.env,
            logEnviron=self.logEnviron,
            timeout=self.timeout,
            collectStdout=collectStdout,
            initialStdin=initialStdin,
            decodeRC=decodeRC,
        )
        cmd.useLog(self.stdio_log, False)
        await self.runCommand(cmd)

        if abandonOnFailure and cmd.didFail():
            log.msg(f"Source step failed while running command {cmd}")
            raise buildstep.BuildStepFailed()
        if collectStdout:
            return cmd.stdout
        else:
            return cmd.rc

    async def _checkDb(self):
        db_exists = await self.pathExists(self.database)
        db_needs_init = False
        if db_exists:
            stdout = await self._dovccmd(
                ['mtn', 'db', 'info', '--db', self.database], workdir='.', collectStdout=True
            )
            if stdout.find("migration needed") >= 0:
                log.msg("Older format database found, migrating it")
                await self._dovccmd(['mtn', 'db', 'migrate', '--db', self.database], workdir='.')
            elif (
                stdout.find("too new, cannot use") >= 0
                or stdout.find("database has no tables") >= 0
            ):
                # The database is of a newer format which the worker's
                # mtn version can not handle. Drop it and pull again
                # with that monotone version installed on the
                # worker. Do the same if it's an empty file.
                await self.runRmdir(self.database)
                db_needs_init = True
            elif stdout.find("not a monotone database") >= 0:
                # There exists a database file, but it's not a valid
                # monotone database. Do not delete it, but fail with
                # an error.
                raise buildstep.BuildStepFailed()
            else:
                log.msg("Database exists and compatible")
        else:
            db_needs_init = True
            log.msg("Database does not exist")

        if db_needs_init:
            command = ['mtn', 'db', 'init', '--db', self.database]
            await self._dovccmd(command, workdir='.')

    async def _sourcedirIsUpdatable(self):
        workdir_path = self.build.path_module.join(self.workdir, '_MTN')
        workdir_exists = await self.pathExists(workdir_path)

        if not workdir_exists:
            log.msg("Workdir does not exist, falling back to a fresh clone")

        return workdir_exists
