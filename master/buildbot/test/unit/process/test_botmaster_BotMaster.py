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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot import config
from buildbot.process import factory
from buildbot.process.botmaster import BotMaster
from buildbot.process.results import CANCELLED
from buildbot.process.results import RETRY
from buildbot.test.fake import fakemaster
from buildbot.test.util.misc import TestReactorMixin


class TestCleanShutdown(TestReactorMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self.setUpTestReactor()
        self.master = fakemaster.make_master(self, wantData=True)
        self.botmaster = BotMaster()
        yield self.botmaster.setServiceParent(self.master)
        self.botmaster.startService()

    def assertReactorStopped(self, _=None):
        self.assertTrue(self.reactor.stop_called)

    def assertReactorNotStopped(self, _=None):
        self.assertFalse(self.reactor.stop_called)

    def makeFakeBuild(self, waitedFor=False):
        self.fake_builder = builder = mock.Mock()
        build_status = mock.Mock()
        builder.builder_status.getCurrentBuilds.return_value = [build_status]
        self.build_deferred = defer.Deferred()

        request = mock.Mock()
        request.waitedFor = waitedFor
        build = mock.Mock()
        build.stopBuild = self.stopFakeBuild
        build.waitUntilFinished.return_value = self.build_deferred
        build.requests = [request]
        builder.building = [build]

        self.botmaster.builders = mock.Mock()
        self.botmaster.builders.values.return_value = [builder]

    def stopFakeBuild(self, reason, results):
        self.reason = reason
        self.results = results
        self.finishFakeBuild()

    def finishFakeBuild(self):
        self.fake_builder.building = []
        self.build_deferred.callback(None)

    # tests

    def test_shutdown_idle(self):
        """Test that the master shuts down when it's idle"""
        self.botmaster.cleanShutdown()
        self.assertReactorStopped()

    def test_shutdown_busy(self):
        """Test that the master shuts down after builds finish"""
        self.makeFakeBuild()

        self.botmaster.cleanShutdown()

        # check that we haven't stopped yet, since there's a running build
        self.assertReactorNotStopped()

        # try to shut it down again, just to check that this does not fail
        self.botmaster.cleanShutdown()

        # Now we cause the build to finish
        self.finishFakeBuild()

        # And now we should be stopped
        self.assertReactorStopped()

    def test_shutdown_busy_quick(self):
        """Test that the master shuts down after builds finish"""
        self.makeFakeBuild()

        self.botmaster.cleanShutdown(quickMode=True)

        # And now we should be stopped
        self.assertReactorStopped()
        self.assertEqual(self.results, RETRY)

    def test_shutdown_busy_quick_cancelled(self):
        """Test that the master shuts down after builds finish"""
        self.makeFakeBuild(waitedFor=True)

        self.botmaster.cleanShutdown(quickMode=True)

        # And now we should be stopped
        self.assertReactorStopped()
        self.assertEqual(self.results, CANCELLED)

    def test_shutdown_cancel_not_shutting_down(self):
        """Test that calling cancelCleanShutdown when none is in progress
        works"""
        # this just shouldn't fail..
        self.botmaster.cancelCleanShutdown()

    def test_shutdown_cancel(self):
        """Test that we can cancel a shutdown"""
        self.makeFakeBuild()

        self.botmaster.cleanShutdown()

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


class TestBotMaster(TestReactorMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self.setUpTestReactor()
        self.master = fakemaster.make_master(self, wantMq=True, wantData=True)
        self.master.mq = self.master.mq
        self.master.botmaster.disownServiceParent()
        self.botmaster = BotMaster()
        yield self.botmaster.setServiceParent(self.master)
        self.new_config = mock.Mock()
        self.botmaster.startService()

    def tearDown(self):
        return self.botmaster.stopService()

    @defer.inlineCallbacks
    def test_reconfigServiceWithBuildbotConfig(self):
        # check that reconfigServiceBuilders is called.
        self.patch(self.botmaster, 'reconfigServiceBuilders',
                   mock.Mock(side_effect=lambda c: defer.succeed(None)))
        self.patch(self.botmaster, 'maybeStartBuildsForAllBuilders',
                   mock.Mock())

        new_config = mock.Mock()
        yield self.botmaster.reconfigServiceWithBuildbotConfig(new_config)

        self.botmaster.reconfigServiceBuilders.assert_called_with(
            new_config)
        self.assertTrue(
            self.botmaster.maybeStartBuildsForAllBuilders.called)

    @defer.inlineCallbacks
    def test_reconfigServiceBuilders_add_remove(self):
        bc = config.BuilderConfig(name='bldr', factory=factory.BuildFactory(),
                                  workername='f')
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

    def test_maybeStartBuildsForWorker(self):
        brd = self.botmaster.brd = mock.Mock()
        b1 = mock.Mock(name='frank')
        b1.name = 'frank'
        b2 = mock.Mock(name='larry')
        b2.name = 'larry'
        self.botmaster.getBuildersForWorker = mock.Mock(return_value=[b1, b2])

        self.botmaster.maybeStartBuildsForWorker('centos')

        self.botmaster.getBuildersForWorker.assert_called_once_with('centos')
        brd.maybeStartBuildsOn.assert_called_once_with(['frank', 'larry'])

    def test_maybeStartBuildsForAll(self):
        brd = self.botmaster.brd = mock.Mock()
        self.botmaster.builderNames = ['frank', 'larry']

        self.botmaster.maybeStartBuildsForAllBuilders()

        brd.maybeStartBuildsOn.assert_called_once_with(['frank', 'larry'])
