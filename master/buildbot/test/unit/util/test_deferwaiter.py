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

from buildbot.test.reactor import TestReactorMixin
from buildbot.util import asyncSleep
from buildbot.util.deferwaiter import DeferWaiter
from buildbot.util.deferwaiter import NonRepeatedActionHandler
from buildbot.util.deferwaiter import RepeatedActionHandler


class TestException(Exception):
    pass


class WaiterTests(unittest.TestCase):
    def test_add_deferred_called(self):
        w = DeferWaiter()
        w.add(defer.succeed(None))
        self.assertFalse(w.has_waited())

        d = w.wait()
        self.assertTrue(d.called)

    def test_add_non_deferred(self):
        w = DeferWaiter()
        w.add(2)
        self.assertFalse(w.has_waited())

        d = w.wait()
        self.assertTrue(d.called)

    def test_add_deferred_not_called_and_call_later(self):
        w = DeferWaiter()

        d1 = defer.Deferred()
        w.add(d1)
        self.assertTrue(w.has_waited())

        d = w.wait()
        self.assertFalse(d.called)

        d1.callback(None)
        self.assertFalse(w.has_waited())
        self.assertTrue(d.called)

    @defer.inlineCallbacks
    def test_passes_result(self):
        w = DeferWaiter()

        d1 = defer.Deferred()
        w.add(d1)

        d1.callback(123)
        res = yield d1
        self.assertEqual(res, 123)

        d = w.wait()
        self.assertTrue(d.called)


class RepeatedActionHandlerTests(unittest.TestCase, TestReactorMixin):
    def setUp(self):
        self.setup_test_reactor()

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
    def test_runs_action(self, name, timer_after_action):
        w = DeferWaiter()
        times = []

        def action():
            times.append(round(self.reactor.seconds(), 1))

        h = RepeatedActionHandler(
            self.reactor, w, 1, action, start_timer_after_action_completes=timer_after_action
        )
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

        h = RepeatedActionHandler(
            self.reactor, w, 1, action, start_timer_after_action_completes=timer_after_action
        )
        h.start()
        self.reactor.pump([0.1] * 35)

        self.assertEqual(times, [1.1, 2.1, 3.1])

        h.stop()
        d = w.wait()
        self.assertTrue(d.called)

        self.flushLoggedErrors(TestException)

        yield d

    @parameterized.expand([
        ('after_action', True),
        ('before_action', False),
    ])
    @defer.inlineCallbacks
    def test_runs_action_with_delay(self, name, timer_after_action):
        w = DeferWaiter()
        times = []

        def action():
            times.append(self.reactor.seconds())

        h = RepeatedActionHandler(
            self.reactor, w, 10, action, start_timer_after_action_completes=timer_after_action
        )
        h.start()
        self.reactor.pump([1] * 15)
        h.delay()
        self.reactor.pump([1] * 35)

        self.assertEqual(times, [10, 25, 35, 45])

        h.stop()
        d = w.wait()
        self.assertTrue(d.called)
        yield d

    @parameterized.expand([
        ('after_action', True),
        ('before_action', False),
    ])
    @defer.inlineCallbacks
    def test_runs_action_with_force(self, name, timer_after_action):
        w = DeferWaiter()
        times = []

        def action():
            times.append(self.reactor.seconds())

        h = RepeatedActionHandler(
            self.reactor, w, 10, action, start_timer_after_action_completes=timer_after_action
        )
        h.start()
        self.reactor.pump([1] * 15)
        h.force()
        self.reactor.pump([1] * 35)

        self.assertEqual(times, [10, 15, 25, 35, 45])

        h.stop()
        d = w.wait()
        self.assertTrue(d.called)
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
        h.set_interval(2)
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
    def test_runs_long_action(self, name, timer_after_action, expected_times):
        w = DeferWaiter()
        times = []

        @defer.inlineCallbacks
        def action():
            times.append(round(self.reactor.seconds(), 1))
            yield asyncSleep(0.5, reactor=self.reactor)

        h = RepeatedActionHandler(
            self.reactor, w, 1, action, start_timer_after_action_completes=timer_after_action
        )
        h.start()
        self.reactor.pump([0.1] * 47)

        self.assertEqual(times, expected_times)

        h.stop()
        d = w.wait()
        self.assertTrue(d.called)
        yield d

    @parameterized.expand([
        ('after_action', True, [10, 25, 47, 62]),
        ('before_action', False, [10, 20, 30, 47, 57, 67]),
    ])
    @defer.inlineCallbacks
    def test_runs_long_action_with_delay(self, name, timer_after_action, expected_times):
        w = DeferWaiter()
        times = []

        @defer.inlineCallbacks
        def action():
            times.append(self.reactor.seconds())
            yield asyncSleep(5, reactor=self.reactor)

        h = RepeatedActionHandler(
            self.reactor, w, 10, action, start_timer_after_action_completes=timer_after_action
        )
        h.start()
        self.reactor.pump([1] * 37)
        h.delay()
        self.reactor.pump([1] * 39)

        self.assertEqual(times, expected_times)

        h.stop()
        d = w.wait()
        self.assertTrue(d.called)
        yield d

    @parameterized.expand([
        ('after_action', True, [10, 25, 40]),
        ('before_action', False, [10, 22, 32, 42]),
    ])
    @defer.inlineCallbacks
    def test_runs_long_action_with_delay_when_running(
        self, name, timer_after_action, expected_times
    ):
        w = DeferWaiter()
        times = []

        @defer.inlineCallbacks
        def action():
            times.append(self.reactor.seconds())
            yield asyncSleep(5, reactor=self.reactor)

        h = RepeatedActionHandler(
            self.reactor, w, 10, action, start_timer_after_action_completes=timer_after_action
        )
        h.start()
        self.reactor.pump([1] * 12)
        h.delay()
        self.reactor.pump([1] * 39)

        self.assertEqual(times, expected_times)

        h.stop()
        d = w.wait()
        self.assertTrue(d.called)
        yield d

    @parameterized.expand([
        ('after_action', True, [10, 25, 37, 52, 67]),
        ('before_action', False, [10, 20, 30, 37, 47, 57, 67]),
    ])
    @defer.inlineCallbacks
    def test_runs_long_action_with_force(self, name, timer_after_action, expected_times):
        w = DeferWaiter()
        times = []

        @defer.inlineCallbacks
        def action():
            times.append(self.reactor.seconds())
            yield asyncSleep(5, reactor=self.reactor)

        h = RepeatedActionHandler(
            self.reactor, w, 10, action, start_timer_after_action_completes=timer_after_action
        )
        h.start()
        self.reactor.pump([1] * 37)
        h.force()
        self.reactor.pump([1] * 39)

        self.assertEqual(times, expected_times)

        h.stop()
        d = w.wait()
        self.assertTrue(d.called)
        yield d

    @parameterized.expand([
        ('after_action', True, [10, 25, 40]),
        ('before_action', False, [10, 20, 30, 40]),
    ])
    @defer.inlineCallbacks
    def test_runs_long_action_with_force_when_running(
        self, name, timer_after_action, expected_times
    ):
        w = DeferWaiter()
        times = []

        @defer.inlineCallbacks
        def action():
            times.append(self.reactor.seconds())
            yield asyncSleep(5, reactor=self.reactor)

        h = RepeatedActionHandler(
            self.reactor, w, 10, action, start_timer_after_action_completes=timer_after_action
        )
        h.start()
        self.reactor.pump([1] * 12)
        h.force()
        self.reactor.pump([1] * 37)

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

        h = RepeatedActionHandler(
            self.reactor, w, 1, action, start_timer_after_action_completes=timer_after_action
        )
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


class NonRepeatedActionHandlerTests(unittest.TestCase, TestReactorMixin):
    def setUp(self):
        self.setup_test_reactor()

    @defer.inlineCallbacks
    def test_does_not_add_action_on_start(self):
        w = DeferWaiter()
        times = []

        def action():
            times.append(self.reactor.seconds())

        h = NonRepeatedActionHandler(self.reactor, w, action)

        self.reactor.advance(20)

        h.stop()
        self.assertEqual(len(times), 0)
        d = w.wait()
        self.assertTrue(d.called)
        yield d

    @defer.inlineCallbacks
    def test_action(self):
        w = DeferWaiter()
        times = []

        def action():
            times.append(self.reactor.seconds())

        h = NonRepeatedActionHandler(self.reactor, w, action)
        self.reactor.pump([1] * 10)
        h.schedule(10)
        self.reactor.pump([1] * 30)

        self.assertEqual(times, [20])

        h.stop()
        d = w.wait()
        self.assertTrue(d.called)
        yield d

    @parameterized.expand([
        ("invoke_again_if_running", True),
        ('dont_invoke_again_if_running', False),
    ])
    @defer.inlineCallbacks
    def test_actions_when_multiple_schedule(self, name, invoke_again_if_running):
        w = DeferWaiter()
        times = []

        def action():
            times.append(self.reactor.seconds())

        h = NonRepeatedActionHandler(self.reactor, w, action)
        self.reactor.pump([1] * 10)
        h.schedule(10, invoke_again_if_running=invoke_again_if_running)
        self.reactor.pump([1] * 2)
        h.schedule(10, invoke_again_if_running=invoke_again_if_running)
        self.reactor.pump([1] * 30)

        self.assertEqual(times, [20])

        h.stop()
        d = w.wait()
        self.assertTrue(d.called)
        yield d

    @parameterized.expand([
        ("invoke_again_if_running", True),
        ('dont_invoke_again_if_running', False),
    ])
    @defer.inlineCallbacks
    def test_actions_when_schedule_and_force(self, name, invoke_again_if_running):
        w = DeferWaiter()
        times = []

        def action():
            times.append(self.reactor.seconds())

        h = NonRepeatedActionHandler(self.reactor, w, action)
        self.reactor.pump([1] * 10)
        h.schedule(10, invoke_again_if_running=invoke_again_if_running)
        self.reactor.pump([1] * 2)
        h.force(invoke_again_if_running=invoke_again_if_running)
        self.reactor.pump([1] * 30)

        self.assertEqual(times, [12])

        h.stop()
        d = w.wait()
        self.assertTrue(d.called)
        yield d

    @parameterized.expand([
        ("invoke_again_if_running", True, [20, 32]),
        ('dont_invoke_again_if_running', False, [20]),
    ])
    @defer.inlineCallbacks
    def test_long_actions_when_2_schedule(self, name, invoke_again_if_running, expected_times):
        w = DeferWaiter()
        times = []

        @defer.inlineCallbacks
        def action():
            times.append(self.reactor.seconds())
            yield asyncSleep(5, reactor=self.reactor)

        h = NonRepeatedActionHandler(self.reactor, w, action)
        self.reactor.pump([1] * 10)
        h.schedule(10, invoke_again_if_running=invoke_again_if_running)
        self.reactor.pump([1] * 12)
        h.schedule(10, invoke_again_if_running=invoke_again_if_running)
        self.reactor.pump([1] * 30)

        self.assertEqual(times, expected_times)

        h.stop()
        d = w.wait()
        self.assertTrue(d.called)
        yield d

    @parameterized.expand([
        ("invoke_again_if_running", True, [10, 15]),
        ('dont_invoke_again_if_running', False, [10]),
    ])
    @defer.inlineCallbacks
    def test_long_actions_when_2_force(self, name, invoke_again_if_running, expected_times):
        w = DeferWaiter()
        times = []

        @defer.inlineCallbacks
        def action():
            times.append(self.reactor.seconds())
            yield asyncSleep(5, reactor=self.reactor)

        h = NonRepeatedActionHandler(self.reactor, w, action)
        self.reactor.pump([1] * 10)
        h.force(invoke_again_if_running=invoke_again_if_running)
        self.reactor.pump([1] * 2)
        h.force(invoke_again_if_running=invoke_again_if_running)
        self.reactor.pump([1] * 30)

        self.assertEqual(times, expected_times)

        h.stop()
        d = w.wait()
        self.assertTrue(d.called)
        yield d

    @parameterized.expand([
        ("invoke_again_if_running", True, [10, 15]),
        ('dont_invoke_again_if_running', False, [10]),
    ])
    @defer.inlineCallbacks
    def test_long_actions_when_3_force(self, name, invoke_again_if_running, expected_times):
        w = DeferWaiter()
        times = []

        @defer.inlineCallbacks
        def action():
            times.append(self.reactor.seconds())
            yield asyncSleep(5, reactor=self.reactor)

        h = NonRepeatedActionHandler(self.reactor, w, action)
        self.reactor.pump([1] * 10)
        h.force(invoke_again_if_running=invoke_again_if_running)
        self.reactor.pump([1] * 2)
        h.force(invoke_again_if_running=invoke_again_if_running)
        self.reactor.pump([1] * 2)
        h.force(invoke_again_if_running=invoke_again_if_running)
        self.reactor.pump([1] * 30)

        self.assertEqual(times, expected_times)

        h.stop()
        d = w.wait()
        self.assertTrue(d.called)
        yield d

    @parameterized.expand([
        ("invoke_again_if_running", True, [20, 25]),
        ('dont_invoke_again_if_running', False, [20]),
    ])
    @defer.inlineCallbacks
    def test_long_actions_when_schedule_and_force(
        self, name, invoke_again_if_running, expected_times
    ):
        w = DeferWaiter()
        times = []

        @defer.inlineCallbacks
        def action():
            times.append(self.reactor.seconds())
            yield asyncSleep(5, reactor=self.reactor)

        h = NonRepeatedActionHandler(self.reactor, w, action)
        self.reactor.pump([1] * 10)
        h.schedule(10, invoke_again_if_running=invoke_again_if_running)
        self.reactor.pump([1] * 12)
        h.force(invoke_again_if_running=invoke_again_if_running)
        self.reactor.pump([1] * 30)

        self.assertEqual(times, expected_times)

        h.stop()
        d = w.wait()
        self.assertTrue(d.called)
        yield d

    @parameterized.expand([
        ("invoke_again_if_running", True, [10, 22]),
        ('dont_invoke_again_if_running', False, [10]),
    ])
    @defer.inlineCallbacks
    def test_long_actions_when_force_and_schedule(
        self, name, invoke_again_if_running, expected_times
    ):
        w = DeferWaiter()
        times = []

        @defer.inlineCallbacks
        def action():
            times.append(self.reactor.seconds())
            yield asyncSleep(5, reactor=self.reactor)

        h = NonRepeatedActionHandler(self.reactor, w, action)
        self.reactor.pump([1] * 10)
        h.force(invoke_again_if_running=invoke_again_if_running)
        self.reactor.pump([1] * 2)
        h.schedule(10, invoke_again_if_running=invoke_again_if_running)
        self.reactor.pump([1] * 30)

        self.assertEqual(times, expected_times)

        h.stop()
        d = w.wait()
        self.assertTrue(d.called)
        yield d
