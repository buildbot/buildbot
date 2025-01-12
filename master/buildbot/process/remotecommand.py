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
from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from twisted.internet import defer
from twisted.internet import error
from twisted.python import log
from twisted.python.failure import Failure
from twisted.spread import pb

from buildbot import util
from buildbot.pbutil import decode
from buildbot.process import metrics
from buildbot.process.results import CANCELLED
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.util.eventual import eventually
from buildbot.util.lineboundaries import LineBoundaryFinder
from buildbot.util.twisted import async_to_deferred
from buildbot.worker.protocols import base

if TYPE_CHECKING:
    from typing import Any
    from typing import Awaitable
    from typing import Callable

    from buildbot.process.buildstep import BuildStep
    from buildbot.process.log import Log
    from buildbot.process.log import StreamLog
    from buildbot.worker.base import AbstractWorker
    from buildbot.worker.protocols.base import Connection


class RemoteException(Exception):
    pass


class RemoteCommand(base.RemoteCommandImpl):
    # class-level unique identifier generator for command ids
    _commandCounter = 0

    active = False
    rc: int | None = None
    debug = False

    def __init__(
        self,
        remote_command: str | list[str],
        args: dict[str, Any],
        ignore_updates: bool = False,
        collectStdout: bool = False,
        collectStderr: bool = False,
        decodeRC: dict[int | None, int] | None = None,
        stdioLogName: str = 'stdio',
    ) -> None:
        if decodeRC is None:
            decodeRC = {0: SUCCESS}
        self.logs: dict[str, Any] = {}
        self.delayedLogs: dict[
            str,
            tuple[
                Callable[[RemoteCommand], Awaitable[StreamLog]],
                bool,
            ],
        ] = {}
        self._closeWhenFinished: dict[str, bool] = {}
        self.collectStdout: bool = collectStdout
        self.collectStderr: bool = collectStderr
        self.stdout = ''
        self.stderr = ''
        self.updates: defaultdict[str, list[Any]] = defaultdict(list)
        self.stdioLogName: str = stdioLogName
        self._startTime: float | None = None
        self._remoteElapsed: float | None = None
        self.remote_failure_reason = None
        self.remote_command: str | list[str] = remote_command
        self.args: dict[str, Any] = args
        self.ignore_updates: bool = ignore_updates
        self.decodeRC: dict[int | None, int] = decodeRC
        self.conn: Connection | None = None
        self._is_conn_test_fake = False
        self.worker: AbstractWorker | None = None
        self.step: BuildStep | None = None
        self.builder_name: str | None = None
        self.commandID: str | None = None
        self.deferred: defer.Deferred[RemoteCommand] | None = None
        self.interrupted: bool = False
        # a lock to make sure that only one log-handling method runs at a time.
        # This is really only a problem with old-style steps, which do not
        # wait for the Deferred from one method before invoking the next.
        self.loglock = defer.DeferredLock()
        self._line_boundary_finders: defaultdict[
            str,
            LineBoundaryFinder,
        ] = defaultdict(LineBoundaryFinder)

    def __repr__(self) -> str:
        return f"<RemoteCommand '{self.remote_command}' at {id(self)}>"

    @classmethod
    def generate_new_command_id(cls) -> str:
        cmd_id = cls._commandCounter
        cls._commandCounter += 1
        return f"{cmd_id}"

    @classmethod
    def get_last_generated_command_id(cls) -> str:
        cmd_id = cls._commandCounter - 1
        return f"{cmd_id}"

    def run(
        self,
        step: BuildStep,
        conn: Connection,
        builder_name: str,
    ) -> defer.Deferred[RemoteCommand]:
        self.active = True
        self.step = step
        self.conn = conn
        self.builder_name = builder_name

        # This probably could be solved in a cleaner way.
        self._is_conn_test_fake = hasattr(self.conn, 'is_fake_test_connection')

        self.commandID = RemoteCommand.generate_new_command_id()

        log.msg(f"{self}: RemoteCommand.run [{self.commandID}]")
        self.deferred = defer.Deferred()

        d = defer.maybeDeferred(self._start)

        # _finished is called with an error for unknown commands, errors
        # that occur while the command is starting (including OSErrors in
        # exec()), StaleBroker (when the connection was lost before we
        # started), and pb.PBConnectionLost (when the worker isn't responding
        # over this connection, perhaps it had a power failure, or NAT
        # weirdness). If this happens, self.deferred is fired right away.
        d.addErrback(self._finished)

        # Connections which are lost while the command is running are caught
        # when our parent Step calls our .lostRemote() method.
        return self.deferred

    def useLog(
        self,
        log_: Log,
        closeWhenFinished: bool = False,
        logfileName: str | None = None,
    ) -> None:
        # NOTE: log may be a SyngLogFileWrapper or a Log instance, depending on
        # the step
        if not logfileName:
            logfileName = log_.getName()
        assert logfileName not in self.logs
        assert logfileName not in self.delayedLogs
        self.logs[logfileName] = log_
        self._closeWhenFinished[logfileName] = closeWhenFinished

    def useLogDelayed(
        self,
        logfileName: str,
        activateCallBack: Callable[
            [RemoteCommand], defer.Deferred[StreamLog] | Awaitable[StreamLog]
        ],
        closeWhenFinished: bool = False,
    ) -> None:
        assert logfileName not in self.logs
        assert logfileName not in self.delayedLogs
        self.delayedLogs[logfileName] = (activateCallBack, closeWhenFinished)

    def _start(self) -> defer.Deferred:
        self._startTime = util.now()
        # This method only initiates the remote command.
        # We will receive remote_update messages as the command runs.
        # We will get a single remote_complete when it finishes.
        # We should fire self.deferred when the command is done.
        assert self.conn is not None
        d = self.conn.remoteStartCommand(
            self, self.builder_name, self.commandID, self.remote_command, self.args
        )
        return d

    @async_to_deferred
    async def _finished(self, failure=None) -> None:
        # Finished may be called concurrently by a message from worker and interruption due to
        # lost connection.
        if not self.active:
            return
        self.active = False

        # the rc is send asynchronously and there is a chance it is still in the callback queue
        # when finished is received, we have to workaround in the master because worker might be
        # older
        if not self._is_conn_test_fake:
            timeout = 10
            while self.rc is None and timeout > 0:
                await util.asyncSleep(0.1)
                timeout -= 1

        assert self.deferred is not None
        try:
            await self.remoteComplete(failure)
            # this fires the original deferred we returned from .run(),
            self.deferred.callback(self)
        except Exception as e:
            self.deferred.errback(e)

    @async_to_deferred
    async def interrupt(self, why) -> None:
        log.msg("RemoteCommand.interrupt", self, why)

        if self.conn and isinstance(why, Failure) and why.check(error.ConnectionLost):
            # Note that we may be in the process of interruption and waiting for the worker to
            # return the final results when the connection is disconnected.
            log.msg("RemoteCommand.interrupt: lost worker")
            self.conn = None
            self._finished(why)
            return
        if not self.active or self.interrupted:
            log.msg(" but this RemoteCommand is already inactive")
            return
        if not self.conn:
            log.msg(" but our .conn went away")
            return

        self.interrupted = True
        # tell the remote command to halt. Returns a Deferred that will fire
        # when the interrupt command has been delivered.

        try:
            await self.conn.remoteInterruptCommand(self.builder_name, self.commandID, str(why))
            # the worker may not have remote_interruptCommand
        except Exception as e:
            log.msg("RemoteCommand.interrupt failed", self, e)

    def remote_update_msgpack(self, updates: list[tuple[str, Any]]) -> None:
        assert self.worker is not None
        self.worker.messageReceivedFromWorker()
        try:
            for key, value in updates:
                if self.active and not self.ignore_updates:
                    if key in ['stdout', 'stderr', 'header']:
                        self.remoteUpdate(key, value[0], False)
                    elif key == "log":
                        logname, data = value
                        self.remoteUpdate(key, (logname, data[0]), False)
                    else:
                        self.remoteUpdate(key, value, False)
        except Exception:
            # log failure, terminate build, let worker retire the update
            self._finished(Failure())

    def split_line(self, stream: str, text: str) -> str | None:
        return self._line_boundary_finders[stream].append(text)

    def remote_update(self, updates: list[tuple[dict[str | bytes, Any], int]]) -> int:
        """
        I am called by the worker's
        L{buildbot_worker.base.WorkerForBuilderBase.sendUpdate} so
        I can receive updates from the running remote command.

        @type  updates: list of [object, int]
        @param updates: list of updates from the remote command
        """
        assert self.worker is not None
        self.worker.messageReceivedFromWorker()
        max_updatenum = 0
        for update, num in updates:
            try:
                if self.active and not self.ignore_updates:
                    for key, value in update.items():
                        key = util.bytes2unicode(key)
                        value = decode(value)
                        if key in ['stdout', 'stderr', 'header']:
                            assert isinstance(value, str), type(value)
                            whole_line = self.split_line(key, value)
                            if whole_line is not None:
                                self.remoteUpdate(key, whole_line, False)
                        elif key == "log":
                            logname, data = value
                            assert isinstance(logname, str), type(logname)
                            assert isinstance(data, str), type(data)
                            whole_line = self.split_line(logname, data)
                            if whole_line is not None:
                                value = (logname, whole_line)
                                self.remoteUpdate(key, value, False)
                        else:
                            self.remoteUpdate(key, value, False)

            except Exception:
                # log failure, terminate build, let worker retire the update
                self._finished(Failure())
                # TODO: what if multiple updates arrive? should
                # skip the rest but ack them all
            max_updatenum = max(max_updatenum, num)
        return max_updatenum

    def remote_complete(self, failure=None) -> None:
        """
        Called by the worker's
        L{buildbot_worker.base.WorkerForBuilderBase.commandComplete} to
        notify me the remote command has finished.

        @type  failure: L{twisted.python.failure.Failure} or None

        @rtype: None
        """
        assert self.worker is not None
        self.worker.messageReceivedFromWorker()
        # call the real remoteComplete a moment later, but first return an
        # acknowledgement so the worker can retire the completion message.
        if self.active:
            eventually(self._finished, failure)

    @util.deferredLocked('loglock')
    @async_to_deferred
    async def addStdout(self, data) -> None:
        if self.collectStdout:
            self.stdout += data
        if self.stdioLogName is not None and self.stdioLogName in self.logs:
            await self.logs[self.stdioLogName].addStdout(data)

    @util.deferredLocked('loglock')
    @async_to_deferred
    async def add_stdout_lines(self, data, is_flushed: bool) -> None:
        if self.collectStdout:
            if is_flushed:
                data = data[:-1]
            self.stdout += data
        if self.stdioLogName is not None and self.stdioLogName in self.logs:
            await self.logs[self.stdioLogName].add_stdout_lines(data)

    @util.deferredLocked('loglock')
    @async_to_deferred
    async def addStderr(self, data) -> None:
        if self.collectStderr:
            self.stderr += data
        if self.stdioLogName is not None and self.stdioLogName in self.logs:
            await self.logs[self.stdioLogName].addStderr(data)

    @util.deferredLocked('loglock')
    @async_to_deferred
    async def add_stderr_lines(self, data, is_flushed) -> None:
        if self.collectStderr:
            if is_flushed:
                data = data[:-1]
            self.stderr += data
        if self.stdioLogName is not None and self.stdioLogName in self.logs:
            await self.logs[self.stdioLogName].add_stderr_lines(data)

    @util.deferredLocked('loglock')
    @async_to_deferred
    async def addHeader(self, data) -> None:
        if self.stdioLogName is not None and self.stdioLogName in self.logs:
            await self.logs[self.stdioLogName].addHeader(data)

    @util.deferredLocked('loglock')
    @async_to_deferred
    async def add_header_lines(self, data) -> None:
        if self.stdioLogName is not None and self.stdioLogName in self.logs:
            await self.logs[self.stdioLogName].add_header_lines(data)

    @util.deferredLocked('loglock')
    @async_to_deferred
    async def addToLog(self, logname, data) -> None:
        # Activate delayed logs on first data.
        if logname in self.delayedLogs:
            (activateCallBack, closeWhenFinished) = self.delayedLogs.pop(logname)
            loog = await activateCallBack(self)
            self.logs[logname] = loog
            self._closeWhenFinished[logname] = closeWhenFinished

        if logname in self.logs:
            await self.logs[logname].add_stdout_lines(data)
        else:
            log.msg(f"{self}.addToLog: no such log {logname}")

    @metrics.countMethod('RemoteCommand.remoteUpdate()')
    @async_to_deferred
    async def remoteUpdate(self, key: str, value, is_flushed: bool) -> None:
        def cleanup(data):
            if self.step is None or self.step.build is None:
                return data
            return self.step.build.properties.cleanupTextFromSecrets(data)

        if self.debug:
            log.msg(f"Update[{key}]: {value}")
        if key == "stdout":
            await self.add_stdout_lines(cleanup(value), is_flushed)
        if key == "stderr":
            await self.add_stderr_lines(cleanup(value), is_flushed)
        if key == "header":
            await self.add_header_lines(cleanup(value))
        if key == "log":
            logname, data = value
            await self.addToLog(logname, cleanup(data))
        if key == "rc":
            rc = self.rc = value
            log.msg(f"{self} rc={rc}")
            await self.add_header_lines(f"program finished with exit code {rc}\n")
        if key == "elapsed":
            self._remoteElapsed = value
        if key == "failure_reason":
            self.remote_failure_reason = value

        # TODO: these should be handled at the RemoteCommand level
        if key not in ('stdout', 'stderr', 'header', 'rc', "failure_reason"):
            self.updates[key].append(value)

    @async_to_deferred
    async def remoteComplete(self, maybeFailure) -> None:
        if self._startTime and self._remoteElapsed:
            delta = (util.now() - self._startTime) - self._remoteElapsed
            metrics.MetricTimeEvent.log("RemoteCommand.overhead", delta)

        for key, lbf in self._line_boundary_finders.items():
            if key in ['stdout', 'stderr', 'header']:
                whole_line = lbf.flush()
                if whole_line is not None:
                    await self.remoteUpdate(key, whole_line, True)
            else:
                logname = key
                whole_line = lbf.flush()
                value = (logname, whole_line)
                if whole_line is not None:
                    await self.remoteUpdate("log", value, True)

        async with self.loglock:
            for name, loog in self.logs.items():
                if self._closeWhenFinished[name]:
                    if maybeFailure:
                        await loog.addHeader(f"\nremoteFailed: {maybeFailure}")
                    else:
                        log.msg(f"closing log {loog}")
                    await loog.finish()

        if maybeFailure:
            # Message Pack protocol can not send an exception object back to the master, so
            # exception information is sent as a string
            if isinstance(maybeFailure, str):
                raise RemoteException(maybeFailure)

            # workaround http://twistedmatrix.com/trac/ticket/5507
            # CopiedFailure cannot be raised back, this make debug difficult
            if isinstance(maybeFailure, pb.CopiedFailure):
                maybeFailure.value = RemoteException(
                    f"{maybeFailure.type}: {maybeFailure.value}\n{maybeFailure.getTraceback()}"
                )
                maybeFailure.type = RemoteException
            maybeFailure.raiseException()

    def results(self) -> int:
        if self.interrupted:
            return CANCELLED
        if self.rc in self.decodeRC:
            return self.decodeRC[self.rc]
        return FAILURE

    def didFail(self) -> bool:
        return self.results() == FAILURE


LoggedRemoteCommand = RemoteCommand


class RemoteShellCommand(RemoteCommand):
    def __init__(
        self,
        workdir,
        command,
        env=None,
        want_stdout=1,
        want_stderr=1,
        timeout=20 * 60,
        maxTime=None,
        max_lines=None,
        sigtermTime=None,
        logfiles=None,
        usePTY=None,
        logEnviron=True,
        collectStdout=False,
        collectStderr=False,
        interruptSignal=None,
        initialStdin=None,
        decodeRC=None,
        stdioLogName='stdio',
    ):
        if logfiles is None:
            logfiles = {}
        if decodeRC is None:
            decodeRC = {0: SUCCESS}
        self.command = command  # stash .command, set it later
        if isinstance(self.command, (str, bytes)):
            # Single string command doesn't support obfuscation.
            self.fake_command = command
        else:
            # Try to obfuscate command.
            def obfuscate(arg):
                if isinstance(arg, tuple) and len(arg) == 3 and arg[0] == 'obfuscated':
                    return arg[2]
                return arg

            self.fake_command = [obfuscate(c) for c in self.command]

        if env is not None:
            # avoid mutating the original master.cfg dictionary. Each
            # ShellCommand gets its own copy, any start() methods won't be
            # able to modify the original.
            env = env.copy()

        args = {
            'workdir': workdir,
            'env': env,
            'want_stdout': want_stdout,
            'want_stderr': want_stderr,
            'logfiles': logfiles,
            'timeout': timeout,
            'maxTime': maxTime,
            'max_lines': max_lines,
            'sigtermTime': sigtermTime,
            'usePTY': usePTY,
            'logEnviron': logEnviron,
            'initial_stdin': initialStdin,
        }
        if interruptSignal is not None:
            args['interruptSignal'] = interruptSignal
        super().__init__(
            "shell",
            args,
            collectStdout=collectStdout,
            collectStderr=collectStderr,
            decodeRC=decodeRC,
            stdioLogName=stdioLogName,
        )

    def _start(self):
        if self.args['usePTY'] is None:
            if self.step.workerVersionIsOlderThan("shell", "3.0"):
                # Old worker default of usePTY is to use worker-configuration.
                self.args['usePTY'] = "slave-config"
            else:
                # buildbot-worker doesn't support worker-configured usePTY,
                # and usePTY defaults to False.
                self.args['usePTY'] = False

        self.args['command'] = self.command
        if self.remote_command == "shell":
            # non-ShellCommand worker commands are responsible for doing this
            # fixup themselves
            if self.step.workerVersion("shell", "old") == "old":
                self.args['dir'] = self.args['workdir']
            if self.step.workerVersionIsOlderThan("shell", "2.16"):
                self.args.pop('sigtermTime', None)
        what = f"command '{self.fake_command}' in dir '{self.args['workdir']}'"
        log.msg(what)
        return super()._start()

    def __repr__(self):
        return f"<RemoteShellCommand '{self.fake_command!r}'>"
