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

from parameterized import parameterized

import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.reactor import TestReactorMixin
from buildbot.util import poll


class TestPollerSync(TestReactorMixin, unittest.TestCase):

    @poll.method
    def poll(self):
        self.calls += 1
        if self.fail_after_running:
            raise RuntimeError('oh noes')

    def setUp(self):
        self.setup_test_reactor()
        self.master = mock.Mock()
        self.master.reactor = self.reactor

        poll.track_poll_methods()
        self.calls = 0
        self.fail_after_running = False

    def tearDown(self):
        poll.reset_poll_methods()
        self.assertEqual(self.reactor.getDelayedCalls(), [])

    def test_call_not_started_does_nothing(self):
        self.reactor.advance(100)
        self.assertEqual(self.calls, 0)

    def test_call_when_stopped_does_nothing(self):
        self.poll()
        self.assertEqual(self.calls, 0)

    @defer.inlineCallbacks
    def test_call_when_started_forces_run(self):
        self.poll.start(interval=100, now=False)
        self.poll()
        self.reactor.advance(0)
        self.assertEqual(self.calls, 1)
        yield self.poll.stop()

    @defer.inlineCallbacks
    def test_start_with_now_forces_run_immediately(self):
        self.poll.start(interval=10, now=True)
        self.reactor.advance(0)
        self.assertEqual(self.calls, 1)
        yield self.poll.stop()

    @defer.inlineCallbacks
    def test_start_with_now_false_does_not_run(self):
        self.poll.start(interval=10, now=False)
        self.assertEqual(self.calls, 0)
        yield self.poll.stop()

    def test_stop_on_stopped_does_nothing(self):
        self.poll.start(interval=1)
        d = self.poll.stop()
        self.assertTrue(d.called)
        d = self.poll.stop()
        self.assertTrue(d.called)

    @defer.inlineCallbacks
    def test_start_twice_error(self):
        self.poll.start(interval=1)
        with self.assertRaises(Exception):
            self.poll.start(interval=2)
        yield self.poll.stop()

    def test_repeats_and_stops(self):
        """Polling repeats until stopped, and stop returns a Deferred"""
        self.poll.start(interval=10, now=True)
        self.reactor.advance(0)
        while self.reactor.seconds() <= 200:
            self.assertEqual(self.calls, (self.reactor.seconds() // 10) + 1)
            self.reactor.advance(1)

        d = self.poll.stop()
        self.assertTrue(d.called)

        self.assertEqual(self.calls, 21)
        self.reactor.advance(10)
        self.assertEqual(self.calls, 21)

    @defer.inlineCallbacks
    def test_fail_reschedules_and_logs_exceptions(self):
        self.fail_after_running = True
        self.poll.start(interval=1, now=True)
        self.reactor.advance(0)
        self.assertEqual(self.calls, 1)
        self.reactor.advance(1)
        self.assertEqual(self.calls, 2)
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 2)
        yield self.poll.stop()

    @parameterized.expand([
        ('shorter_than_interval_now_True', 5, True),
        ('longer_than_interval_now_True', 15, True),
        ('shorter_than_interval_now_False', 5, False),
        ('longer_than_interval_now_False', 15, False),
    ])
    @defer.inlineCallbacks
    def test_run_with_random_delay(self, name, random_delay_max, now):
        interval = 10

        with mock.patch("buildbot.util.poll.randint", return_value=random_delay_max):
            self.poll.start(interval=interval, now=now, random_delay_max=random_delay_max)
            self.reactor.advance(0)

            if not now:
                i = 0
                while i < interval:
                    self.assertEqual(self.calls, 0)
                    self.reactor.advance(1)
                    i += 1

            i = 0
            while i < random_delay_max:
                self.assertEqual(self.calls, 0)
                self.reactor.advance(1)
                i += 1
            self.assertEqual(self.calls, 1)
        yield self.poll.stop()

    @parameterized.expand([
        ('now_True', True),
        ('now_False', False),
    ])
    @defer.inlineCallbacks
    def test_run_with_random_delay_zero_interval_still_delays(self, name, now):
        random_delay_max = 5
        with mock.patch("buildbot.util.poll.randint", return_value=random_delay_max):
            self.poll.start(interval=0, now=now, random_delay_max=random_delay_max)
            self.reactor.advance(0)
            self.assertEqual(self.calls, 0)

            i = 0
            while i < random_delay_max:
                self.assertEqual(self.calls, 0)
                self.reactor.advance(1)
                i += 1
            self.assertEqual(self.calls, 1)

        yield self.poll.stop()

    @defer.inlineCallbacks
    def test_run_with_random_delay_stops_immediately_during_delay_phase(self):
        random_delay_max = 5
        with mock.patch("buildbot.util.poll.randint", return_value=random_delay_max):
            self.poll.start(interval=10, now=True, random_delay_max=random_delay_max)
            self.reactor.advance(1)
            self.assertEqual(self.calls, 0)
        yield self.poll.stop()


class TestPollerAsync(TestReactorMixin, unittest.TestCase):

    @poll.method
    @defer.inlineCallbacks
    def poll(self):
        assert not self.running, "overlapping call"
        self.running = True

        d = defer.Deferred()
        self.reactor.callLater(self.duration, d.callback, None)
        yield d

        self.calls += 1
        self.running = False

        if self.fail_after_running:
            raise RuntimeError('oh noes')

    def setUp(self):
        self.setup_test_reactor()
        self.master = mock.Mock()
        self.master.reactor = self.reactor

        poll.track_poll_methods()
        self.calls = 0
        self.running = False
        self.duration = 1
        self.fail_after_running = False

    def tearDown(self):
        poll.reset_poll_methods()

    @defer.inlineCallbacks
    def test_call_when_started_forces_run(self):
        self.poll.start(interval=10, now=True)
        self.reactor.advance(0)
        self.assertEqual(self.calls, 0)
        self.assertTrue(self.running)
        self.reactor.advance(self.duration)
        self.assertEqual(self.calls, 1)
        self.assertFalse(self.running)
        yield self.poll.stop()

    def test_repeats_and_stops(self):
        """ Polling repeats until stopped, and stop returns a Deferred.  The
        duration of the function's execution does not affect the execution
        interval: executions occur every 10 seconds.  """
        self.poll.start(interval=10, now=True)
        self.reactor.advance(0)

        while self.reactor.seconds() <= 200:
            self.assertEqual(self.calls, (self.reactor.seconds() + 9) // 10)
            self.assertEqual(self.running, self.reactor.seconds() % 10 == 0)
            self.reactor.advance(1)

        d = self.poll.stop()
        self.assertTrue(d.called)

        self.assertEqual(self.calls, 21)
        self.reactor.advance(10)
        self.assertEqual(self.calls, 21)

    @parameterized.expand([
        ('now_True', True),
        ('now_False', False),
    ])
    @defer.inlineCallbacks
    def test_zero_interval_starts_immediately(self, name, now):
        self.poll.start(interval=0, now=now)
        self.reactor.advance(0)

        self.assertEqual(self.calls, 0)
        self.assertTrue(self.running)
        self.reactor.advance(1)
        self.assertEqual(self.calls, 1)
        self.assertTrue(self.running)
        self.reactor.pump([1] * 10)
        self.assertEqual(self.calls, 11)
        self.assertTrue(self.running)
        d = self.poll.stop()
        self.assertTrue(self.running)
        self.reactor.advance(1)
        self.assertFalse(self.running)
        yield d

    @defer.inlineCallbacks
    def test_fail_reschedules_and_logs_exceptions(self):
        self.fail_after_running = True
        self.poll.start(interval=10, now=True)
        self.reactor.advance(0)
        self.assertTrue(self.running)
        self.reactor.advance(1)
        self.assertEqual(self.calls, 1)
        self.reactor.advance(10)
        self.assertTrue(self.running)
        self.reactor.advance(1)
        self.assertEqual(self.calls, 2)
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 2)
        yield self.poll.stop()

    def test_stop_while_running_waits_for_completion(self):
        self.duration = 2
        self.poll.start(interval=10)
        self.reactor.advance(0)
        self.assertFalse(self.running)
        self.reactor.advance(10)
        self.assertTrue(self.running)
        d = self.poll.stop()
        self.assertFalse(d.called)  # not stopped yet
        self.reactor.advance(1)
        self.assertFalse(d.called)
        self.reactor.advance(1)
        self.assertTrue(d.called)

    def test_call_while_waiting_schedules_immediately(self):
        self.poll.start(interval=10)
        self.reactor.advance(0)
        self.reactor.advance(5)
        self.poll()
        self.reactor.advance(0)
        self.assertTrue(self.running)
        self.reactor.advance(1)
        self.assertEqual(self.calls, 1)
        self.assertFalse(self.running)
        self.reactor.advance(4)
        self.assertTrue(self.running)
        self.reactor.advance(1)
        self.assertEqual(self.calls, 2)

    def test_call_while_running_reschedules_immediately_after(self):
        self.duration = 5
        self.poll.start(interval=10, now=True)
        self.reactor.advance(0)
        self.assertTrue(self.running)
        self.reactor.advance(3)
        self.poll()
        self.reactor.advance(2)
        self.assertEqual(self.calls, 1)
        self.reactor.advance(5)
        self.assertEqual(self.calls, 2)

    def test_call_while_running_then_stop(self):
        """Calling the poll method while the decorated method is running, then
        calling stop will not wait for both invocations to complete."""
        self.duration = 5
        self.poll.start(interval=10, now=True)
        self.reactor.advance(0)
        self.assertTrue(self.running)
        self.reactor.advance(3)
        self.assertTrue(self.running)
        self.poll()
        d = self.poll.stop()
        self.reactor.advance(2)
        self.assertEqual(self.calls, 1)
        self.assertTrue(d.called)

        self.reactor.advance(5)
        self.assertEqual(self.calls, 1)

    def test_stop_twice_while_running(self):
        """If stop is called *twice* while the poll function is running, then
        neither Deferred fires until the run is complete."""
        self.duration = 2
        self.poll.start(interval=10)
        self.reactor.advance(0)
        self.assertFalse(self.running)
        self.reactor.advance(10)
        self.assertTrue(self.running)
        d1 = self.poll.stop()
        self.assertFalse(d1.called)  # not stopped yet
        self.reactor.advance(1)
        d2 = self.poll.stop()
        self.assertFalse(d2.called)
        self.reactor.advance(1)
        self.assertTrue(d1.called)
        self.assertTrue(d2.called)

    @defer.inlineCallbacks
    def test_stop_and_restart(self):
        """If the method is immediately restarted from a callback on a stop Deferred,
        the polling continues with the new start time."""
        self.duration = 6
        self.poll.start(interval=10)
        self.reactor.advance(0)
        self.assertFalse(self.running)
        self.reactor.advance(10)
        self.assertTrue(self.running)
        d = self.poll.stop()
        self.assertFalse(d.called)  # not stopped yet
        self.reactor.advance(6)
        self.assertFalse(self.running)
        self.assertTrue(d.called)
        yield d
        self.poll.start(interval=10)
        self.reactor.advance(10)
        self.assertEqual(self.reactor.seconds(), 26)
        self.assertTrue(self.running)

        self.reactor.advance(6)
        yield self.poll.stop()

    def test_method_longer_than_interval_invoked_at_interval_multiples(self):
        self.duration = 4
        self.poll.start(interval=3, now=True)
        self.reactor.advance(0)

        exp = [
            (0, True, 0),
            (1, True, 0),
            (2, True, 0),
            (3, True, 0),
            (4, False, 1),
            (5, False, 1),
            (6, True, 1),  # next multiple of 3
            (10, False, 2),
            (12, True, 2),
            (16, False, 3),
        ]
        for secs, running, calls in exp:
            while self.reactor.seconds() < secs:
                self.reactor.advance(1)
            self.assertEqual(self.running, running)
            self.assertEqual(self.calls, calls)

    @parameterized.expand([
        ('shorter_than_interval_now_True', 5, True),
        ('longer_than_interval_now_True', 15, True),
        ('shorter_than_interval_now_False', 5, False),
        ('longer_than_interval_now_False', 15, False),
    ])
    @defer.inlineCallbacks
    def test_run_with_random_delay(self, name, random_delay_max, now):
        interval = 10

        with mock.patch("buildbot.util.poll.randint", return_value=random_delay_max):
            self.poll.start(interval=interval, now=now, random_delay_max=random_delay_max)
            self.reactor.advance(0)

            if not now:
                i = 0
                while i < interval:
                    self.assertFalse(self.running)
                    self.assertEqual(self.calls, 0)
                    self.reactor.advance(1)
                    i += 1

            i = 0
            while i < random_delay_max:
                self.assertFalse(self.running)
                self.assertEqual(self.calls, 0)
                self.reactor.advance(1)
                i += 1

            self.assertEqual(self.calls, 0)
            self.assertTrue(self.running)
            self.reactor.advance(self.duration)
            self.assertEqual(self.calls, 1)
            self.assertFalse(self.running)
        yield self.poll.stop()

    @parameterized.expand([
        ('now_True', True),
        ('now_False', False),
    ])
    @defer.inlineCallbacks
    def test_run_with_random_delay_zero_interval_still_delays(self, name, now):
        random_delay_max = 5
        with mock.patch("buildbot.util.poll.randint", return_value=random_delay_max):
            self.poll.start(interval=0, now=now, random_delay_max=random_delay_max)
            self.reactor.advance(0)
            self.assertFalse(self.running)
            self.assertEqual(self.calls, 0)

            i = 0
            while i < random_delay_max:
                self.assertFalse(self.running)
                self.assertEqual(self.calls, 0)
                self.reactor.advance(1)
                i += 1

            self.assertTrue(self.running)
            self.reactor.advance(1)
            self.assertEqual(self.calls, 1)
            self.assertFalse(self.running)

        yield self.poll.stop()

    @defer.inlineCallbacks
    def test_run_with_random_delay_stops_immediately_during_delay_phase(self):
        random_delay_max = 5
        with mock.patch("buildbot.util.poll.randint", return_value=random_delay_max):
            self.poll.start(interval=10, now=True, random_delay_max=random_delay_max)
            self.reactor.advance(1)
            self.assertFalse(self.running)
            self.assertEqual(self.calls, 0)
        yield self.poll.stop()
