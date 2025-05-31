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

from typing import TYPE_CHECKING
from typing import Any
from typing import Callable
from typing import TypeVar

from twisted.internet import defer

from buildbot.util import ComparableMixin
from buildbot.util import subscription
from buildbot.util.eventual import eventually

if TYPE_CHECKING:
    from collections.abc import Mapping

    from twisted.internet.defer import Deferred

    from buildbot.master import BuildMaster
    from buildbot.util.twisted import InlineCallbacksType
    from buildbot.worker.protocols.manager.base import BaseManager
    from buildbot.worker.protocols.manager.base import Registration

    _Connection = TypeVar("_Connection", bound="Connection")


class Listener:
    pass


class UpdateRegistrationListener(Listener):
    def __init__(self, master: BuildMaster) -> None:
        super().__init__()
        self.master = master

        # username : (password, portstr, manager registration)
        self._registrations: dict[str, tuple[str, str, Registration]] = {}

    @defer.inlineCallbacks
    def updateRegistration(
        self,
        username: str,
        password: str,
        portStr: str | None,
    ) -> InlineCallbacksType[Registration | None]:
        # NOTE: this method is only present on the PB and MsgPack protocols; others do not
        # use registrations
        if username in self._registrations:
            currentPassword, currentPortStr, currentReg = self._registrations[username]
        else:
            currentPassword, currentPortStr, currentReg = None, None, None

        iseq = ComparableMixin.isEquivalent(
            currentPassword, password
        ) and ComparableMixin.isEquivalent(currentPortStr, portStr)
        if iseq:
            return currentReg
        if currentReg:
            yield currentReg.unregister()
            del self._registrations[username]

        if portStr is not None and password:
            reg = yield self.get_manager().register(
                portStr, username, password, self._create_connection
            )
            self._registrations[username] = (password, portStr, reg)
            return reg
        return currentReg

    def get_manager(self) -> BaseManager:
        raise NotImplementedError

    def before_connection_setup(self, protocol: object, workerName: str) -> None:
        raise NotImplementedError

    @defer.inlineCallbacks
    def _create_connection(
        self,
        mind: object,
        workerName: str,
    ) -> InlineCallbacksType[_Connection]:
        self.before_connection_setup(mind, workerName)
        worker = self.master.workers.getWorkerByName(workerName)
        conn = self.ConnectionClass(self.master, worker, mind)  # type: ignore[attr-defined]

        # inform the manager, logging any problems in the deferred
        accepted = yield self.master.workers.newConnection(conn, workerName)

        # return the Connection as the perspective
        if accepted:
            return conn
        else:
            # TODO: return something more useful
            raise RuntimeError("rejecting duplicate worker")


class Connection:
    proxies: dict[type, type] = {}

    def __init__(self, name: str) -> None:
        self._disconnectSubs = subscription.SubscriptionPoint(f"disconnections from {name}")

    # This method replace all Impl args by their Proxy protocol implementation
    def createArgsProxies(self, args: Mapping) -> dict:
        newargs = {}
        for k, v in args.items():
            for implclass, proxyclass in self.proxies.items():
                if isinstance(v, implclass):
                    v = proxyclass(v)
            newargs[k] = v
        return newargs

    def get_peer(self) -> str:
        raise NotImplementedError

    # disconnection handling

    def wait_shutdown_started(self) -> Deferred[None]:
        d: Deferred[None] = defer.Deferred()
        self.notifyOnDisconnect(lambda: eventually(d.callback, None))
        return d

    def waitShutdown(self) -> Deferred[None]:
        return self._disconnectSubs.waitForDeliveriesToFinish()

    def notifyOnDisconnect(self, cb: Callable) -> subscription.Subscription:
        return self._disconnectSubs.subscribe(cb)

    def notifyDisconnected(self) -> None:
        self._disconnectSubs.deliver()

    def loseConnection(self) -> None:
        raise NotImplementedError

    # methods to send messages to the worker

    def remotePrint(self, message: str) -> Deferred[None]:
        raise NotImplementedError

    def remoteGetWorkerInfo(self) -> Deferred[Any]:
        raise NotImplementedError

    def remoteSetBuilderList(self, builders: list[tuple[str, str]]) -> Deferred[list[str]]:
        raise NotImplementedError

    def remoteStartCommand(
        self,
        remoteCommand: RemoteCommandImpl,
        builderName: str,
        commandId: str,
        commandName: str,
        args: dict[str, Any],
    ) -> Deferred[None]:
        raise NotImplementedError

    def remoteShutdown(self) -> Deferred[None]:
        raise NotImplementedError

    def remoteStartBuild(self, builderName: str) -> Deferred[None]:
        raise NotImplementedError

    def remoteInterruptCommand(self, builderName: str, commandId: str, why: str) -> Deferred[None]:
        raise NotImplementedError


# RemoteCommand base implementation and base proxy
class RemoteCommandImpl:
    def remote_update(self, updates: list[tuple[dict[str | bytes, Any], int]]) -> Deferred[int]:
        raise NotImplementedError

    def remote_update_msgpack(self, updates: list[tuple[str, Any]]) -> Deferred[None]:
        raise NotImplementedError

    def remote_complete(self, failure: Any | None = None) -> Deferred[None]:
        raise NotImplementedError


# FileWriter base implementation
class FileWriterImpl:
    def remote_write(self, data: str | bytes) -> Deferred[None]:
        raise NotImplementedError

    def remote_utime(self, accessed_modified: tuple[float, float]) -> Deferred[None]:
        raise NotImplementedError

    def remote_unpack(self) -> Deferred[None]:
        raise NotImplementedError

    def remote_close(self) -> Deferred[None]:
        raise NotImplementedError


# FileReader base implementation
class FileReaderImpl:
    def remote_read(self, maxLength: int) -> Deferred[bytes]:
        raise NotImplementedError

    def remote_close(self) -> Deferred[None]:
        raise NotImplementedError
