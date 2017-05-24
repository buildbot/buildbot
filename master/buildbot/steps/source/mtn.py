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

from __future__ import absolute_import
from __future__ import print_function

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log

from buildbot.config import ConfigErrors
from buildbot.interfaces import WorkerTooOldError
from buildbot.process import buildstep
from buildbot.process import remotecommand
from buildbot.process.results import SUCCESS
from buildbot.steps.source.base import Source


class Monotone(Source):

    """ Class for Monotone with all smarts """

    name = 'monotone'

    renderables = ['repourl']
    possible_methods = ('clobber', 'copy', 'fresh', 'clean')

    def __init__(self, repourl=None, branch=None, progress=False,
                 mode='incremental', method=None, **kwargs):

        self.repourl = repourl
        self.method = method
        self.mode = mode
        self.branch = branch
        self.sourcedata = "%s?%s" % (self.repourl, self.branch)
        self.database = 'db.mtn'
        self.progress = progress
        Source.__init__(self, **kwargs)
        errors = []

        if not self._hasAttrGroupMember('mode', self.mode):
            errors.append("mode %s is not one of %s" %
                          (self.mode, self._listAttrGroupMembers('mode')))
        if self.mode == 'incremental' and self.method:
            errors.append("Incremental mode does not require method")

        if self.mode == 'full':
            if self.method is None:
                self.method = 'copy'
            elif self.method not in self.possible_methods:
                errors.append("Invalid method for mode == %s" % (self.mode))

        if repourl is None:
            errors.append("you must provide repourl")

        if branch is None:
            errors.append("you must provide branch")

        if errors:
            raise ConfigErrors(errors)

    @defer.inlineCallbacks
    def startVC(self, branch, revision, patch):
        self.revision = revision
        self.stdio_log = self.addLogForRemoteCommands("stdio")

        try:
            monotoneInstalled = yield self.checkMonotone()
            if not monotoneInstalled:
                raise WorkerTooOldError("Monotone is not installed on worker")

            yield self._checkDb()
            yield self._retryPull()

            # If we're not throwing away the workdir, check if it's
            # somehow patched or modified and revert.
            if self.mode != 'full' or self.method not in ('clobber', 'copy'):
                patched = yield self.sourcedirIsPatched()
                if patched:
                    yield self.clean()

            # Call a mode specific method
            fn = self._getAttrGroupMember('mode', self.mode)
            yield fn()

            if patch:
                yield self.patch(None, patch)
            yield self.parseGotRevision()
            self.finish()
        except Exception as e:
            self.failed(e)

    @defer.inlineCallbacks
    def mode_full(self):
        if self.method == 'clobber':
            yield self.clobber()
            return
        elif self.method == 'copy':
            yield self.copy()
            return

        updatable = yield self._sourcedirIsUpdatable()
        if not updatable:
            yield self.clobber()
        elif self.method == 'clean':
            yield self.clean()
            yield self._update()
        elif self.method == 'fresh':
            yield self.clean(False)
            yield self._update()
        else:
            raise ValueError("Unknown method, check your configuration")

    @defer.inlineCallbacks
    def mode_incremental(self):
        updatable = yield self._sourcedirIsUpdatable()
        if not updatable:
            yield self.clobber()
        else:
            yield self._update()

    @defer.inlineCallbacks
    def clobber(self):
        yield self.runRmdir(self.workdir)
        yield self._checkout()

    @defer.inlineCallbacks
    def copy(self):
        cmd = remotecommand.RemoteCommand('rmdir', {
            'dir': self.workdir,
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
        defer.returnValue(0)

    @defer.inlineCallbacks
    def checkMonotone(self):
        cmd = remotecommand.RemoteShellCommand(self.workdir,
                                               ['mtn', '--version'],
                                               env=self.env,
                                               logEnviron=self.logEnviron,
                                               timeout=self.timeout)
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)
        defer.returnValue(cmd.rc == 0)

    @defer.inlineCallbacks
    def clean(self, ignore_ignored=True):
        files = []
        commands = [['mtn', 'ls', 'unknown']]
        if not ignore_ignored:
            commands.append(['mtn', 'ls', 'ignored'])
        for cmd in commands:
            stdout = yield self._dovccmd(cmd, workdir=self.workdir,
                                         collectStdout=True)
            if not stdout:
                continue
            for filename in stdout.strip().split('\n'):
                filename = self.workdir + '/' + str(filename)
                files.append(filename)

        if not files:
            rc = 0
        else:
            if self.workerVersionIsOlderThan('rmdir', '2.14'):
                rc = yield self.removeFiles(files)
            else:
                rc = yield self.runRmdir(files, abandonOnFailure=False)

        if rc != 0:
            log.msg("Failed removing files")
            raise buildstep.BuildStepFailed()

    @defer.inlineCallbacks
    def removeFiles(self, files):
        for filename in files:
            res = yield self.runRmdir(filename, abandonOnFailure=False)
            if res:
                defer.returnValue(res)
                return
        defer.returnValue(0)

    def _checkout(self, abandonOnFailure=False):
        command = ['mtn', 'checkout', self.workdir, '--db', self.database]
        if self.revision:
            command.extend(['--revision', self.revision])
        command.extend(['--branch', self.branch])
        return self._dovccmd(command, workdir='.',
                             abandonOnFailure=abandonOnFailure)

    def _update(self, abandonOnFailure=False):
        command = ['mtn', 'update']
        if self.revision:
            command.extend(['--revision', self.revision])
        else:
            command.extend(['--revision', 'h:' + self.branch])
        command.extend(['--branch', self.branch])
        return self._dovccmd(command, workdir=self.workdir,
                             abandonOnFailure=abandonOnFailure)

    def _pull(self, abandonOnFailure=False):
        command = ['mtn', 'pull', self.sourcedata, '--db', self.database]
        if self.progress:
            command.extend(['--ticker=dot'])
        else:
            command.extend(['--ticker=none'])
        d = self._dovccmd(command, workdir='.',
                          abandonOnFailure=abandonOnFailure)
        return d

    @defer.inlineCallbacks
    def _retryPull(self):
        if self.retry:
            abandonOnFailure = (self.retry[1] <= 0)
        else:
            abandonOnFailure = True

        res = yield self._pull(abandonOnFailure)
        if self.retry:
            delay, repeats = self.retry
            if self.stopped or res == 0 or repeats <= 0:
                defer.returnValue(res)
            else:
                log.msg("Checkout failed, trying %d more times after %d seconds"
                        % (repeats, delay))
                self.retry = (delay, repeats - 1)
                df = defer.Deferred()
                df.addCallback(lambda _: self._retryPull())
                reactor.callLater(delay, df.callback, None)
                yield df

    @defer.inlineCallbacks
    def parseGotRevision(self):
        stdout = yield self._dovccmd(['mtn', 'automate', 'select', 'w:'],
                                     workdir=self.workdir,
                                     collectStdout=True)
        revision = stdout.strip()
        if len(revision) != 40:
            raise buildstep.BuildStepFailed()
        log.msg("Got Monotone revision %s" % (revision, ))
        self.updateSourceProperty('got_revision', revision)
        defer.returnValue(0)

    @defer.inlineCallbacks
    def _dovccmd(self, command, workdir,
                 collectStdout=False, initialStdin=None, decodeRC=None,
                 abandonOnFailure=True):
        if not command:
            raise ValueError("No command specified")

        if decodeRC is None:
            decodeRC = {0: SUCCESS}
        cmd = buildstep.RemoteShellCommand(workdir, command,
                                           env=self.env,
                                           logEnviron=self.logEnviron,
                                           timeout=self.timeout,
                                           collectStdout=collectStdout,
                                           initialStdin=initialStdin,
                                           decodeRC=decodeRC)
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)

        if abandonOnFailure and cmd.didFail():
            log.msg("Source step failed while running command %s" % cmd)
            raise buildstep.BuildStepFailed()
        if collectStdout:
            defer.returnValue(cmd.stdout)
        else:
            defer.returnValue(cmd.rc)

    @defer.inlineCallbacks
    def _checkDb(self):
        db_exists = yield self.pathExists(self.database)
        db_needs_init = False
        if db_exists:
            stdout = yield self._dovccmd(
                ['mtn', 'db', 'info', '--db', self.database],
                workdir='.',
                collectStdout=True)
            if stdout.find("migration needed") >= 0:
                log.msg("Older format database found, migrating it")
                yield self._dovccmd(['mtn', 'db', 'migrate', '--db',
                                     self.database],
                                    workdir='.')
            elif stdout.find("too new, cannot use") >= 0 or \
                    stdout.find("database has no tables") >= 0:
                # The database is of a newer format which the worker's
                # mtn version can not handle. Drop it and pull again
                # with that monotone version installed on the
                # worker. Do the same if it's an empty file.
                yield self.runRmdir(self.database)
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
            yield self._dovccmd(command, workdir='.')

    @defer.inlineCallbacks
    def _sourcedirIsUpdatable(self):
        workdir_path = self.build.path_module.join(self.workdir, '_MTN')
        workdir_exists = yield self.pathExists(workdir_path)

        if not workdir_exists:
            log.msg("Workdir does not exist, falling back to a fresh clone")

        defer.returnValue(workdir_exists)

    def finish(self):
        self.setStatus(self.cmd, 0)
        log.msg("Closing log, sending result of the command %s " %
                (self.cmd))
        return self.finished(0)
