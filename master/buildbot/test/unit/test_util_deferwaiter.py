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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.util.misc import TestReactorMixin
from buildbot.util import asyncSleep
from buildbot.util.deferwaiter import DeferWaiter
from buildbot.util.deferwaiter import RepeatedActionHandler


class TestException(Exception):
    pass


class WaiterTests(unittest.TestCase):

    def test_add_deferred_called(self):
        w = DeferWaiter()
        w.add(defer.succeed(None))
        d = w.wait()
        self.assertTrue(d.called)

    def test_add_non_deferred(self):
        w = DeferWaiter()
        w.add(2)
        d = w.wait()
        self.assertTrue(d.called)

    def test_add_deferred_not_called_and_call_later(self):
        w = DeferWaiter()

        d1 = defer.Deferred()
        w.add(d1)

        d = w.wait()
        self.assertFalse(d.called)

        d1.callback(None)
        self.assertTrue(d.called)


class RepeatedActionHandlerTests(unittest.TestCase, TestReactorMixin):

    def setUp(self):
        self.setUpTestReactor()

    @defer.inlineCallbacks
    def test_does_not_add_action_on_start(self):
        w = DeferWaiter()
        times = []

        def action():
            times.append(self.reactor.seconds())

        h = RepeatedActionHandler(self.reactor, w, 1, action)

        self.reactor.advance(2)

        h.stop()
        self.assertEqual(len(times), 0)
        d = w.wait()
        self.assertTrue(d.called)
        yield d

    @parameterized.expand([
        ('after_action', True),
        ('before_action', False),
    ])
    @defer.inlineCallbacks
    def test_runs_action_with_timer(self, name, timer_after_action):
        w = DeferWaiter()
        times = []

        def action():
            times.append(round(self.reactor.seconds(), 1))

        h = RepeatedActionHandler(self.reactor, w, 1, action,
                                  start_timer_after_action_completes=timer_after_action)
        h.start()
        self.reactor.pump([0.1] * 35)

        self.assertEqual(times, [1.1, 2.1, 3.1])

        h.stop()
        d = w.wait()
        self.assertTrue(d.called)
        yield d

    @parameterized.expand([
        ('after_action', True),
        ('before_action', False),
    ])
    @defer.inlineCallbacks
    def test_runs_action_after_exception_with_timer(self, name, timer_after_action):
        w = DeferWaiter()
        times = []

        def action():
            times.append(round(self.reactor.seconds(), 1))
            if len(times) == 2:
                raise TestException()

        h = RepeatedActionHandler(self.reactor, w, 1, action,
                                  start_timer_after_action_completes=timer_after_action)
        h.start()
        self.reactor.pump([0.1] * 35)

        self.assertEqual(times, [1.1, 2.1, 3.1])

        h.stop()
        d = w.wait()
        self.assertTrue(d.called)

        self.flushLoggedErrors(TestException)

        yield d

    @defer.inlineCallbacks
    def test_ignores_duplicate_start_or_stop(self):
        w = DeferWaiter()
        times = []

        def action():
            times.append(round(self.reactor.seconds(), 1))

        h = RepeatedActionHandler(self.reactor, w, 1, action)
        h.start()
        h.start()
        self.reactor.pump([0.1] * 35)

        self.assertEqual(times, [1.1, 2.1, 3.1])

        h.stop()
        h.stop()
        d = w.wait()
        self.assertTrue(d.called)
        yield d

    @defer.inlineCallbacks
    def test_can_update_interval(self):
        w = DeferWaiter()
        times = []

        def action():
            times.append(round(self.reactor.seconds(), 1))

        h = RepeatedActionHandler(self.reactor, w, 1, action)
        h.start()
        self.reactor.pump([0.1] * 15)
        h.setInterval(2)
        self.reactor.pump([0.1] * 50)

        self.assertEqual(times, [1.1, 2.1, 4.1, 6.2])

        h.stop()
        d = w.wait()
        self.assertTrue(d.called)
        yield d

    @parameterized.expand([
        ('after_action', True, [1.1, 2.6, 4.1]),
        ('before_action', False, [1.1, 2.1, 3.1, 4.1]),
    ])
    @defer.inlineCallbacks
    def test_runs_action_with_timer_delay(self, name, timer_after_action, expected_times):
        w = DeferWaiter()
        times = []

        @defer.inlineCallbacks
        def action():
            times.append(round(self.reactor.seconds(), 1))
            yield asyncSleep(0.5, reactor=self.reactor)

        h = RepeatedActionHandler(self.reactor, w, 1, action,
                                  start_timer_after_action_completes=timer_after_action)
        h.start()
        self.reactor.pump([0.1] * 47)

        self.assertEqual(times, expected_times)

        h.stop()
        d = w.wait()
        self.assertTrue(d.called)
        yield d

    @parameterized.expand([
        ('after_action', True),
        ('before_action', False),
    ])
    @defer.inlineCallbacks
    def test_waiter_waits_for_action_timer_starts(self, name, timer_after_action):

        w = DeferWaiter()
        times = []

        @defer.inlineCallbacks
        def action():
            times.append(round(self.reactor.seconds(), 1))
            yield asyncSleep(0.5, reactor=self.reactor)

        h = RepeatedActionHandler(self.reactor, w, 1, action,
                                  start_timer_after_action_completes=timer_after_action)
        h.start()
        self.reactor.pump([0.1] * 12)

        self.assertEqual(times, [1.1])

        d = w.wait()
        self.assertFalse(d.called)
        h.stop()
        self.assertFalse(d.called)

        self.reactor.pump([0.1] * 5)  # action started on 1.1, will end at 1.6
        self.assertTrue(d.called)
        yield d
