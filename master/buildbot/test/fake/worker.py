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

    def __init__(self, master):
        self.master = master
        self.conn = fakeprotocol.FakeConnection(self)
        self.info = properties.Properties()
        self.properties = properties.Properties()
        self.defaultProperties = properties.Properties()
        self.workerid = 383

    def acquireLocks(self):
        return True

    def releaseLocks(self):
        pass

    def attached(self, conn):
        self.worker_system = 'posix'
        self.path_module = os.path
        self.path_cls = PurePosixPath
        self.workerid = 1234
        self.worker_basedir = '/wrk'
        return defer.succeed(None)

    def detached(self):
        pass

    def messageReceivedFromWorker(self):
        pass

    def addWorkerForBuilder(self, wfb):
        pass

    def removeWorkerForBuilder(self, wfb):
        pass

    def buildFinished(self, wfb):
        pass

    def canStartBuild(self):
        pass

    def putInQuarantine(self):
        pass

    def resetQuarantine(self):
        pass


@async_to_deferred
async def disconnect_master_side_worker(worker) -> None:
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
    _severed_deferreds = None

    def disconnect_worker(self) -> defer.Deferred[None]:
        if not self._connection_severed:
            return defer.succeed(None)

        if self._severed_deferreds is not None:
            for d in self._severed_deferreds:
                d.errback(pb.PBConnectionLost('lost connection'))

        self._connection_severed = False

        return defer.succeed(None)

    def sever_connection(self):
        # stubs the worker connection so that it appears that the TCP connection
        # has been severed in a way that no response is ever received, but
        # messages don't fail immediately. All callback will be called when
        # disconnect_worker is called
        self._connection_severed = True

        def register_deferred():
            d = defer.Deferred()

            if self._severed_deferreds is None:
                self._severed_deferreds = []
            self._severed_deferreds.append(d)

            return d

        def remotePrint(message):
            return register_deferred()

        self.worker.conn.remotePrint = remotePrint

        def remoteGetWorkerInfo():
            return register_deferred()

        self.worker.conn.remoteGetWorkerInfo = remoteGetWorkerInfo

        def remoteSetBuilderList(builders):
            return register_deferred()

        self.worker.conn.remoteSetBuilderList = remoteSetBuilderList

        def remoteStartCommand(remoteCommand, builderName, commandId, commandName, args):
            return register_deferred()

        self.worker.conn.remoteStartCommand = remoteStartCommand

        def remoteShutdown():
            return register_deferred()

        self.worker.conn.remoteShutdown = remoteShutdown

        def remoteStartBuild(builderName):
            return register_deferred()

        self.worker.conn.remoteStartBuild = remoteStartBuild

        def remoteInterruptCommand(builderName, commandId, why):
            return register_deferred()

        self.worker.conn.remoteInterruptCommand = remoteInterruptCommand


class WorkerController(SeverWorkerConnectionMixin):
    """
    A controller for a ``Worker``.

    https://glyph.twistedmatrix.com/2015/05/separate-your-fakes-and-your-inspectors.html
    """

    def __init__(self, case, name, build_wait_timeout=600, worker_class=None, **kwargs):
        if worker_class is None:
            worker_class = Worker

        self.case = case
        self.build_wait_timeout = build_wait_timeout
        self.worker = worker_class(name, self, **kwargs)
        self.remote_worker = None

    @async_to_deferred
    async def connect_worker(self):
        if self.remote_worker is not None:
            return
        if RemoteWorker is None:
            raise SkipTest("buildbot-worker package is not installed")
        workdir = FilePath(self.case.mktemp())
        workdir.createDirectory()
        self.remote_worker = RemoteWorker(self.worker.name, workdir.path, False)
        self.remote_worker.setServiceParent(self.worker)

    @async_to_deferred
    async def disconnect_worker(self):
        await super().disconnect_worker()
        if self.remote_worker is None:
            return

        worker = self.remote_worker
        self.remote_worker = None
        await worker.disownServiceParent()
        await disconnect_master_side_worker(self.worker)
