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


import os

from twisted.internet import defer
from twisted.python.filepath import FilePath
from twisted.trial.unittest import SkipTest

from buildbot.process import properties
from buildbot.test.fake import fakeprotocol
from buildbot.worker import Worker

try:
    from buildbot_worker.bot import LocalWorker as RemoteWorker
except ImportError:
    RemoteWorker = None


class FakeWorker(object):
    workername = 'test'

    def __init__(self, master):
        self.master = master
        self.conn = fakeprotocol.FakeConnection(master, self)
        self.properties = properties.Properties()
        self.workerid = 383

    def acquireLocks(self):
        pass

    def releaseLocks(self):
        pass

    def attached(self, conn):
        self.worker_system = 'posix'
        self.path_module = os.path
        self.workerid = 1234
        self.worker_basedir = '/wrk'
        return defer.succeed(None)

    def detached(self):
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


class WorkerController:

    """
    A controller for a ``Worker``.

    https://glyph.twistedmatrix.com/2015/05/separate-your-fakes-and-your-inspectors.html
    """

    def __init__(self, case, name, build_wait_timeout=600,
                 worker_class=None, **kwargs):
        if worker_class is None:
            worker_class = Worker

        self.case = case
        self.build_wait_timeout = build_wait_timeout
        self.worker = worker_class(name, self, **kwargs)
        self.remote_worker = None

    def connect_worker(self):
        if self.remote_worker is not None:
            return
        if RemoteWorker is None:
            raise SkipTest("buildbot-worker package is not installed")
        workdir = FilePath(self.case.mktemp())
        workdir.createDirectory()
        self.remote_worker = RemoteWorker(self.worker.name, workdir.path, False)
        self.remote_worker.setServiceParent(self.worker)

    def disconnect_worker(self):
        if self.remote_worker is None:
            return
        self.worker.conn, conn = None, self.worker.conn
        # LocalWorker does actually disconnect, so we must force disconnection
        # via detached
        conn.notifyDisconnected()
        ret = self.remote_worker.disownServiceParent()
        self.remote_worker = None
        return ret

    def sever_connection(self):
        # stubs the worker connection so that it appears that the TCP connection
        # has been severed in a way that no response is ever received, but
        # messages don't fail immediately.
        def remotePrint(message):
            return defer.Deferred()
        self.worker.conn.remotePrint = remotePrint

        def remoteGetWorkerInfo():
            return defer.Deferred()
        self.worker.conn.remoteGetWorkerInfo = remoteGetWorkerInfo

        def remoteSetBuilderList(builders):
            return defer.Deferred()
        self.worker.conn.remoteSetBuilderList = remoteSetBuilderList

        def remoteStartCommand(remoteCommand, builderName, commandId,
                               commandName, args):
            return defer.Deferred()
        self.worker.conn.remoteStartCommand = remoteStartCommand

        def remoteShutdown():
            return defer.Deferred()
        self.worker.conn.remoteShutdown = remoteShutdown

        def remoteStartBuild(builderName):
            return defer.Deferred()
        self.worker.conn.remoteStartBuild = remoteStartBuild

        def remoteInterruptCommand(builderName, commandId, why):
            return defer.Deferred()
        self.worker.conn.remoteInterruptCommand = remoteInterruptCommand
