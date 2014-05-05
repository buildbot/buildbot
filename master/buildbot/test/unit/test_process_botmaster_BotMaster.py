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

from buildbot import config
from buildbot import interfaces
from buildbot.process import factory
from buildbot.process.botmaster import BotMaster
from buildbot.test.fake import fakemaster
from twisted.application import service
from twisted.internet import defer
from twisted.trial import unittest
from zope.interface import implements


class TestCleanShutdown(unittest.TestCase):

    def setUp(self):
        self.botmaster = BotMaster(mock.Mock())
        self.reactor = mock.Mock()
        self.botmaster.startService()

    def assertReactorStopped(self, _=None):
        self.assertTrue(self.reactor.stop.called)

    def assertReactorNotStopped(self, _=None):
        self.assertFalse(self.reactor.stop.called)

    def makeFakeBuild(self):
        self.fake_builder = builder = mock.Mock()
        build = mock.Mock()
        builder.builder_status.getCurrentBuilds.return_value = [build]

        self.build_deferred = defer.Deferred()
        build.waitUntilFinished.return_value = self.build_deferred

        self.botmaster.builders = mock.Mock()
        self.botmaster.builders.values.return_value = [builder]

    def finishFakeBuild(self):
        self.fake_builder.builder_status.getCurrentBuilds.return_value = []
        self.build_deferred.callback(None)

    # tests

    def test_shutdown_idle(self):
        """Test that the master shuts down when it's idle"""
        self.botmaster.cleanShutdown(_reactor=self.reactor)
        self.assertReactorStopped()

    def test_shutdown_busy(self):
        """Test that the master shuts down after builds finish"""
        self.makeFakeBuild()

        self.botmaster.cleanShutdown(_reactor=self.reactor)

        # check that we haven't stopped yet, since there's a running build
        self.assertReactorNotStopped()

        # try to shut it down again, just to check that this does not fail
        self.botmaster.cleanShutdown(_reactor=self.reactor)

        # Now we cause the build to finish
        self.finishFakeBuild()

        # And now we should be stopped
        self.assertReactorStopped()

    def test_shutdown_cancel_not_shutting_down(self):
        """Test that calling cancelCleanShutdown when none is in progress
        works"""
        # this just shouldn't fail..
        self.botmaster.cancelCleanShutdown()

    def test_shutdown_cancel(self):
        """Test that we can cancel a shutdown"""
        self.makeFakeBuild()

        self.botmaster.cleanShutdown(_reactor=self.reactor)

        # Next we check that we haven't stopped yet, since there's a running
        # build.
        self.assertReactorNotStopped()

        # but the BuildRequestDistributor should not be running
        self.assertFalse(self.botmaster.brd.running)

        # Cancel the shutdown
        self.botmaster.cancelCleanShutdown()

        # Now we cause the build to finish
        self.finishFakeBuild()

        # We should still be running!
        self.assertReactorNotStopped()

        # and the BuildRequestDistributor should be, as well
        self.assertTrue(self.botmaster.brd.running)


class FakeBuildSlave(config.ReconfigurableServiceMixin, service.Service):

    implements(interfaces.IBuildSlave)

    reconfig_count = 0

    def __init__(self, slavename):
        self.slavename = slavename

    def reconfigService(self, new_config):
        self.reconfig_count += 1
        return defer.succeed(None)


class FakeBuildSlave2(FakeBuildSlave):
    pass


class TestBotMaster(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master()
        self.botmaster = BotMaster(self.master)
        self.new_config = mock.Mock()
        self.botmaster.startService()

    def tearDown(self):
        return self.botmaster.stopService()

    def test_reconfigService(self):
        # check that reconfigServiceSlaves and reconfigServiceBuilders are
        # both called; they will be tested invidually below
        self.patch(self.botmaster, 'reconfigServiceBuilders',
                   mock.Mock(side_effect=lambda c: defer.succeed(None)))
        self.patch(self.botmaster, 'reconfigServiceSlaves',
                   mock.Mock(side_effect=lambda c: defer.succeed(None)))
        self.patch(self.botmaster, 'maybeStartBuildsForAllBuilders',
                   mock.Mock())

        new_config = mock.Mock()
        d = self.botmaster.reconfigService(new_config)

        @d.addCallback
        def check(_):
            self.botmaster.reconfigServiceBuilders.assert_called_with(
                new_config)
            self.botmaster.reconfigServiceSlaves.assert_called_with(
                new_config)
            self.assertTrue(
                self.botmaster.maybeStartBuildsForAllBuilders.called)
        return d

    @defer.inlineCallbacks
    def test_reconfigServiceSlaves_add_remove(self):
        sl = FakeBuildSlave('sl1')
        self.new_config.slaves = [sl]

        yield self.botmaster.reconfigServiceSlaves(self.new_config)

        self.assertIdentical(sl.parent, self.botmaster)
        self.assertEqual(self.botmaster.slaves, {'sl1': sl})

        self.new_config.slaves = []

        yield self.botmaster.reconfigServiceSlaves(self.new_config)

        self.assertIdentical(sl.parent, None)
        self.assertIdentical(sl.master, None)

    @defer.inlineCallbacks
    def test_reconfigServiceSlaves_reconfig(self):
        sl = FakeBuildSlave('sl1')
        self.botmaster.slaves = dict(sl1=sl)
        sl.setServiceParent(self.botmaster)
        sl.master = self.master
        sl.botmaster = self.botmaster

        sl_new = FakeBuildSlave('sl1')
        self.new_config.slaves = [sl_new]

        yield self.botmaster.reconfigServiceSlaves(self.new_config)

        # sl was not replaced..
        self.assertIdentical(self.botmaster.slaves['sl1'], sl)

    @defer.inlineCallbacks
    def test_reconfigServiceSlaves_class_changes(self):
        sl = FakeBuildSlave('sl1')
        self.botmaster.slaves = dict(sl1=sl)
        sl.setServiceParent(self.botmaster)
        sl.master = self.master
        sl.botmaster = self.botmaster

        sl_new = FakeBuildSlave2('sl1')
        self.new_config.slaves = [sl_new]

        yield self.botmaster.reconfigServiceSlaves(self.new_config)

        # sl *was* replaced (different class)
        self.assertIdentical(self.botmaster.slaves['sl1'], sl_new)

    @defer.inlineCallbacks
    def test_reconfigServiceBuilders_add_remove(self):
        bc = config.BuilderConfig(name='bldr', factory=factory.BuildFactory(),
                                  slavename='f')
        self.new_config.builders = [bc]

        yield self.botmaster.reconfigServiceBuilders(self.new_config)

        bldr = self.botmaster.builders['bldr']
        self.assertIdentical(bldr.parent, self.botmaster)
        self.assertIdentical(bldr.master, self.master)
        self.assertEqual(self.botmaster.builderNames, ['bldr'])

        self.new_config.builders = []

        yield self.botmaster.reconfigServiceBuilders(self.new_config)

        self.assertIdentical(bldr.parent, None)
        self.assertIdentical(bldr.master, None)
        self.assertEqual(self.botmaster.builders, {})
        self.assertEqual(self.botmaster.builderNames, [])

    def test_maybeStartBuildsForBuilder(self):
        brd = self.botmaster.brd = mock.Mock()

        self.botmaster.maybeStartBuildsForBuilder('frank')

        brd.maybeStartBuildsOn.assert_called_once_with(['frank'])

    def test_maybeStartBuildsForSlave(self):
        brd = self.botmaster.brd = mock.Mock()
        b1 = mock.Mock(name='frank')
        b1.name = 'frank'
        b2 = mock.Mock(name='larry')
        b2.name = 'larry'
        self.botmaster.getBuildersForSlave = mock.Mock(return_value=[b1, b2])

        self.botmaster.maybeStartBuildsForSlave('centos')

        self.botmaster.getBuildersForSlave.assert_called_once_with('centos')
        brd.maybeStartBuildsOn.assert_called_once_with(['frank', 'larry'])

    def test_maybeStartBuildsForAll(self):
        brd = self.botmaster.brd = mock.Mock()
        self.botmaster.builderNames = ['frank', 'larry']

        self.botmaster.maybeStartBuildsForAllBuilders()

        brd.maybeStartBuildsOn.assert_called_once_with(['frank', 'larry'])
