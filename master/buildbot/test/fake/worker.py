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

import os
from pathlib import PurePosixPath
from typing import Any

from twisted.internet import defer
from twisted.python.filepath import FilePath
from twisted.spread import pb
from twisted.trial.unittest import SkipTest

from buildbot.process import properties
from buildbot.test.fake import fakeprotocol
from buildbot.util.twisted import async_to_deferred
from buildbot.worker import Worker

RemoteWorker: type | None = None
try:
    from buildbot_worker.bot import LocalWorker as RemoteWorker
except ImportError:
    pass


class FakeWorker:
    workername = 'test'

    def __init__(self, master: Any) -> None:
        self.master = master
        self.conn = fakeprotocol.FakeConnection(self)
        self.info = properties.Properties()
        self.properties = properties.Properties()
        self.defaultProperties = properties.Properties()
        self.workerid = 383

    def acquireLocks(self) -> bool:
        return True

    def releaseLocks(self) -> None:
        pass

    def attached(self, conn: Any) -> defer.Deferred[None]:
        self.worker_system = 'posix'
        self.path_module = os.path
        self.path_cls = PurePosixPath
        self.workerid = 1234
        self.worker_basedir = '/wrk'
        return defer.succeed(None)

    def detached(self) -> None:
        pass

    def messageReceivedFromWorker(self) -> None:
        pass

    def addWorkerForBuilder(self, wfb: Any) -> None:
        pass

    def removeWorkerForBuilder(self, wfb: Any) -> None:
        pass

    def buildFinished(self, wfb: Any) -> None:
        pass

    def canStartBuild(self) -> None:
        pass

    def putInQuarantine(self) -> None:
        pass

    def resetQuarantine(self) -> None:
        pass


@async_to_deferred
async def disconnect_master_side_worker(worker: Any) -> None:
    # Force disconnection because the LocalWorker does not disconnect itself. Note that
    # the worker may have already been disconnected by something else (e.g. if it's not
    # responding). We need to call detached() explicitly because the order in which
    # disconnection subscriptions are invoked is unspecified.
    if worker.conn is not None:
        worker._detached_sub.unsubscribe()
        conn = worker.conn
        await worker.detached()
        conn.loseConnection()
    await worker.waitForCompleteShutdown()


class SeverWorkerConnectionMixin:
    _connection_severed = False
    _severed_deferreds: list[defer.Deferred[Any]] | None = None

    def disconnect_worker(self) -> defer.Deferred[None]:
        if not self._connection_severed:
            return defer.succeed(None)

        if self._severed_deferreds is not None:
            for d in self._severed_deferreds:
                d.errback(pb.PBConnectionLost('lost connection'))

        self._connection_severed = False

        return defer.succeed(None)

    def sever_connection(self) -> None:
        # stubs the worker connection so that it appears that the TCP connection
        # has been severed in a way that no response is ever received, but
        # messages don't fail immediately. All callback will be called when
        # disconnect_worker is called
        self._connection_severed = True

        def register_deferred() -> defer.Deferred[Any]:
            d: defer.Deferred[Any] = defer.Deferred()

            if self._severed_deferreds is None:
                self._severed_deferreds = []
            self._severed_deferreds.append(d)

            return d

        def remotePrint(message: str) -> defer.Deferred[Any]:
            return register_deferred()

        self.worker.conn.remotePrint = remotePrint  # type: ignore[attr-defined]

        def remoteGetWorkerInfo() -> defer.Deferred[Any]:
            return register_deferred()

        self.worker.conn.remoteGetWorkerInfo = remoteGetWorkerInfo  # type: ignore[attr-defined]

        def remoteSetBuilderList(builders: Any) -> defer.Deferred[Any]:
            return register_deferred()

        self.worker.conn.remoteSetBuilderList = remoteSetBuilderList  # type: ignore[attr-defined]

        def remoteStartCommand(
            remoteCommand: Any, builderName: str, commandId: str, commandName: str, args: Any
        ) -> defer.Deferred[Any]:
            return register_deferred()

        self.worker.conn.remoteStartCommand = remoteStartCommand  # type: ignore[attr-defined]

        def remoteShutdown() -> defer.Deferred[Any]:
            return register_deferred()

        self.worker.conn.remoteShutdown = remoteShutdown  # type: ignore[attr-defined]

        def remoteStartBuild(builderName: str) -> defer.Deferred[Any]:
            return register_deferred()

        self.worker.conn.remoteStartBuild = remoteStartBuild  # type: ignore[attr-defined]

        def remoteInterruptCommand(
            builderName: str, commandId: str, why: str
        ) -> defer.Deferred[Any]:
            return register_deferred()

        self.worker.conn.remoteInterruptCommand = remoteInterruptCommand  # type: ignore[attr-defined]


class WorkerController(SeverWorkerConnectionMixin):
    """
    A controller for a ``Worker``.

    https://glyph.twistedmatrix.com/2015/05/separate-your-fakes-and-your-inspectors.html
    """

    def __init__(
        self,
        case: Any,
        name: str,
        build_wait_timeout: int = 600,
        worker_class: type | None = None,
        **kwargs: Any,
    ) -> None:
        if worker_class is None:
            worker_class = Worker

        self.case = case
        self.build_wait_timeout = build_wait_timeout
        self.worker = worker_class(name, self, **kwargs)
        self.remote_worker: Any = None

    @async_to_deferred
    async def connect_worker(self) -> None:
        if self.remote_worker is not None:
            return
        if RemoteWorker is None:
            raise SkipTest("buildbot-worker package is not installed")
        workdir = FilePath(self.case.mktemp())
        workdir.createDirectory()
        self.remote_worker = RemoteWorker(self.worker.name, workdir.path, False)
        self.remote_worker.setServiceParent(self.worker)

    @async_to_deferred
    async def disconnect_worker(self) -> None:
        await super().disconnect_worker()
        if self.remote_worker is None:
            return

        worker = self.remote_worker
        self.remote_worker = None
        await worker.disownServiceParent()
        await disconnect_master_side_worker(self.worker)
