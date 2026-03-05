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

from typing import Any

from twisted.internet import defer

from buildbot.util import service


class FakeWorkerManager(service.AsyncMultiService):
    def __init__(self) -> None:
        super().__init__()
        self.setName('workers')

        # WorkerRegistration instances keyed by worker name
        self.registrations: dict[str, FakeWorkerRegistration] = {}

        # connection objects keyed by worker name
        self.connections: dict[str, Any] = {}

        # self.workers contains a ready Worker instance for each
        # potential worker, i.e. all the ones listed in the config file.
        # If the worker is connected, self.workers[workername].worker will
        # contain a RemoteReference to their Bot instance. If it is not
        # connected, that attribute will hold None.
        self.workers: dict[str, Any] = {}

    def register(self, worker: Any) -> defer.Deferred[FakeWorkerRegistration]:
        workerName = worker.workername
        reg = FakeWorkerRegistration(worker)
        self.registrations[workerName] = reg
        return defer.succeed(reg)

    def _unregister(self, registration: FakeWorkerRegistration) -> None:
        del self.registrations[registration.worker.workername]

    def getWorkerByName(self, workerName: str) -> Any:
        return self.registrations[workerName].worker

    def newConnection(self, conn: Any, workerName: str) -> defer.Deferred[bool]:
        assert workerName not in self.connections
        self.connections[workerName] = conn
        conn.info = {}
        return defer.succeed(True)


class FakeWorkerRegistration:
    def __init__(self, worker: Any) -> None:
        self.updates: list[str] = []
        self.unregistered = False
        self.worker = worker

    def getPBPort(self) -> int:
        return 1234

    def unregister(self) -> defer.Deferred[None]:
        assert not self.unregistered, "called twice"
        self.unregistered = True
        return defer.succeed(None)

    def update(self, worker_config: Any, global_config: Any) -> defer.Deferred[None]:
        if worker_config.workername not in self.updates:
            self.updates.append(worker_config.workername)
        return defer.succeed(None)
