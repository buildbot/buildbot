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
from __future__ import division
from __future__ import print_function

from twisted.internet import defer
from twisted.internet import task
from twisted.trial import unittest

from buildbot.util import poll


class TestPollerSync(unittest.TestCase):

    @poll.method
    def poll(self):
        self.calls += 1
        if self.fail:
            raise RuntimeError('oh noes')

    def setUp(self):
        poll.track_poll_methods()
        self.calls = 0
        self.fail = False
        self.poll._reactor = self.clock = task.Clock()

    def tearDown(self):
        poll.reset_poll_methods()
        self.assertEqual(self.clock.getDelayedCalls(), [])

    def test_not_started(self):
        """If the poll method isn't started, nothing happens"""
        self.clock.advance(100)
        self.assertEqual(self.calls, 0)

    def test_call_when_stopped(self):
        """Calling the poll method does nothing when stopped."""
        self.poll()
        self.assertEqual(self.calls, 0)

    def test_call_when_started(self):
        """Calling the poll method when started forces a run."""
        self.poll.start(interval=100, now=False)
        self.poll()
        self.clock.advance(0)
        self.assertEqual(self.calls, 1)
        return self.poll.stop()

    def test_run_now(self):
        """If NOW is true, the poll runs immediately"""
        self.poll.start(interval=10, now=True)
        self.assertEqual(self.calls, 1)
        return self.poll.stop()

    def test_no_run_now(self):
        """If NOW is false, the poll does not run immediately"""
        self.poll.start(interval=10, now=False)
        self.assertEqual(self.calls, 0)
        return self.poll.stop()

    def test_stop_twice(self):
        """Calling stop on a stopped poller does nothing"""
        self.poll.start(interval=1)
        d = self.poll.stop()
        self.assertTrue(d.called)
        d = self.poll.stop()
        self.assertTrue(d.called)

    def test_start_twice(self):
        """Calling start on an already-started loop is an error."""
        self.poll.start(interval=1)
        self.assertRaises(Exception, lambda: self.poll.start(interval=2))
        return self.poll.stop()

    def test_repeats_and_stops(self):
        """Polling repeats until stopped, and stop returns a Deferred"""
        self.poll.start(interval=10, now=True)
        while self.clock.seconds() <= 200:
            self.assertEqual(self.calls, (self.clock.seconds() // 10) + 1)
            self.clock.advance(1)

        d = self.poll.stop()
        self.assertTrue(d.called)

        self.assertEqual(self.calls, 21)
        self.clock.advance(10)
        self.assertEqual(self.calls, 21)

    def test_fails(self):
        """If the poll function fails, it is still called again, but
        the exception is logged each time."""
        self.fail = True
        self.poll.start(interval=1, now=True)
        self.assertEqual(self.calls, 1)
        self.clock.advance(1)
        self.assertEqual(self.calls, 2)
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 2)
        return self.poll.stop()


class TestPollerAsync(unittest.TestCase):

    @poll.method
    def poll(self):
        assert not self.running, "overlapping call"
        self.running = True
        d = defer.Deferred()
        self.clock.callLater(self.duration, d.callback, None)

        @d.addCallback
        def inc(_):
            self.calls += 1
            self.running = False

        @d.addCallback
        def maybeFail(_):
            if self.fail:
                raise RuntimeError('oh noes')
        return d

    def setUp(self):
        poll.track_poll_methods()
        self.calls = 0
        self.running = False
        self.duration = 1
        self.fail = False
        self.poll._reactor = self.clock = task.Clock()

    def tearDown(self):
        poll.reset_poll_methods()

    def test_run_now(self):
        """If NOW is true, the poll begins immediately"""
        self.poll.start(interval=10, now=True)
        self.assertEqual(self.calls, 0)
        self.assertTrue(self.running)
        self.clock.advance(self.duration)
        self.assertEqual(self.calls, 1)
        self.assertFalse(self.running)

    def test_no_run_now(self):
        """If NOW is false, the poll begins after the interval"""
        self.poll.start(interval=10, now=False)
        self.assertEqual(self.calls, 0)
        self.assertFalse(self.running)
        self.clock.advance(10)
        self.assertEqual(self.calls, 0)
        self.assertTrue(self.running)
        self.clock.advance(1)
        self.assertEqual(self.calls, 1)
        self.assertFalse(self.running)

    def test_repeats_and_stops(self):
        """ Polling repeats until stopped, and stop returns a Deferred.  The
        duration of the function's execution does not affect the execution
        interval: executions occur every 10 seconds.  """
        self.poll.start(interval=10, now=True)
        while self.clock.seconds() <= 200:
            self.assertEqual(self.calls, (self.clock.seconds() + 9) // 10)
            self.assertEqual(self.running, self.clock.seconds() % 10 == 0)
            self.clock.advance(1)

        d = self.poll.stop()
        self.assertTrue(d.called)

        self.assertEqual(self.calls, 21)
        self.clock.advance(10)
        self.assertEqual(self.calls, 21)

    def test_fails(self):
        """If the poll function fails, it is still called again, but
        the exception is logged each time."""
        self.fail = True
        self.poll.start(interval=10, now=True)
        self.clock.advance(1)
        self.assertEqual(self.calls, 1)
        self.clock.advance(10)
        self.assertTrue(self.running)
        self.clock.advance(1)
        self.assertEqual(self.calls, 2)
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 2)

    def test_stop_while_running(self):
        """If stop is called while the poll function is running, then stop's
        Deferred does not fire until the run is complete."""
        self.duration = 2
        self.poll.start(interval=10)
        self.clock.advance(10)
        self.assertTrue(self.running)
        d = self.poll.stop()
        self.assertFalse(d.called)  # not stopped yet
        self.clock.advance(1)
        self.assertFalse(d.called)
        self.clock.advance(1)
        self.assertTrue(d.called)

    def test_call_while_running(self):
        """Calling the poll method while the decorated method is running causes
        a second call as soon as the first is done."""
        self.duration = 5
        self.poll.start(interval=10, now=True)
        self.clock.advance(3)
        self.poll()
        self.clock.advance(2)
        self.assertEqual(self.calls, 1)
        self.clock.advance(5)
        self.assertEqual(self.calls, 2)

    def test_call_while_running_then_stop(self):
        """Calling the poll method while the decorated method is running, then
        calling stop will wait for both invocations to complete."""
        self.duration = 5
        self.poll.start(interval=10, now=True)
        self.clock.advance(3)
        self.poll()
        d = self.poll.stop()
        self.clock.advance(2)
        self.assertEqual(self.calls, 1)
        self.clock.advance(4)
        self.assertEqual(self.calls, 1)
        self.assertFalse(d.called)
        self.clock.advance(1)
        self.assertEqual(self.calls, 2)
        self.assertTrue(d.called)

    def test_stop_twice_while_running(self):
        """If stop is called *twice* while the poll function is running, then
        neither Deferred fires until the run is complete."""
        self.duration = 2
        self.poll.start(interval=10)
        self.clock.advance(10)
        self.assertTrue(self.running)
        d1 = self.poll.stop()
        self.assertFalse(d1.called)  # not stopped yet
        self.clock.advance(1)
        d2 = self.poll.stop()
        self.assertFalse(d2.called)
        self.clock.advance(1)
        self.assertTrue(d1.called)
        self.assertTrue(d2.called)

    def test_stop_and_restart(self):
        """If the method is immediately restarted from a callback on a stop Deferred,
        the polling continues with the new start time."""
        self.duration = 6
        self.poll.start(interval=10)
        self.clock.advance(10)
        self.assertTrue(self.running)
        d = self.poll.stop()
        d.addCallback(lambda _: self.poll.start(interval=10))
        self.assertFalse(d.called)  # not stopped yet
        self.clock.advance(6)
        self.assertFalse(self.running)
        self.assertTrue(d.called)
        self.clock.advance(10)
        self.assertEqual(self.clock.seconds(), 26)
        self.assertTrue(self.running)

    def test_long_method(self):
        """If the method takes more than INTERVAL seconds to execute, then it
        is re-invoked at the next multiple of INTERVAL seconds"""

        self.duration = 4
        self.poll.start(interval=3, now=True)
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
            while self.clock.seconds() < secs:
                self.clock.advance(1)
            self.assertEqual(self.running, running)
            self.assertEqual(self.calls, calls)
