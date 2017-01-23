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
from __future__ import print_function
from future.builtins import range
from future.utils import lrange

import gc
import sys

from twisted.internet import task
from twisted.trial import unittest

from buildbot.process import metrics
from buildbot.test.fake import fakemaster


class TestMetricBase(unittest.TestCase):

    def setUp(self):
        self.clock = task.Clock()
        self.observer = metrics.MetricLogObserver()
        self.observer.parent = self.master = fakemaster.make_master()
        self.master.config.metrics = dict(log_interval=0, periodic_interval=0)
        self.observer._reactor = self.clock
        self.observer.startService()
        self.observer.reconfigServiceWithBuildbotConfig(self.master.config)

    def tearDown(self):
        if self.observer.running:
            self.observer.stopService()


class TestMetricCountEvent(TestMetricBase):

    def testIncrement(self):
        metrics.MetricCountEvent.log('num_widgets', 1)
        report = self.observer.asDict()
        self.assertEqual(report['counters']['num_widgets'], 1)

        metrics.MetricCountEvent.log('num_widgets', 1)
        report = self.observer.asDict()
        self.assertEqual(report['counters']['num_widgets'], 2)

    def testDecrement(self):
        metrics.MetricCountEvent.log('num_widgets', 1)
        report = self.observer.asDict()
        self.assertEqual(report['counters']['num_widgets'], 1)

        metrics.MetricCountEvent.log('num_widgets', -1)
        report = self.observer.asDict()
        self.assertEqual(report['counters']['num_widgets'], 0)

    def testAbsolute(self):
        metrics.MetricCountEvent.log('num_widgets', 10, absolute=True)
        report = self.observer.asDict()
        self.assertEqual(report['counters']['num_widgets'], 10)

    def testCountMethod(self):
        @metrics.countMethod('foo_called')
        def foo():
            return "foo!"

        for i in range(10):
            foo()
        report = self.observer.asDict()
        self.assertEqual(report['counters']['foo_called'], 10)


class TestMetricTimeEvent(TestMetricBase):

    def testManualEvent(self):
        metrics.MetricTimeEvent.log('foo_time', 0.001)
        report = self.observer.asDict()
        self.assertEqual(report['timers']['foo_time'], 0.001)

    def testTimer(self):
        clock = task.Clock()
        t = metrics.Timer('foo_time')
        t._reactor = clock
        t.start()

        clock.advance(5)
        t.stop()

        report = self.observer.asDict()
        self.assertEqual(report['timers']['foo_time'], 5)

    def testStartStopDecorators(self):
        clock = task.Clock()
        t = metrics.Timer('foo_time')
        t._reactor = clock

        @t.startTimer
        def foo():
            clock.advance(5)
            return "foo!"

        @t.stopTimer
        def bar():
            clock.advance(5)
            return "bar!"

        foo()
        bar()
        report = self.observer.asDict()
        self.assertEqual(report['timers']['foo_time'], 10)

    def testTimeMethod(self):
        clock = task.Clock()

        @metrics.timeMethod('foo_time', _reactor=clock)
        def foo():
            clock.advance(5)
            return "foo!"
        foo()
        report = self.observer.asDict()
        self.assertEqual(report['timers']['foo_time'], 5)

    def testAverages(self):
        data = lrange(10)
        for i in data:
            metrics.MetricTimeEvent.log('foo_time', i)
        report = self.observer.asDict()
        self.assertEqual(
            report['timers']['foo_time'], sum(data) / float(len(data)))


class TestPeriodicChecks(TestMetricBase):

    def testPeriodicCheck(self):
        # fake out that there's no garbage (since we can't rely on Python
        # not having any garbage while running tests)
        self.patch(gc, 'garbage', [])

        clock = task.Clock()
        metrics.periodicCheck(_reactor=clock)
        clock.pump([0.1, 0.1, 0.1])

        # We should have 0 reactor delay since we're using a fake clock
        report = self.observer.asDict()
        self.assertEqual(report['timers']['reactorDelay'], 0)
        self.assertEqual(report['counters']['gc.garbage'], 0)
        self.assertEqual(report['alarms']['gc.garbage'][0], 'OK')

    def testUncollectable(self):
        # make some fake garbage
        self.patch(gc, 'garbage', [1, 2])

        clock = task.Clock()
        metrics.periodicCheck(_reactor=clock)
        clock.pump([0.1, 0.1, 0.1])

        # We should have 0 reactor delay since we're using a fake clock
        report = self.observer.asDict()
        self.assertEqual(report['timers']['reactorDelay'], 0)
        self.assertEqual(report['counters']['gc.garbage'], 2)
        self.assertEqual(report['alarms']['gc.garbage'][0], 'WARN')

    def testGetRSS(self):
        self.assertTrue(metrics._get_rss() > 0)
    if sys.platform != 'linux2':
        testGetRSS.skip = "only available on linux2 platforms"


class TestReconfig(TestMetricBase):

    def testReconfig(self):
        observer = self.observer
        new_config = self.master.config

        # starts up without running tasks
        self.assertEqual(observer.log_task, None)
        self.assertEqual(observer.periodic_task, None)

        # enable log_interval
        new_config.metrics = dict(log_interval=10, periodic_interval=0)
        observer.reconfigServiceWithBuildbotConfig(new_config)
        self.assertTrue(observer.log_task)
        self.assertEqual(observer.periodic_task, None)

        # disable that and enable periodic_interval
        new_config.metrics = dict(periodic_interval=10, log_interval=0)
        observer.reconfigServiceWithBuildbotConfig(new_config)
        self.assertTrue(observer.periodic_task)
        self.assertEqual(observer.log_task, None)

        # Make the periodic check run
        self.clock.pump([0.1])

        # disable the whole listener
        new_config.metrics = None
        observer.reconfigServiceWithBuildbotConfig(new_config)
        self.assertFalse(observer.enabled)
        self.assertEqual(observer.log_task, None)
        self.assertEqual(observer.periodic_task, None)

        # disable both
        new_config.metrics = dict(periodic_interval=0, log_interval=0)
        observer.reconfigServiceWithBuildbotConfig(new_config)
        self.assertEqual(observer.log_task, None)
        self.assertEqual(observer.periodic_task, None)

        # enable both
        new_config.metrics = dict(periodic_interval=10, log_interval=10)
        observer.reconfigServiceWithBuildbotConfig(new_config)
        self.assertTrue(observer.log_task)
        self.assertTrue(observer.periodic_task)

        # (service will be stopped by tearDown)


class _LogObserver:

    def __init__(self):
        self.events = []

    def gotEvent(self, event):
        self.events.append(event)


class TestReports(unittest.TestCase):

    def testMetricCountReport(self):
        handler = metrics.MetricCountHandler(None)
        handler.handle({}, metrics.MetricCountEvent('num_foo', 1))

        self.assertEqual("Counter num_foo: 1", handler.report())
        self.assertEqual({"counters": {"num_foo": 1}}, handler.asDict())

    def testMetricTimeReport(self):
        handler = metrics.MetricTimeHandler(None)
        handler.handle({}, metrics.MetricTimeEvent('time_foo', 1))

        self.assertEqual("Timer time_foo: 1", handler.report())
        self.assertEqual({"timers": {"time_foo": 1}}, handler.asDict())

    def testMetricAlarmReport(self):
        handler = metrics.MetricAlarmHandler(None)
        handler.handle({}, metrics.MetricAlarmEvent(
            'alarm_foo', msg='Uh oh', level=metrics.ALARM_WARN))

        self.assertEqual("WARN alarm_foo: Uh oh", handler.report())
        self.assertEqual(
            {"alarms": {"alarm_foo": ("WARN", "Uh oh")}}, handler.asDict())
