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

import contextlib
from typing import TYPE_CHECKING
from typing import Any

from twisted.internet import defer
from twisted.python import log
from twisted.spread import pb
from twisted.spread.pb import RemoteReference

from buildbot.pbutil import decode
from buildbot.util import deferwaiter
from buildbot.worker.protocols import base

if TYPE_CHECKING:
    from collections.abc import Generator

    from twisted.internet.defer import Deferred
    from twisted.python.failure import Failure

    from buildbot.master import BuildMaster
    from buildbot.util.twisted import InlineCallbacksType
    from buildbot.worker.base import Worker
    from buildbot.worker.protocols.base import RemoteCommandImpl
    from buildbot.worker.protocols.manager.pb import PBManager
    from buildbot_worker.base import WorkerForBuilderBase


class Listener(base.UpdateRegistrationListener):
    name = "pbListener"

    def __init__(self, master: BuildMaster) -> None:
        super().__init__(master=master)
        self.ConnectionClass = Connection

    def get_manager(self) -> PBManager:
        return self.master.pbmanager

    def before_connection_setup(self, mind: object, workerName: str) -> None:
        assert isinstance(mind, RemoteReference), type(mind)
        log.msg(f"worker '{workerName}' attaching from {mind.broker.transport.getPeer()}")
        try:
            mind.broker.transport.setTcpKeepAlive(1)
        except Exception:
            log.err("Can't set TcpKeepAlive")


class ReferenceableProxy(pb.Referenceable):
    ImplClass: type

    def __init__(self, impl: object) -> None:
        assert isinstance(impl, self.ImplClass)
        self.impl = impl

    def __getattr__(self, name: str) -> Any:
        return getattr(self.impl, name)


# Proxy are just ReferenceableProxy to the Impl classes
class RemoteCommand(ReferenceableProxy):
    ImplClass = base.RemoteCommandImpl


class FileReaderProxy(ReferenceableProxy):
    ImplClass = base.FileReaderImpl


class FileWriterProxy(ReferenceableProxy):
    ImplClass = base.FileWriterImpl


class _NoSuchMethod(Exception):
    """Rewrapped pb.NoSuchMethod remote exception"""


@contextlib.contextmanager
def _wrapRemoteException() -> Generator[None, Any, None]:
    try:
        yield
    except pb.RemoteError as e:
        if e.remoteType in (
            b'twisted.spread.flavors.NoSuchMethod',
            'twisted.spread.flavors.NoSuchMethod',
        ):
            raise _NoSuchMethod(e) from e
        raise


class Connection(base.Connection, pb.Avatar):
    proxies: dict[type, type[ReferenceableProxy]] = {
        base.FileWriterImpl: FileWriterProxy,
        base.FileReaderImpl: FileReaderProxy,
    }
    # TODO: configure keepalive_interval in
    # c['protocols']['pb']['keepalive_interval']
    keepalive_timer: None = None
    keepalive_interval = 3600
    info: Any = None

    def __init__(self, master: BuildMaster, worker: Worker, mind: RemoteReference) -> None:
        assert worker.workername is not None
        super().__init__(worker.workername)
        self.master = master
        self.worker = worker
        self.mind: RemoteReference | None = mind
        self._keepalive_waiter: deferwaiter.DeferWaiter[None] = deferwaiter.DeferWaiter()
        self._keepalive_action_handler = deferwaiter.RepeatedActionHandler(
            master.reactor,
            self._keepalive_waiter,
            self.keepalive_interval,
            self._do_keepalive,
        )

        self.builders: dict[str, WorkerForBuilderBase]

    # methods called by the PBManager

    @defer.inlineCallbacks
    def attached(self, mind: RemoteReference) -> InlineCallbacksType[Connection]:
        self.startKeepaliveTimer()
        self.notifyOnDisconnect(self._stop_keepalive_timer)
        # pbmanager calls perspective.attached; pass this along to the
        # worker
        yield self.worker.attached(self)
        # and then return a reference to the avatar
        return self

    def detached(self, mind: RemoteReference) -> None:
        self.stopKeepaliveTimer()
        self.mind = None
        self.notifyDisconnected()

    # disconnection handling
    @defer.inlineCallbacks
    def _stop_keepalive_timer(self) -> InlineCallbacksType[None]:
        self.stopKeepaliveTimer()
        yield self._keepalive_waiter.wait()

    def loseConnection(self) -> None:
        self.stopKeepaliveTimer()
        assert self.mind is not None
        self.mind.broker.transport.abortConnection()

    # keepalive handling

    def _do_keepalive(self) -> Deferred[None]:
        assert self.mind is not None
        return self.mind.callRemote('print', message="keepalive")

    def stopKeepaliveTimer(self) -> None:
        self._keepalive_action_handler.stop()

    def startKeepaliveTimer(self) -> None:
        assert self.keepalive_interval
        self._keepalive_action_handler.start()

    # methods to send messages to the worker

    def remotePrint(self, message: str) -> Deferred[None]:
        assert self.mind is not None
        return self.mind.callRemote('print', message=message)

    @defer.inlineCallbacks
    def remoteGetWorkerInfo(self) -> InlineCallbacksType[Any]:
        try:
            with _wrapRemoteException():
                # Try to call buildbot-worker method.
                assert self.mind is not None
                info = yield self.mind.callRemote('getWorkerInfo')
            return decode(info)
        except _NoSuchMethod:
            yield self.remotePrint(
                "buildbot-slave detected, failing back to deprecated buildslave API. "
                "(Ignoring missing getWorkerInfo method.)"
            )
            info = {}

            # Probably this is deprecated buildslave.
            log.msg(
                "Worker.getWorkerInfo is unavailable - falling back to deprecated buildslave API"
            )

            try:
                with _wrapRemoteException():
                    assert self.mind is not None
                    info = yield self.mind.callRemote('getSlaveInfo')
            except _NoSuchMethod:
                log.msg("Worker.getSlaveInfo is unavailable - ignoring")

            # newer workers send all info in one command
            if "slave_commands" in info:
                assert "worker_commands" not in info
                info["worker_commands"] = info.pop("slave_commands")
                return info

            # Old version buildslave - need to retrieve list of supported
            # commands and version using separate requests.
            try:
                with _wrapRemoteException():
                    assert self.mind is not None
                    info["worker_commands"] = yield self.mind.callRemote('getCommands')
            except _NoSuchMethod:
                log.msg("Worker.getCommands is unavailable - ignoring")

            try:
                with _wrapRemoteException():
                    assert self.mind is not None
                    info["version"] = yield self.mind.callRemote('getVersion')
            except _NoSuchMethod:
                log.msg("Worker.getVersion is unavailable - ignoring")

            return decode(info)

    @defer.inlineCallbacks
    def remoteSetBuilderList(
        self,
        builders: list[tuple[str, str]],
    ) -> InlineCallbacksType[list[str]]:
        assert self.mind is not None
        builders = yield self.mind.callRemote('setBuilderList', builders)
        self.builders = builders  # type: ignore[assignment]
        return builders  # type: ignore[return-value]

    def remoteStartCommand(
        self,
        remoteCommand: RemoteCommandImpl,
        builderName: str,
        commandId: str | None,
        commandName: str,
        args: dict[str, Any],
    ) -> Deferred:
        workerforbuilder = self.builders.get(builderName)
        remoteCommand = RemoteCommand(remoteCommand)  # type: ignore[assignment]
        args = self.createArgsProxies(args)
        assert workerforbuilder is not None
        return workerforbuilder.callRemote(  # type: ignore[attr-defined]
            'startCommand', remoteCommand, commandId, commandName, args
        )

    @defer.inlineCallbacks
    def remoteShutdown(self) -> InlineCallbacksType[None]:
        # First, try the "new" way - calling our own remote's shutdown
        # method. The method was only added in 0.8.3, so ignore NoSuchMethod
        # failures.
        @defer.inlineCallbacks
        def new_way() -> InlineCallbacksType[bool]:
            try:
                with _wrapRemoteException():
                    assert self.mind is not None
                    yield self.mind.callRemote('shutdown')
                    # successful shutdown request
                    return True
            except _NoSuchMethod:
                # fall through to the old way
                return False

            except pb.PBConnectionLost:
                # the worker is gone, so call it finished
                return True

        if (yield new_way()):
            return  # done!

        # Now, the old way. Look for a builder with a remote reference to the
        # client side worker. If we can find one, then call "shutdown" on the
        # remote builder, which will cause the worker buildbot process to exit.
        def old_way() -> Deferred[None]:
            d = None
            for b in self.worker.workerforbuilders.values():
                if b.remote:
                    d = b.mind.callRemote("shutdown")
                    break

            if d:
                name = self.worker.workername
                log.msg(f"Shutting down (old) worker: {name}")
                # The remote shutdown call will not complete successfully since
                # the buildbot process exits almost immediately after getting
                # the shutdown request.
                # Here we look at the reason why the remote call failed, and if
                # it's because the connection was lost, that means the worker
                # shutdown as expected.

                @d.addErrback
                def _errback(why: Failure) -> None:
                    if why.check(pb.PBConnectionLost):
                        log.msg(f"Lost connection to {name}")
                    else:
                        log.err(f"Unexpected error when trying to shutdown {name}")

                return d
            log.err("Couldn't find remote builder to shut down worker")
            return defer.succeed(None)

        yield old_way()

    def remoteStartBuild(self, builderName: str) -> Deferred[None]:
        workerforbuilder = self.builders.get(builderName)
        assert workerforbuilder is not None
        return workerforbuilder.callRemote('startBuild')  # type: ignore[attr-defined]

    def remoteInterruptCommand(self, builderName: str, commandId: str, why: str) -> Deferred:
        workerforbuilder = self.builders.get(builderName)
        assert workerforbuilder is not None
        return defer.maybeDeferred(  # type: ignore[call-overload]
            workerforbuilder.callRemote,  # type: ignore[attr-defined]
            "interruptCommand",
            commandId,
            why,
        )

    # perspective methods called by the worker

    def perspective_keepalive(self) -> None:
        self.worker.messageReceivedFromWorker()

    def perspective_shutdown(self) -> None:
        self.worker.messageReceivedFromWorker()
        self.worker.shutdownRequested()

    def get_peer(self) -> str:
        assert self.mind is not None
        p = self.mind.broker.transport.getPeer()
        return f"{p.host}:{p.port}"
