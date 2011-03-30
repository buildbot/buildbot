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
from twisted.trial import unittest
from twisted.internet import defer
from buildbot.process.botmaster import BotMaster

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

class TestBotMaster(unittest.TestCase):

    def setUp(self):
        self.botmaster = BotMaster(mock.Mock())

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

