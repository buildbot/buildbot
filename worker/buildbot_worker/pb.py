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

import os.path
import shutil
import signal
import sys
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable
from typing import cast

from twisted.application import service
from twisted.application.internet import ClientService
from twisted.application.internet import backoffPolicy
from twisted.cred import credentials
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import task
from twisted.internet.endpoints import clientFromString
from twisted.python import log
from twisted.spread import pb

from buildbot_worker import util
from buildbot_worker.base import BotBase
from buildbot_worker.base import ProtocolCommandBase
from buildbot_worker.base import WorkerBase
from buildbot_worker.base import WorkerForBuilderBase
from buildbot_worker.compat import bytes2unicode
from buildbot_worker.compat import unicode2bytes
from buildbot_worker.msgpack import BuildbotWebSocketClientFactory
from buildbot_worker.msgpack import BuildbotWebSocketClientProtocol
from buildbot_worker.msgpack import ProtocolCommandMsgpack
from buildbot_worker.pbutil import AutoLoginPBFactory
from buildbot_worker.pbutil import decode
from buildbot_worker.tunnel import HTTPTunnelEndpoint

if TYPE_CHECKING:
    from twisted.internet.defer import Deferred
    from twisted.internet.interfaces import IDelayedCall
    from twisted.internet.interfaces import IReactorCore
    from twisted.internet.interfaces import IReactorTime
    from twisted.internet.interfaces import IStreamClientEndpoint
    from twisted.python.failure import Failure
    from twisted.spread.pb import RemoteReference

    from buildbot_worker.util.twisted import InlineCallbacksType


class UnknownCommand(pb.Error):
    pass


class ProtocolCommandPb(ProtocolCommandBase):
    def __init__(
        self,
        unicode_encoding: str,
        worker_basedir: str,
        basedir: str,
        buffer_size: int,
        buffer_timeout: int,
        max_line_length: int,
        newline_re: str,
        builder_is_running: int,
        on_command_complete: Callable[[], None],
        on_lost_remote_step: Callable[[RemoteReference], None],
        command: str,
        command_id: str,
        args: dict[str, list[str] | str],
        command_ref: RemoteReference,
    ) -> None:
        self.basedir = basedir
        self.command_ref: RemoteReference | None = command_ref
        ProtocolCommandBase.__init__(
            self,
            unicode_encoding,
            worker_basedir,
            buffer_size,
            buffer_timeout,
            max_line_length,
            newline_re,
            builder_is_running,
            on_command_complete,
            on_lost_remote_step,
            command,
            command_id,
            args,
        )

    def protocol_args_setup(self, command: str, args: dict[str, list[str] | str]) -> None:
        if command == "mkdir":
            assert isinstance(args['dir'], str)
            args['paths'] = [os.path.join(self.basedir, args['dir'])]
            del args['dir']

        if command == "rmdir":
            args['paths'] = []
            if isinstance(args['dir'], list):
                args['paths'] = [os.path.join(self.basedir, dir) for dir in args['dir']]
            else:
                args['paths'] = [os.path.join(self.basedir, args['dir'])]
            del args['dir']

        if command == "cpdir":
            assert isinstance(args['fromdir'], str)
            args['from_path'] = os.path.join(self.basedir, args['fromdir'])
            assert isinstance(args['todir'], str)
            args['to_path'] = os.path.join(self.basedir, args['todir'])
            del args['fromdir']
            del args['todir']

        if command == "stat":
            workdir = args.get('workdir', '')
            assert isinstance(workdir, str)
            assert isinstance(args['file'], str)
            args['path'] = os.path.join(self.basedir, workdir, args['file'])
            del args['file']

        if command == "glob":
            assert isinstance(args['path'], str)
            args['path'] = os.path.join(self.basedir, args['path'])

        if command == "listdir":
            assert isinstance(args['dir'], str)
            args['path'] = os.path.join(self.basedir, args['dir'])
            del args['dir']

        if command == "rmfile":
            assert isinstance(args['path'], str)
            args['path'] = os.path.join(self.basedir, os.path.expanduser(args['path']))

        if command == "shell":
            assert isinstance(args['workdir'], str)
            args['workdir'] = os.path.join(self.basedir, args['workdir'])

        if command == "uploadFile":
            assert isinstance(args['workdir'], str)
            assert isinstance(args['workersrc'], str)
            args["path"] = os.path.join(
                self.basedir, args['workdir'], os.path.expanduser(args['workersrc'])
            )
            del args['workdir']
            del args['workersrc']

        if command == "uploadDirectory":
            assert isinstance(args['workdir'], str)
            assert isinstance(args['workersrc'], str)
            args['path'] = os.path.join(
                self.basedir, args['workdir'], os.path.expanduser(args['workersrc'])
            )
            del args['workdir']
            del args['workersrc']

        if command == "downloadFile":
            assert isinstance(args['workdir'], str)
            assert isinstance(args['workerdest'], str)
            args['path'] = os.path.join(
                self.basedir, args['workdir'], os.path.expanduser(args['workerdest'])
            )
            del args['workdir']
            del args['workerdest']

    def protocol_send_update_message(self, message: list[tuple[str, Any]]) -> None:
        # after self.buffer.append log message is of type:
        # (key, (text, newline_indexes, line_times))
        # only key and text is sent to master in PB protocol
        # if message is not log, simply sends the value (e.g.[("rc", 0)])
        for key, value in message:
            if key in ['stdout', 'stderr', 'header']:
                # the update[1]=0 comes from the leftover 'updateNum', which the
                # master still expects to receive. Provide it to avoid significant
                # interoperability issues between new workers and old masters.
                update = [{key: value[0]}, 0]
            elif key == "log":
                logname, data = value
                update = [{key: (logname, data[0])}, 0]
            else:
                update = [{key: value}, 0]
            updates = [update]
            assert self.command_ref is not None
            d = self.command_ref.callRemote("update", updates)
            d.addErrback(self._ack_failed, "ProtocolCommandBase.send_update")

    def protocol_notify_on_disconnect(self) -> None:
        assert self.command_ref is not None
        self.command_ref.notifyOnDisconnect(self.on_lost_remote_step)

    @defer.inlineCallbacks
    def protocol_complete(self, failure: Failure | None) -> InlineCallbacksType[None]:
        d_update = self.flush_command_output()
        assert self.command_ref is not None
        self.command_ref.dontNotifyOnDisconnect(self.on_lost_remote_step)
        d_complete = self.command_ref.callRemote("complete", failure)

        yield d_update
        yield d_complete

    def protocol_update_upload_file_close(self, writer: RemoteReference) -> Deferred:
        return writer.callRemote("close")

    def protocol_update_upload_file_utime(
        self,
        writer: RemoteReference,
        access_time: float,
        modified_time: float,
    ) -> Deferred:
        return writer.callRemote("utime", (access_time, modified_time))

    def protocol_update_upload_file_write(
        self,
        writer: RemoteReference,
        data: str | bytes,
    ) -> Deferred:
        return writer.callRemote('write', data)

    def protocol_update_upload_directory(self, writer: RemoteReference) -> Deferred:
        return writer.callRemote("unpack")

    def protocol_update_upload_directory_write(
        self,
        writer: RemoteReference,
        data: str | bytes,
    ) -> Deferred:
        return writer.callRemote('write', data)

    def protocol_update_read_file_close(self, reader: RemoteReference) -> Deferred:
        return reader.callRemote('close')

    def protocol_update_read_file(self, reader: RemoteReference, length: int) -> Deferred:
        return reader.callRemote('read', length)


class WorkerForBuilderPbLike(WorkerForBuilderBase):
    ProtocolCommand = ProtocolCommandPb

    """This is the local representation of a single Builder: it handles a
    single kind of build (like an all-warnings build). It has a name and a
    home directory. The rest of its behavior is determined by the master.
    """

    stopCommandOnShutdown = True

    # remote is a ref to the Builder object on the master side, and is set
    # when they attach. We use it to detect when the connection to the master
    # is severed.
    remote: RemoteReference | None = None

    def __init__(
        self,
        name: str,
        unicode_encoding: str,
        buffer_size: int,
        buffer_timeout: int,
        max_line_length: int,
        newline_re: str,
    ) -> None:
        # service.Service.__init__(self) # Service has no __init__ method
        self.setName(name)
        self.unicode_encoding = unicode_encoding
        self.buffer_size = buffer_size
        self.buffer_timeout = buffer_timeout
        self.max_line_length = max_line_length
        self.newline_re = newline_re
        self.protocol_command: ProtocolCommandPb | None = None
        self.builddir: str | None = None

    def __repr__(self) -> str:
        return f"<WorkerForBuilder '{self.name}' at {id(self)}>"

    @defer.inlineCallbacks
    def setServiceParent(self, parent: service.Service) -> InlineCallbacksType[None]:
        yield service.Service.setServiceParent(self, parent)
        self.bot = self.parent
        # note that self.parent will go away when the buildmaster's config
        # file changes and this Builder is removed (possibly because it has
        # been changed, so the Builder will be re-added again in a moment).
        # This may occur during a build, while a step is running.

    def setBuilddir(self, builddir: str) -> None:
        assert self.parent
        self.builddir = builddir
        self.basedir = os.path.join(bytes2unicode(self.bot.basedir), bytes2unicode(self.builddir))
        if not os.path.isdir(self.basedir):
            os.makedirs(self.basedir)

    def startService(self) -> None:
        service.Service.startService(self)
        if self.protocol_command:
            self.protocol_command.builder_is_running = True

    def stopService(self) -> None:
        service.Service.stopService(self)
        if self.protocol_command:
            self.protocol_command.builder_is_running = False
        if self.stopCommandOnShutdown:
            self.stopCommand()

    def remote_setMaster(self, remote: RemoteReference) -> None:
        self.remote = remote
        self.remote.notifyOnDisconnect(self.lostRemote)

    def remote_print(self, message: str) -> None:
        log.msg(f"WorkerForBuilder.remote_print({self.name}): message from master: {message}")

    def lostRemote(self, remote: RemoteReference) -> None:
        log.msg("lost remote")
        self.remote = None

    def lostRemoteStep(self, remotestep: RemoteReference) -> None:
        log.msg("lost remote step")
        if self.protocol_command:
            self.protocol_command.command_ref = None
        if self.stopCommandOnShutdown:
            self.stopCommand()

    # the following are Commands that can be invoked by the master-side
    # Builder
    def remote_startBuild(self) -> None:
        """This is invoked before the first step of any new build is run.  It
        doesn't do much, but masters call it so it's still here."""

    def remote_startCommand(
        self,
        command_ref: RemoteReference,
        command_id: str,
        command: str,
        args: dict[str, list[str] | str],
    ) -> None:
        """
        This gets invoked by L{buildbot.process.step.RemoteCommand.start}, as
        part of various master-side BuildSteps, to start various commands
        that actually do the build. I return nothing. Eventually I will call
        .commandComplete() to notify the master-side RemoteCommand that I'm
        done.
        """
        command_id = decode(command_id)
        command = decode(command)
        args = decode(args)

        if self.protocol_command:
            log.msg("leftover command, dropping it")
            self.stopCommand()

        def on_command_complete() -> None:
            self.protocol_command = None

        assert self.bot is not None
        self.protocol_command = self.ProtocolCommand(
            self.unicode_encoding,
            self.bot.basedir,
            self.basedir,
            self.buffer_size,
            self.buffer_timeout,
            self.max_line_length,
            self.newline_re,
            self.running,
            on_command_complete,
            self.lostRemoteStep,
            command,
            command_id,
            args,
            command_ref,
        )

        log.msg(f"(command {command_id}): startCommand:{command}")
        self.protocol_command.protocol_notify_on_disconnect()
        d = self.protocol_command.command.doStart()
        d.addCallback(lambda res: None)
        d.addBoth(self.protocol_command.command_complete)
        return None

    def remote_interruptCommand(self, command_id: str, why: str) -> None:
        """Halt the current step."""
        log.msg(f"(command {command_id}): asked to interrupt: reason {why}")
        if not self.protocol_command:
            # TODO: just log it, a race could result in their interrupting a
            # command that wasn't actually running
            log.msg(" .. but none was running")
            return
        self.protocol_command.command.doInterrupt()

    def stopCommand(self) -> None:
        """Make any currently-running command die, with no further status
        output. This is used when the worker is shutting down or the
        connection to the master has been lost. Interrupt the command,
        silence it, and then forget about it."""
        if not self.protocol_command:
            return
        log.msg(f"stopCommand: halting current command {self.protocol_command.command}")
        self.protocol_command.command.doInterrupt()
        self.protocol_command = None


class WorkerForBuilderPb(WorkerForBuilderPbLike, pb.Referenceable):
    pass


class BotPbLike(BotBase):
    WorkerForBuilder = WorkerForBuilderPbLike

    @defer.inlineCallbacks
    def remote_setBuilderList(
        self,
        wanted: list[tuple[str, str]],
    ) -> InlineCallbacksType[dict[str, WorkerForBuilderPbLike]]:
        retval = {}
        wanted_names = {name for (name, builddir) in wanted}
        wanted_dirs = {builddir for (name, builddir) in wanted}
        wanted_dirs.add('info')
        for name, builddir in wanted:
            b = self.builders.get(name, None)
            if b:
                assert isinstance(b, WorkerForBuilderPbLike)
                if b.builddir != builddir:
                    log.msg(f"changing builddir for builder {name} from {b.builddir} to {builddir}")
                    b.setBuilddir(builddir)
            else:
                b = self.WorkerForBuilder(
                    name,
                    self.unicode_encoding,
                    self.buffer_size,
                    self.buffer_timeout,
                    self.max_line_length,
                    self.newline_re,
                )
                b.setServiceParent(self)
                b.setBuilddir(builddir)
                self.builders[name] = b
            retval[name] = b

        # disown any builders no longer desired
        to_remove = list(set(self.builders.keys()) - wanted_names)
        if to_remove:
            yield defer.gatherResults(
                [
                    defer.maybeDeferred(self.builders[name].disownServiceParent)
                    for name in to_remove
                ],
                consumeErrors=True,
            )

        # and *then* remove them from the builder list
        for name in to_remove:
            del self.builders[name]

        # finally warn about any leftover dirs
        for dir in os.listdir(self.basedir):
            if os.path.isdir(os.path.join(self.basedir, dir)):
                if dir not in wanted_dirs:
                    if self.delete_leftover_dirs:
                        log.msg(
                            f"Deleting directory '{dir}' that is not being used by the buildmaster"
                        )
                        try:
                            shutil.rmtree(dir)
                        except OSError as e:
                            log.msg(f"Cannot remove directory '{dir}': {e}")
                    else:
                        log.msg(
                            f"I have a leftover directory '{dir}' that is not "
                            "being used by the buildmaster: you can delete "
                            "it now"
                        )

        return retval


class BotPb(BotPbLike, pb.Referenceable):
    WorkerForBuilder = WorkerForBuilderPb


class BotMsgpack(BotBase):
    def __init__(
        self,
        basedir: str,
        unicode_encoding: None = None,
        delete_leftover_dirs: bool = False,
    ) -> None:
        BotBase.__init__(
            self,
            basedir,
            unicode_encoding=unicode_encoding,
            delete_leftover_dirs=delete_leftover_dirs,
        )
        self.protocol_commands: dict[str, ProtocolCommandMsgpack] = {}

    @defer.inlineCallbacks
    def startService(self) -> InlineCallbacksType[None]:
        yield BotBase.startService(self)

    @defer.inlineCallbacks
    def stopService(self) -> InlineCallbacksType[None]:
        yield BotBase.stopService(self)

        # Make any currently-running command die, with no further status
        # output. This is used when the worker is shutting down or the
        # connection to the master has been lost.
        # FIXME: missing `.values()` here
        for protocol_command in self.protocol_commands:
            protocol_command.builder_is_running = False  # type: ignore[attr-defined]
            log.msg(f"stopCommand: halting current command {protocol_command.command}")  # type: ignore[attr-defined]
            protocol_command.command.doInterrupt()  # type: ignore[attr-defined]
        self.protocol_commands = {}

    def calculate_basedir(self, builddir: str | bytes) -> str:
        return os.path.join(bytes2unicode(self.basedir), bytes2unicode(builddir))

    def create_dirs(self, basedir: str | bytes) -> None:
        if not os.path.isdir(basedir):
            os.makedirs(basedir)

    def start_command(
        self,
        protocol: BuildbotWebSocketClientProtocol,
        command_id: str,
        command: str,
        args: dict[str, list[str] | str],
    ) -> None:
        """
        This gets invoked by L{buildbot.process.step.RemoteCommand.start}, as
        part of various master-side BuildSteps, to start various commands
        that actually do the build. I return nothing. Eventually I will call
        .commandComplete() to notify the master-side RemoteCommand that I'm
        done.
        """
        command = decode(command)
        args = decode(args)

        def on_command_complete() -> None:
            del self.protocol_commands[command_id]

        protocol_command = ProtocolCommandMsgpack(
            self.unicode_encoding,
            self.basedir,
            self.buffer_size,
            self.buffer_timeout,
            self.max_line_length,
            self.newline_re,
            self.running,
            on_command_complete,
            protocol,
            command_id,
            command,
            args,
        )

        self.protocol_commands[command_id] = protocol_command

        log.msg(f" startCommand:{command} [id {command_id}]")
        protocol_command.protocol_notify_on_disconnect()
        d = protocol_command.command.doStart()
        d.addCallback(lambda res: None)
        d.addBoth(protocol_command.command_complete)
        return None

    def interrupt_command(self, command_id: str, why: str) -> None:
        """Halt the current step."""
        log.msg(f"asked to interrupt current command: {why}")

        if command_id not in self.protocol_commands:
            # TODO: just log it, a race could result in their interrupting a
            # command that wasn't actually running
            log.msg(" .. but none was running")
            return
        d = self.protocol_commands[command_id].flush_command_output()
        d.addErrback(
            self.protocol_commands[command_id]._ack_failed,
            "ProtocolCommandMsgpack.flush_command_output",
        )
        self.protocol_commands[command_id].command.doInterrupt()


class BotFactory(AutoLoginPBFactory):
    """The protocol factory for the worker.

    This class implements the optional applicative keepalives, on top of
    AutoLoginPBFactory.

    'keepaliveInterval' serves two purposes. The first is to keep the
    connection alive: it guarantees that there will be at least some
    traffic once every 'keepaliveInterval' seconds, which may help keep an
    interposed NAT gateway from dropping the address mapping because it
    thinks the connection has been abandoned.  This also gives the operating
    system a chance to notice that the master has gone away, and inform us
    of such (although this could take several minutes).

    buildmaster host, port and maxDelay are accepted for backwards
    compatibility only.
    """

    keepaliveTimer: IDelayedCall | None = None
    perspective: RemoteReference | None = None

    _reactor = cast("IReactorTime", reactor)

    def __init__(
        self,
        buildmaster_host: str | None,
        port: int | None,
        keepaliveInterval: float | None,  # None = do not use keepalives
        maxDelay: int | None,
        retryPolicy: Callable[[int], float] | None = None,
    ) -> None:
        AutoLoginPBFactory.__init__(self, retryPolicy=retryPolicy)
        self.keepaliveInterval = keepaliveInterval
        self.keepalive_lock = defer.DeferredLock()
        self._shutting_down = False

        # notified when shutdown is complete.
        self._shutdown_notifier: util.Notifier[None] | None = util.Notifier()
        self._active_keepalives = 0

        self.currentKeepaliveWaiter: Deferred[Any] | None = None

    def gotPerspective(self, perspective: RemoteReference) -> None:
        log.msg("Connected to buildmaster; worker is ready")
        AutoLoginPBFactory.gotPerspective(self, perspective)
        self.perspective = perspective
        try:
            perspective.broker.transport.setTcpKeepAlive(1)
        except Exception:
            log.msg("unable to set SO_KEEPALIVE")
            if not self.keepaliveInterval:
                self.keepaliveInterval = 10 * 60
        if self.keepaliveInterval:
            log.msg(f"sending application-level keepalives every {self.keepaliveInterval} seconds")
            self.startTimers()

    def startTimers(self) -> None:
        assert self.keepaliveInterval
        assert not self.keepaliveTimer

        @defer.inlineCallbacks
        def doKeepalive() -> InlineCallbacksType[None]:
            self._active_keepalives += 1
            self.keepaliveTimer = None
            self.startTimers()

            yield self.keepalive_lock.acquire()
            self.currentKeepaliveWaiter = defer.Deferred()

            # Send the keepalive request.  If an error occurs
            # was already dropped, so just log and ignore.
            log.msg("sending app-level keepalive")
            try:
                assert self.perspective is not None
                details = yield self.perspective.callRemote("keepalive")
                log.msg("Master replied to keepalive, everything's fine")
                self.currentKeepaliveWaiter.callback(details)
                self.currentKeepaliveWaiter = None
            except (pb.PBConnectionLost, pb.DeadReferenceError):
                log.msg("connection already shut down when attempting keepalive")
            except Exception as e:
                log.err(e, "error sending keepalive")
            finally:
                self.keepalive_lock.release()
                self._active_keepalives -= 1
                self._checkNotifyShutdown()

        assert self.keepaliveInterval is not None
        self.keepaliveTimer = self._reactor.callLater(self.keepaliveInterval, doKeepalive)

    def _checkNotifyShutdown(self) -> None:
        if (
            self._active_keepalives == 0
            and self._shutting_down
            and self._shutdown_notifier is not None
        ):
            self._shutdown_notifier.notify(None)
            self._shutdown_notifier = None

    def stopTimers(self) -> None:
        self._shutting_down = True

        if self.keepaliveTimer:
            # by cancelling the timer we are guaranteed that doKeepalive() won't be called again,
            # as there's no interruption point between doKeepalive() beginning and call to
            # startTimers()
            self.keepaliveTimer.cancel()
            self.keepaliveTimer = None

        self._checkNotifyShutdown()

    def stopFactory(self) -> None:
        self.stopTimers()
        AutoLoginPBFactory.stopFactory(self)

    @defer.inlineCallbacks
    def waitForCompleteShutdown(self) -> InlineCallbacksType[None]:
        # This function waits for a complete shutdown to happen. It's fired when all keepalives
        # have been finished and there are no pending ones.
        if self._shutdown_notifier is not None:
            yield self._shutdown_notifier.wait()


class Worker(WorkerBase):
    """The service class to be instantiated from buildbot.tac

    to just pass a connection string, set buildmaster_host and
    port to None, and use connection_string.

    maxdelay is deprecated in favor of using twisted's backoffPolicy.
    """

    def __init__(
        self,
        buildmaster_host: str | None,
        port: int | None,
        name: str,
        passwd: str,
        basedir: str,
        keepalive: float | None,
        keepaliveTimeout: int | None = None,
        umask: int | None = None,
        maxdelay: int | None = None,
        numcpus: int | str | None = None,
        unicode_encoding: str | None = None,
        protocol: str = 'pb',
        useTls: bool = False,
        allow_shutdown: str | None = None,
        maxRetries: int | None = None,
        connection_string: str | None = None,
        path: None = None,
        delete_leftover_dirs: bool = False,
        proxy_connection_string: str | None = None,
    ) -> None:
        assert connection_string is None or (buildmaster_host, port) == (
            None,
            None,
        ), "If you want to supply a connection string, then set host and port to None"

        bot_class: type[BotBase]
        if protocol == 'pb':
            bot_class = BotPb
        elif protocol == 'msgpack_experimental_v7':
            bot_class = BotMsgpack
        else:
            raise ValueError(f'Unknown protocol {protocol}')

        WorkerBase.__init__(
            self,
            name,
            basedir,
            bot_class,
            umask=umask,
            unicode_encoding=unicode_encoding,
            delete_leftover_dirs=delete_leftover_dirs,
        )
        if keepalive == 0:
            keepalive = None

        name_b = unicode2bytes(name, self.bot.unicode_encoding)
        passwd_b = unicode2bytes(passwd, self.bot.unicode_encoding)

        self.numcpus = numcpus
        self.shutdown_loop: task.LoopingCall | None = None

        if allow_shutdown == 'signal':
            if not hasattr(signal, 'SIGHUP'):
                raise ValueError("Can't install signal handler")
        elif allow_shutdown == 'file':
            self.shutdown_file = os.path.join(basedir, 'shutdown.stamp')
            self.shutdown_mtime = 0.0

        self.allow_shutdown = allow_shutdown

        def policy(attempt: int) -> float:
            if maxRetries and attempt >= maxRetries:
                cast("IReactorCore", reactor).stop()
            return backoffPolicy()(attempt)

        self.bf: BotFactory | BuildbotWebSocketClientFactory
        if protocol == 'pb':
            bf = self.bf = BotFactory(
                buildmaster_host,
                port,
                keepalive,
                maxdelay,
                retryPolicy=policy,
            )
            assert self.bot is None or isinstance(self.bot, (BotPb))
            bf.startLogin(
                credentials.UsernamePassword(
                    name_b,
                    passwd_b,
                ),
                client=self.bot,
            )
        elif protocol == 'msgpack_experimental_v7':
            if connection_string is None:
                ws_conn_string = f"ws://{buildmaster_host}:{port}"
            else:
                ws_conn_string = util.twisted_connection_string_to_ws_url(connection_string)

            if path is not None:
                if not path.startswith('/'):
                    ws_conn_string += '/'
                ws_conn_string += path

            bf = self.bf = BuildbotWebSocketClientFactory(ws_conn_string)
            bf.protocol = BuildbotWebSocketClientProtocol
            self.bf.buildbot_bot = self.bot
            self.bf.name = name_b
            self.bf.password = passwd_b
        else:
            raise ValueError(f'Unknown protocol {protocol}')

        def get_connection_string(host: str, port: str | int) -> str:
            if useTls:
                connection_type = 'tls'
            else:
                connection_type = 'tcp'

            return '{}:host={}:port={}'.format(
                connection_type,
                host.replace(':', r'\:'),  # escape ipv6 addresses
                port,
            )

        assert not (proxy_connection_string and connection_string), (
            "If you want to use HTTP tunneling, then supply build master "
            "host and port rather than a connection string"
        )

        if proxy_connection_string:
            log.msg("Using HTTP tunnel to connect through proxy")
            proxy_endpoint = clientFromString(reactor, proxy_connection_string)
            assert isinstance(buildmaster_host, str)
            assert isinstance(port, int)
            endpoint: IStreamClientEndpoint = HTTPTunnelEndpoint(
                buildmaster_host,
                port,
                cast("IStreamClientEndpoint", proxy_endpoint),
            )
            if useTls:
                from twisted.internet.endpoints import wrapClientTLS
                from twisted.internet.ssl import optionsForClientTLS

                contextFactory = optionsForClientTLS(hostname=buildmaster_host)
                endpoint = wrapClientTLS(contextFactory, endpoint)
        else:
            if connection_string is None:
                assert isinstance(buildmaster_host, str)
                assert isinstance(port, (int, str))
                connection_string = get_connection_string(buildmaster_host, port)
            endpoint = clientFromString(reactor, connection_string)

        pb_service = ClientService(endpoint, bf, retryPolicy=policy)
        self.addService(pb_service)

    def startService(self) -> None:
        WorkerBase.startService(self)

        if self.allow_shutdown == 'signal':
            if sys.platform != "win32":
                log.msg("Setting up SIGHUP handler to initiate shutdown")
                signal.signal(signal.SIGHUP, self._handleSIGHUP)
            else:
                raise ValueError(
                    f"Shutdown method 'signal' is not available on this platform ({sys.platform})"
                )
        elif self.allow_shutdown == 'file':
            log.msg(f"Watching {self.shutdown_file}'s mtime to initiate shutdown")
            if os.path.exists(self.shutdown_file):
                self.shutdown_mtime = os.path.getmtime(self.shutdown_file)
            self.shutdown_loop = loop = task.LoopingCall(self._checkShutdownFile)
            loop.start(interval=10)

    @defer.inlineCallbacks
    def stopService(self) -> InlineCallbacksType[None]:
        if self.shutdown_loop:
            self.shutdown_loop.stop()
            self.shutdown_loop = None
        yield WorkerBase.stopService(self)
        yield self.bf.waitForCompleteShutdown()

    def _handleSIGHUP(self, *args: Any) -> Deferred[Any] | None:
        log.msg("Initiating shutdown because we got SIGHUP")
        return self.gracefulShutdown()

    def _checkShutdownFile(self) -> None:
        if (
            os.path.exists(self.shutdown_file)
            and os.path.getmtime(self.shutdown_file) > self.shutdown_mtime
        ):
            log.msg(f"Initiating shutdown because {self.shutdown_file} was touched")
            self.gracefulShutdown()

            # In case the shutdown fails, update our mtime so we don't keep
            # trying to shutdown over and over again.
            # We do want to be able to try again later if the master is
            # restarted, so we'll keep monitoring the mtime.
            self.shutdown_mtime = os.path.getmtime(self.shutdown_file)

    def gracefulShutdown(self) -> Deferred[Any] | None:
        """Start shutting down"""
        if not self.bf.perspective:
            log.msg("No active connection, shutting down NOW")
            cast("IReactorCore", reactor).stop()
            return None

        log.msg("Telling the master we want to shutdown after any running builds are finished")
        d = self.bf.perspective.callRemote("shutdown")

        def _shutdownfailed(err: Failure) -> None:
            if err.check(AttributeError):
                log.msg(
                    "Master does not support worker initiated shutdown.  Upgrade master to 0.8.3"
                    "or later to use this feature."
                )
            else:
                log.msg('callRemote("shutdown") failed')
                log.err(err)

        d.addErrback(_shutdownfailed)
        return d
