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
from buildbot.buildslave import manager as bslavemanager
from buildbot.process import botmaster
from buildbot.test.fake import fakemaster
from buildbot.util import service
from twisted.internet import defer
from twisted.trial import unittest
from zope.interface import implements


class FakeBuildSlave(service.ReconfigurableServiceMixin, service.AsyncService):

    implements(interfaces.IBuildSlave)

    reconfig_count = 0

    def __init__(self, slavename):
        self.slavename = slavename

    def reconfigServiceWithBuildbotConfig(self, new_config):
        self.reconfig_count += 1
        return defer.succeed(None)


class FakeBuildSlave2(FakeBuildSlave):
    pass


class TestBuildSlaveManager(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self,
                                             wantMq=True, wantData=True)
        self.master.mq = self.master.mq
        self.buildslaves = bslavemanager.BuildslaveManager(self.master)
        # slaves expect a botmaster as well as a manager.
        self.botmaster = botmaster.BotMaster(self.master)
        self.master.botmaster = self.botmaster

        self.new_config = mock.Mock()
        self.buildslaves.startService()

    def tearDown(self):
        return self.buildslaves.stopService()

    def test_reconfigServiceWithBuildbotConfig(self):
        self.patch(self.buildslaves, 'reconfigServiceSlaves',
                   mock.Mock(side_effect=lambda c: defer.succeed(None)))

        new_config = mock.Mock()
        d = self.buildslaves.reconfigServiceWithBuildbotConfig(new_config)

        @d.addCallback
        def check(_):
            self.buildslaves.reconfigServiceSlaves.assert_called_with(new_config)

        return d

    @defer.inlineCallbacks
    def test_reconfigServiceSlaves_add_remove(self):
        sl = FakeBuildSlave('sl1')
        self.new_config.slaves = [sl]

        yield self.buildslaves.reconfigServiceSlaves(self.new_config)

        self.assertIdentical(sl.parent, self.buildslaves)
        self.assertEqual(self.buildslaves.slaves, {'sl1': sl})

        self.new_config.slaves = []

        yield self.buildslaves.reconfigServiceSlaves(self.new_config)

        self.assertIdentical(sl.parent, None)
        self.assertIdentical(sl.master, None)

    @defer.inlineCallbacks
    def test_reconfigServiceSlaves_reconfig(self):
        sl = FakeBuildSlave('sl1')
        self.buildslaves.slaves = dict(sl1=sl)
        sl.setServiceParent(self.buildslaves)
        sl.master = self.master
        sl.manager = self.buildslaves
        sl.botmaster = self.master.botmaster

        sl_new = FakeBuildSlave('sl1')
        self.new_config.slaves = [sl_new]

        yield self.buildslaves.reconfigServiceSlaves(self.new_config)

        # sl was not replaced..
        self.assertIdentical(self.buildslaves.slaves['sl1'], sl)

    @defer.inlineCallbacks
    def test_reconfigServiceSlaves_class_changes(self):
        sl = FakeBuildSlave('sl1')
        self.buildslaves.slaves = dict(sl1=sl)
        sl.setServiceParent(self.buildslaves)
        sl.master = self.master
        sl.manager = self.buildslaves
        sl.botmaster = self.master.botmaster

        sl_new = FakeBuildSlave2('sl1')
        self.new_config.slaves = [sl_new]

        yield self.buildslaves.reconfigServiceSlaves(self.new_config)

        # sl *was* replaced (different class)
        self.assertIdentical(self.buildslaves.slaves['sl1'], sl_new)
