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

from twisted.internet import defer

from buildbot.worker.protocols import base

if TYPE_CHECKING:
    from twisted.internet.defer import Deferred

    from buildbot.test.fake.worker import FakeWorker
    from buildbot.worker.base import AbstractWorker


class FakeTrivialConnection(base.Connection):
    info: dict[str, Any] = {}

    def __init__(self) -> None:
        super().__init__("Fake")

    def loseConnection(self) -> None:
        self.notifyDisconnected()

    def remoteSetBuilderList(self, builders: list[tuple[str, str]]) -> Deferred[list[str]]:
        return defer.succeed(None)  # type: ignore[arg-type]


class FakeConnection(base.Connection):
    def __init__(self, worker: AbstractWorker | FakeWorker) -> None:
        assert isinstance(worker.workername, str), type(worker.workername)
        super().__init__(worker.workername)
        self._connected = True
        self.remoteCalls: list[tuple[Any, ...]] = []
        # TODO: looks fishy, need to check usage
        self.builders: dict[tuple[str, str], bool] = {}  # { name : isBusy }

        # users of the fake can add to this as desired
        self.info = {
            'worker_commands': [],
            'version': '0.9.0',
            'basedir': '/w',
            'system': 'nt',
        }

    def loseConnection(self) -> None:
        self.notifyDisconnected()

    def remotePrint(self, message: str) -> Deferred[None]:
        self.remoteCalls.append(('remotePrint', message))
        return defer.succeed(None)

    def remoteGetWorkerInfo(self) -> Deferred[Any]:
        self.remoteCalls.append(('remoteGetWorkerInfo',))
        return defer.succeed(self.info)

    def remoteSetBuilderList(self, builders: list[tuple[str, str]]) -> Deferred[list[str]]:
        self.remoteCalls.append(('remoteSetBuilderList', builders[:]))
        self.builders = dict((b, False) for b in builders)
        return defer.succeed(None)  # type: ignore[arg-type]

    def remoteStartCommand(
        self,
        remoteCommand: base.RemoteCommandImpl,
        builderName: str,
        commandId: str,
        commandName: str,
        args: dict[str, Any],
    ) -> Deferred:
        self.remoteCalls.append((
            'remoteStartCommand',
            remoteCommand,
            builderName,
            commandId,
            commandName,
            args,
        ))
        return defer.succeed(None)

    def remoteShutdown(self) -> Deferred[None]:
        self.remoteCalls.append(('remoteShutdown',))
        return defer.succeed(None)

    def remoteStartBuild(self, builderName: str) -> Deferred[None]:
        self.remoteCalls.append(('remoteStartBuild', builderName))
        return defer.succeed(None)

    def remoteInterruptCommand(self, builderName: str, commandId: str, why: str) -> Deferred:
        self.remoteCalls.append(('remoteInterruptCommand', builderName, commandId, why))
        return defer.succeed(None)

    def get_peer(self) -> str:
        if self._connected:
            return "fake_peer"
        return None  # type: ignore[return-value]
