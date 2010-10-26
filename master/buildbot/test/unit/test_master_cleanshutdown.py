# Test clean shutdown functionality of the master
from mock import Mock
from twisted.trial import unittest
from twisted.internet import defer
from buildbot.master import BotMaster

class TestCleanShutdown(unittest.TestCase):
    def setUp(self):
        self.master = BotMaster()
        self.master.reactor = Mock()
        self.master.startService()

    def test_shutdown_idle(self):
        """Test that the master shuts down when it's idle"""
        d = self.master.cleanShutdown()
        def _check(ign):
            self.assertEquals(self.master.reactor.stop.called, True)

        d.addCallback(_check)
        return d

    def test_shutdown_busy(self):
        """Test that the master shuts down after builds finish"""
        # Fake some builds
        builder = Mock()
        build = Mock()
        builder.builder_status.getCurrentBuilds.return_value = [build]

        d_finished = defer.Deferred()
        build.waitUntilFinished.return_value = d_finished

        self.master.builders = Mock()
        self.master.builders.values.return_value = [builder]

        d_shutdown = self.master.cleanShutdown()

        # Trigger the loop to get things going
        self.master.loop.trigger()

        # First we wait for it to quiet down again
        d = self.master.loop.when_quiet()

        # Next we check that we haven't stopped yet, since there's a running
        # build
        def _check1(ign):
            self.assertEquals(self.master.reactor.stop.called, False)
        d.addCallback(_check1)

        # Now we cause the build to finish, then kick the loop again,
        # empty out the list of running builds, and wait for the shutdown
        # process to finish
        def _finish_build(ign):
            d_finished.callback(None)
            self.master.loop.trigger()
            self.master.builders.values.return_value = []
            return d_shutdown
        d.addCallback(_finish_build)

        # And now we should be done
        def _check2(ign):
            self.assertEquals(self.master.reactor.stop.called, True)
        d.addCallback(_check2)

        return d

    def test_shutdown_cancel(self):
        """Test that we can cancel a shutdown"""
        # Fake some builds
        builder = Mock()
        build = Mock()
        builder.builder_status.getCurrentBuilds.return_value = [build]

        d_finished = defer.Deferred()
        build.waitUntilFinished.return_value = d_finished

        self.master.builders = Mock()
        self.master.builders.values.return_value = [builder]

        d_shutdown = self.master.cleanShutdown()

        # Trigger the loop to get things going
        self.master.loop.trigger()

        # First we wait for it to quiet down again
        d = self.master.loop.when_quiet()

        # Next we check that we haven't stopped yet, since there's a running
        # build.
        # We cancel the shutdown here too
        def _check1(ign):
            self.assertEquals(self.master.reactor.stop.called, False)
            self.master.cancelCleanShutdown()
        d.addCallback(_check1)

        # Now we cause the build to finish, then kick the loop again,
        # empty out the list of running builds, and wait for the shutdown
        # process to finish
        def _finish_build(ign):
            d_finished.callback(None)
            self.master.loop.trigger()
            self.master.builders.values.return_value = []
            return d_shutdown
        d.addCallback(_finish_build)

        # We should still be running!
        def _check2(ign):
            self.assertEquals(self.master.reactor.stop.called, False)
        d.addCallback(_check2)

        return d

    def test_shutdown_no_new_builds(self):
        """Test that no new builds get handed out when we're shutting down"""
        # Fake some builds
        builder = Mock()
        build = Mock()
        builder.builder_status.getCurrentBuilds.return_value = [build]

        d_finished = defer.Deferred()
        build.waitUntilFinished.return_value = d_finished

        self.master.builders = Mock()
        self.master.builders.values.return_value = [builder]

        self.assertEquals(self.master._get_processors(), [builder.run])

        d_shutdown = self.master.cleanShutdown()
        assert d_shutdown

        # Trigger the loop to get things going
        self.master.loop.trigger()

        # First we wait for it to quiet down again
        d = self.master.loop.when_quiet()

        # Next we check that we haven't stopped yet, since there's a running
        # build.
        # Also check that we're not trying to hand out new builds!
        def _check1(ign):
            self.assertEquals(self.master.reactor.stop.called, False)
            self.assertEquals(self.master._get_processors(), [])
        d.addCallback(_check1)

        return d
