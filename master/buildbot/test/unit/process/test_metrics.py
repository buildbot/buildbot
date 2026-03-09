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

from __future__ import annotations

import gc
import sys
from typing import TYPE_CHECKING
from typing import Any
from unittest import skipIf

from twisted.internet import defer
from twisted.internet import task
from twisted.trial import unittest

from buildbot.process import metrics
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class TestMetricBase(TestReactorMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.observer = metrics.MetricLogObserver()
        self.observer.parent = self.master = yield fakemaster.make_master(self)
        self.master.config.metrics = {"log_interval": 0, "periodic_interval": 0}
        self.observer._reactor = self.reactor
        self.observer.startService()
        self.observer.reconfigServiceWithBuildbotConfig(self.master.config)

        @defer.inlineCallbacks
        def cleanup() -> InlineCallbacksType[None]:
            if self.observer.running:
                yield self.observer.stopService()  # type: ignore[func-returns-value]

        self.addCleanup(cleanup)


class TestMetricCountEvent(TestMetricBase):
    def testIncrement(self) -> None:
        metrics.MetricCountEvent.log('num_widgets', 1)
        report = self.observer.asDict()
        self.assertEqual(report['counters']['num_widgets'], 1)

        metrics.MetricCountEvent.log('num_widgets', 1)
        report = self.observer.asDict()
        self.assertEqual(report['counters']['num_widgets'], 2)

    def testDecrement(self) -> None:
        metrics.MetricCountEvent.log('num_widgets', 1)
        report = self.observer.asDict()
        self.assertEqual(report['counters']['num_widgets'], 1)

        metrics.MetricCountEvent.log('num_widgets', -1)
        report = self.observer.asDict()
        self.assertEqual(report['counters']['num_widgets'], 0)

    def testAbsolute(self) -> None:
        metrics.MetricCountEvent.log('num_widgets', 10, absolute=True)
        report = self.observer.asDict()
        self.assertEqual(report['counters']['num_widgets'], 10)

    def testCountMethod(self) -> None:
        @metrics.countMethod('foo_called')
        def foo() -> str:
            return "foo!"

        for _ in range(10):
            foo()
        report = self.observer.asDict()
        self.assertEqual(report['counters']['foo_called'], 10)


class TestMetricTimeEvent(TestMetricBase):
    def testManualEvent(self) -> None:
        metrics.MetricTimeEvent.log('foo_time', 0.001)
        report = self.observer.asDict()
        self.assertEqual(report['timers']['foo_time'], 0.001)

    def testTimer(self) -> None:
        clock = task.Clock()
        t = metrics.Timer('foo_time')
        t._reactor = clock  # type: ignore[assignment]
        t.start()

        clock.advance(5)
        t.stop()

        report = self.observer.asDict()
        self.assertEqual(report['timers']['foo_time'], 5)

    def testStartStopDecorators(self) -> None:
        clock = task.Clock()
        t = metrics.Timer('foo_time')
        t._reactor = clock  # type: ignore[assignment]

        @t.startTimer
        def foo() -> str:
            clock.advance(5)
            return "foo!"

        @t.stopTimer
        def bar() -> str:
            clock.advance(5)
            return "bar!"

        foo()
        bar()
        report = self.observer.asDict()
        self.assertEqual(report['timers']['foo_time'], 10)

    def testTimeMethod(self) -> None:
        clock = task.Clock()

        @metrics.timeMethod('foo_time', _reactor=clock)  # type: ignore[arg-type]
        def foo() -> str:
            clock.advance(5)
            return "foo!"

        foo()
        report = self.observer.asDict()
        self.assertEqual(report['timers']['foo_time'], 5)

    def testAverages(self) -> None:
        data = list(range(10))
        for i in data:
            metrics.MetricTimeEvent.log('foo_time', i)
        report = self.observer.asDict()
        self.assertEqual(report['timers']['foo_time'], sum(data) / float(len(data)))


class TestPeriodicChecks(TestMetricBase):
    def testPeriodicCheck(self) -> None:
        # fake out that there's no garbage (since we can't rely on Python
        # not having any garbage while running tests)
        self.patch(gc, 'garbage', [])

        clock = task.Clock()
        metrics.periodicCheck(_reactor=clock)  # type: ignore[arg-type]
        clock.pump([0.1, 0.1, 0.1])

        # We should have 0 reactor delay since we're using a fake clock
        report = self.observer.asDict()
        self.assertEqual(report['timers']['reactorDelay'], 0)
        self.assertEqual(report['counters']['gc.garbage'], 0)
        self.assertEqual(report['alarms']['gc.garbage'][0], 'OK')

    def testUncollectable(self) -> None:
        # make some fake garbage
        self.patch(gc, 'garbage', [1, 2])

        clock = task.Clock()
        metrics.periodicCheck(_reactor=clock)  # type: ignore[arg-type]
        clock.pump([0.1, 0.1, 0.1])

        # We should have 0 reactor delay since we're using a fake clock
        report = self.observer.asDict()
        self.assertEqual(report['timers']['reactorDelay'], 0)
        self.assertEqual(report['counters']['gc.garbage'], 2)
        self.assertEqual(report['alarms']['gc.garbage'][0], 'WARN')

    @skipIf(
        sys.platform != 'linux',
        "only available on linux platforms",
    )
    def testGetRSS(self) -> None:
        self.assertTrue(metrics._get_rss() > 0)


class TestReconfig(TestMetricBase):
    def testReconfig(self) -> None:
        observer = self.observer
        new_config = self.master.config

        # starts up without running tasks
        self.assertEqual(observer.log_task, None)
        self.assertEqual(observer.periodic_task, None)

        # enable log_interval
        new_config.metrics = {"log_interval": 10, "periodic_interval": 0}
        observer.reconfigServiceWithBuildbotConfig(new_config)
        self.assertTrue(observer.log_task)
        self.assertEqual(observer.periodic_task, None)

        # disable that and enable periodic_interval
        new_config.metrics = {"periodic_interval": 10, "log_interval": 0}
        observer.reconfigServiceWithBuildbotConfig(new_config)
        self.assertTrue(observer.periodic_task)
        self.assertEqual(observer.log_task, None)

        # Make the periodic check run
        self.reactor.pump([0.1])

        # disable the whole listener
        new_config.metrics = None
        observer.reconfigServiceWithBuildbotConfig(new_config)
        self.assertFalse(observer.enabled)
        self.assertEqual(observer.log_task, None)
        self.assertEqual(observer.periodic_task, None)

        # disable both
        new_config.metrics = {"periodic_interval": 0, "log_interval": 0}
        observer.reconfigServiceWithBuildbotConfig(new_config)
        self.assertEqual(observer.log_task, None)
        self.assertEqual(observer.periodic_task, None)

        # enable both
        new_config.metrics = {"periodic_interval": 10, "log_interval": 10}
        observer.reconfigServiceWithBuildbotConfig(new_config)
        self.assertTrue(observer.log_task)
        self.assertTrue(observer.periodic_task)

        # (service will be stopped by tearDown)


class _LogObserver:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def gotEvent(self, event: dict[str, Any]) -> None:
        self.events.append(event)


class TestReports(unittest.TestCase):
    def testMetricCountReport(self) -> None:
        handler = metrics.MetricCountHandler(None)  # type: ignore[arg-type]
        handler.handle({}, metrics.MetricCountEvent('num_foo', 1))

        self.assertEqual("Counter num_foo: 1", handler.report())
        self.assertEqual({"counters": {"num_foo": 1}}, handler.asDict())

    def testMetricTimeReport(self) -> None:
        handler = metrics.MetricTimeHandler(None)  # type: ignore[arg-type]
        handler.handle({}, metrics.MetricTimeEvent('time_foo', 1))

        self.assertEqual("Timer time_foo: 1", handler.report())
        self.assertEqual({"timers": {"time_foo": 1}}, handler.asDict())

    def testMetricAlarmReport(self) -> None:
        handler = metrics.MetricAlarmHandler(None)  # type: ignore[arg-type]
        handler.handle(
            {}, metrics.MetricAlarmEvent('alarm_foo', msg='Uh oh', level=metrics.ALARM_WARN)
        )

        self.assertEqual("WARN alarm_foo: Uh oh", handler.report())
        self.assertEqual({"alarms": {"alarm_foo": ("WARN", "Uh oh")}}, handler.asDict())
