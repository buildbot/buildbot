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

import mock

from buildbot import interfaces
from buildbot.buildworker import manager as bworkermanager
from buildbot.process import botmaster
from buildbot.test.fake import fakemaster
from buildbot.util import service
from twisted.internet import defer
from twisted.trial import unittest
from zope.interface import implements


class FakeBuildWorker(service.BuildbotService):

    implements(interfaces.IBuildWorker)

    reconfig_count = 0

    def __init__(self, workername):
        service.BuildbotService.__init__(self, name=workername)

    def reconfigService(self):
        self.reconfig_count += 1
        self.configured = True
        return defer.succeed(None)


class FakeBuildWorker2(FakeBuildWorker):
    pass


class TestBuildWorkerManager(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self,
                                             wantMq=True, wantData=True)
        self.master.mq = self.master.mq
        self.buildworkers = bworkermanager.BuildworkerManager(self.master)
        self.buildworkers.setServiceParent(self.master)
        # workers expect a botmaster as well as a manager.
        self.master.botmaster.disownServiceParent()
        self.botmaster = botmaster.BotMaster()
        self.master.botmaster = self.botmaster
        self.master.botmaster.setServiceParent(self.master)

        self.new_config = mock.Mock()
        self.buildworkers.startService()

    def tearDown(self):
        return self.buildworkers.stopService()

    @defer.inlineCallbacks
    def test_reconfigServiceWorkers_add_remove(self):
        sl = FakeBuildWorker('sl1')
        self.new_config.workers = [sl]

        yield self.buildworkers.reconfigServiceWithBuildbotConfig(self.new_config)

        self.assertIdentical(sl.parent, self.buildworkers)
        self.assertEqual(self.buildworkers.workers, {'sl1': sl})

        self.new_config.workers = []

        yield self.buildworkers.reconfigServiceWithBuildbotConfig(self.new_config)

        self.assertIdentical(sl.parent, None)
        self.assertIdentical(sl.master, None)

    @defer.inlineCallbacks
    def test_reconfigServiceWorkers_reconfig(self):
        sl = FakeBuildWorker('sl1')
        sl.setServiceParent(self.buildworkers)
        sl.parent = self.master
        sl.manager = self.buildworkers
        sl.botmaster = self.master.botmaster

        sl_new = FakeBuildWorker('sl1')
        self.new_config.workers = [sl_new]

        yield self.buildworkers.reconfigServiceWithBuildbotConfig(self.new_config)

        # sl was not replaced..
        self.assertIdentical(self.buildworkers.workers['sl1'], sl)

    @defer.inlineCallbacks
    def test_reconfigServiceWorkers_class_changes(self):
        sl = FakeBuildWorker('sl1')
        sl.setServiceParent(self.buildworkers)

        sl_new = FakeBuildWorker2('sl1')
        self.new_config.workers = [sl_new]

        yield self.buildworkers.reconfigServiceWithBuildbotConfig(self.new_config)

        # sl *was* replaced (different class)
        self.assertIdentical(self.buildworkers.workers['sl1'], sl_new)
