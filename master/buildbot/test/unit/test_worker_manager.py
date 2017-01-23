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

from __future__ import absolute_import
from __future__ import print_function

import mock

from twisted.internet import defer
from twisted.trial import unittest
from zope.interface import implementer

from buildbot import interfaces
from buildbot.process import botmaster
from buildbot.test.fake import fakemaster
from buildbot.util import service
from buildbot.worker import manager as workermanager


@implementer(interfaces.IWorker)
class FakeWorker(service.BuildbotService):

    reconfig_count = 0

    def __init__(self, workername):
        service.BuildbotService.__init__(self, name=workername)

    def reconfigService(self):
        self.reconfig_count += 1
        self.configured = True
        return defer.succeed(None)


class FakeWorker2(FakeWorker):
    pass


class TestWorkerManager(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self,
                                             wantMq=True, wantData=True)
        self.master.mq = self.master.mq
        self.workers = workermanager.WorkerManager(self.master)
        self.workers.setServiceParent(self.master)
        # workers expect a botmaster as well as a manager.
        self.master.botmaster.disownServiceParent()
        self.botmaster = botmaster.BotMaster()
        self.master.botmaster = self.botmaster
        self.master.botmaster.setServiceParent(self.master)

        self.new_config = mock.Mock()
        self.workers.startService()

    def tearDown(self):
        return self.workers.stopService()

    @defer.inlineCallbacks
    def test_reconfigServiceWorkers_add_remove(self):
        worker = FakeWorker('worker1')
        self.new_config.workers = [worker]

        yield self.workers.reconfigServiceWithBuildbotConfig(self.new_config)

        self.assertIdentical(worker.parent, self.workers)
        self.assertEqual(self.workers.workers, {'worker1': worker})

        self.new_config.workers = []

        self.assertEqual(worker.running, True)
        yield self.workers.reconfigServiceWithBuildbotConfig(self.new_config)

        self.assertEqual(worker.running, False)

    @defer.inlineCallbacks
    def test_reconfigServiceWorkers_reconfig(self):
        worker = FakeWorker('worker1')
        worker.setServiceParent(self.workers)
        worker.parent = self.master
        worker.manager = self.workers
        worker.botmaster = self.master.botmaster

        worker_new = FakeWorker('worker1')
        self.new_config.workers = [worker_new]

        yield self.workers.reconfigServiceWithBuildbotConfig(self.new_config)

        # worker was not replaced..
        self.assertIdentical(self.workers.workers['worker1'], worker)

    @defer.inlineCallbacks
    def test_reconfigServiceWorkers_class_changes(self):
        worker = FakeWorker('worker1')
        worker.setServiceParent(self.workers)

        worker_new = FakeWorker2('worker1')
        self.new_config.workers = [worker_new]

        yield self.workers.reconfigServiceWithBuildbotConfig(self.new_config)

        # worker *was* replaced (different class)
        self.assertIdentical(self.workers.workers['worker1'], worker_new)

    @defer.inlineCallbacks
    def test_newConnection_remoteGetWorkerInfo_failure(self):
        class Error(RuntimeError):
            pass

        conn = mock.Mock()
        conn.remoteGetWorkerInfo = mock.Mock(
            return_value=defer.fail(Error()))
        yield self.assertFailure(
            self.workers.newConnection(conn, "worker"), Error)
