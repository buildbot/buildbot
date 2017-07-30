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
r"""
Buildbot metrics module

Keeps track of counts and timings of various internal buildbot
activities.

Basic architecture:

    MetricEvent.log(...)
          ||
          \/
    MetricLogObserver
          ||
          \/
    MetricHandler
          ||
          \/
    MetricWatcher
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from future.utils import iteritems
from future.utils import lrange

import gc
import os
import sys
from collections import defaultdict
from collections import deque

from twisted.application import service
from twisted.internet import reactor
from twisted.internet.task import LoopingCall
from twisted.python import log

from buildbot import util
from buildbot.util import service as util_service

# Make use of the resource module if we can
try:
    import resource
    assert resource
except ImportError:
    resource = None


class MetricEvent(object):

    @classmethod
    def log(cls, *args, **kwargs):
        log.msg(metric=cls(*args, **kwargs))


class MetricCountEvent(MetricEvent):

    def __init__(self, counter, count=1, absolute=False):
        self.counter = counter
        self.count = count
        self.absolute = absolute


class MetricTimeEvent(MetricEvent):

    def __init__(self, timer, elapsed):
        self.timer = timer
        self.elapsed = elapsed


ALARM_OK, ALARM_WARN, ALARM_CRIT = lrange(3)
ALARM_TEXT = ["OK", "WARN", "CRIT"]


class MetricAlarmEvent(MetricEvent):

    def __init__(self, alarm, msg=None, level=ALARM_OK):
        self.alarm = alarm
        self.level = level
        self.msg = msg


def countMethod(counter):
    def decorator(func):
        def wrapper(*args, **kwargs):
            MetricCountEvent.log(counter=counter)
            return func(*args, **kwargs)
        return wrapper
    return decorator


class Timer(object):
    # For testing
    _reactor = None

    def __init__(self, name):
        self.name = name
        self.started = None

    def startTimer(self, func):
        def wrapper(*args, **kwargs):
            self.start()
            return func(*args, **kwargs)
        return wrapper

    def stopTimer(self, func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            finally:
                self.stop()
        return wrapper

    def start(self):
        self.started = util.now(self._reactor)

    def stop(self):
        if self.started is not None:
            elapsed = util.now(self._reactor) - self.started
            MetricTimeEvent.log(timer=self.name, elapsed=elapsed)
            self.started = None


def timeMethod(name, _reactor=None):
    def decorator(func):
        t = Timer(name)
        t._reactor = _reactor

        def wrapper(*args, **kwargs):
            t.start()
            try:
                return func(*args, **kwargs)
            finally:
                t.stop()
        return wrapper
    return decorator


class FiniteList(deque):

    def __init__(self, maxlen=10):
        self._maxlen = maxlen
        deque.__init__(self)

    def append(self, o):
        deque.append(self, o)
        if len(self) > self._maxlen:
            self.popleft()


class AveragingFiniteList(FiniteList):

    def __init__(self, maxlen=10):
        FiniteList.__init__(self, maxlen)
        self.average = 0

    def append(self, o):
        FiniteList.append(self, o)
        self._calc()

    def _calc(self):
        if not self:
            self.average = 0
        else:
            self.average = float(sum(self)) / len(self)

        return self.average


class MetricHandler(object):

    def __init__(self, metrics):
        self.metrics = metrics
        self.watchers = []

        self.reset()

    def addWatcher(self, watcher):
        self.watchers.append(watcher)

    def removeWatcher(self, watcher):
        self.watchers.remove(watcher)

    # For subclasses to define
    def reset(self):
        raise NotImplementedError

    def handle(self, eventDict, metric):
        raise NotImplementedError

    def get(self, metric):
        raise NotImplementedError

    def keys(self):
        raise NotImplementedError

    def report(self):
        raise NotImplementedError

    def asDict(self):
        raise NotImplementedError


class MetricCountHandler(MetricHandler):
    _counters = None

    def reset(self):
        self._counters = defaultdict(int)

    def handle(self, eventDict, metric):
        if metric.absolute:
            self._counters[metric.counter] = metric.count
        else:
            self._counters[metric.counter] += metric.count

    def keys(self):
        return list(self._counters)

    def get(self, counter):
        return self._counters[counter]

    def report(self):
        retval = []
        for counter in sorted(self.keys()):
            retval.append("Counter %s: %i" % (counter, self.get(counter)))
        return "\n".join(retval)

    def asDict(self):
        retval = {}
        for counter in sorted(self.keys()):
            retval[counter] = self.get(counter)
        return dict(counters=retval)


class MetricTimeHandler(MetricHandler):
    _timers = None

    def reset(self):
        self._timers = defaultdict(AveragingFiniteList)

    def handle(self, eventDict, metric):
        self._timers[metric.timer].append(metric.elapsed)

    def keys(self):
        return list(self._timers)

    def get(self, timer):
        return self._timers[timer].average

    def report(self):
        retval = []
        for timer in sorted(self.keys()):
            retval.append("Timer %s: %.3g" % (timer, self.get(timer)))
        return "\n".join(retval)

    def asDict(self):
        retval = {}
        for timer in sorted(self.keys()):
            retval[timer] = self.get(timer)
        return dict(timers=retval)


class MetricAlarmHandler(MetricHandler):
    _alarms = None

    def reset(self):
        self._alarms = defaultdict(lambda x: ALARM_OK)

    def handle(self, eventDict, metric):
        self._alarms[metric.alarm] = (metric.level, metric.msg)

    def report(self):
        retval = []
        for alarm, (level, msg) in sorted(self._alarms.items()):
            if msg:
                retval.append("%s %s: %s" % (ALARM_TEXT[level], alarm, msg))
            else:
                retval.append("%s %s" % (ALARM_TEXT[level], alarm))
        return "\n".join(retval)

    def asDict(self):
        retval = {}
        for alarm, (level, msg) in sorted(self._alarms.items()):
            retval[alarm] = (ALARM_TEXT[level], msg)
        return dict(alarms=retval)


class AttachedWorkersWatcher(object):

    def __init__(self, metrics):
        self.metrics = metrics

    def run(self):
        # Check if 'BotMaster.attached_workers' equals
        # 'AbstractWorker.attached_workers'
        h = self.metrics.getHandler(MetricCountEvent)
        if not h:
            log.msg("Couldn't get MetricCountEvent handler")
            MetricAlarmEvent.log('AttachedWorkersWatcher',
                                 msg="Coudln't get MetricCountEvent handler",
                                 level=ALARM_WARN)
            return
        botmaster_count = h.get('BotMaster.attached_workers')
        worker_count = h.get('AbstractWorker.attached_workers')

        # We let these be off by one since they're counted at slightly
        # different times
        if abs(botmaster_count - worker_count) > 1:
            level = ALARM_WARN
        else:
            level = ALARM_OK

        MetricAlarmEvent.log('attached_workers',
                             msg='%s %s' % (botmaster_count, worker_count),
                             level=level)


def _get_rss():
    if sys.platform == 'linux2':
        try:
            with open("/proc/%i/statm" % os.getpid()) as f:
                return int(f.read().split()[1])
        except Exception:
            return 0
    return 0


def periodicCheck(_reactor=reactor):
    try:
        # Measure how much garbage we have
        garbage_count = len(gc.garbage)
        MetricCountEvent.log('gc.garbage', garbage_count, absolute=True)
        if garbage_count == 0:
            level = ALARM_OK
        else:
            level = ALARM_WARN
        MetricAlarmEvent.log('gc.garbage', level=level)

        if resource:
            r = resource.getrusage(resource.RUSAGE_SELF)
            attrs = ['ru_utime', 'ru_stime', 'ru_maxrss', 'ru_ixrss', 'ru_idrss',
                     'ru_isrss', 'ru_minflt', 'ru_majflt', 'ru_nswap',
                     'ru_inblock', 'ru_oublock', 'ru_msgsnd', 'ru_msgrcv',
                     'ru_nsignals', 'ru_nvcsw', 'ru_nivcsw']
            for i, a in enumerate(attrs):
                # Linux versions prior to 2.6.32 didn't report this value, but we
                # can calculate it from /proc/<pid>/statm
                v = r[i]
                if a == 'ru_maxrss' and v == 0:
                    v = _get_rss() * resource.getpagesize() / 1024
                MetricCountEvent.log('resource.%s' % a, v, absolute=True)
            MetricCountEvent.log(
                'resource.pagesize', resource.getpagesize(), absolute=True)
        # Measure the reactor delay
        then = util.now(_reactor)
        dt = 0.1

        def cb():
            now = util.now(_reactor)
            delay = (now - then) - dt
            MetricTimeEvent.log("reactorDelay", delay)
        _reactor.callLater(dt, cb)
    except Exception:
        log.err(None, "while collecting VM metrics")


class MetricLogObserver(util_service.ReconfigurableServiceMixin,
                        service.MultiService):
    _reactor = reactor

    def __init__(self):
        service.MultiService.__init__(self)
        self.setName('metrics')

        self.enabled = False
        self.periodic_task = None
        self.periodic_interval = None
        self.log_task = None
        self.log_interval = None

        # Mapping of metric type to handlers for that type
        self.handlers = {}

        # Register our default handlers
        self.registerHandler(MetricCountEvent, MetricCountHandler(self))
        self.registerHandler(MetricTimeEvent, MetricTimeHandler(self))
        self.registerHandler(MetricAlarmEvent, MetricAlarmHandler(self))

        self.getHandler(MetricCountEvent).addWatcher(
            AttachedWorkersWatcher(self))

    def reconfigServiceWithBuildbotConfig(self, new_config):
        # first, enable or disable
        if new_config.metrics is None:
            self.disable()
        else:
            self.enable()

            metrics_config = new_config.metrics

            # Start up periodic logging
            log_interval = metrics_config.get('log_interval', 60)
            if log_interval != self.log_interval:
                if self.log_task:
                    self.log_task.stop()
                    self.log_task = None
                if log_interval:
                    self.log_task = LoopingCall(self.report)
                    self.log_task.clock = self._reactor
                    self.log_task.start(log_interval)

            # same for the periodic task
            periodic_interval = metrics_config.get('periodic_interval', 10)
            if periodic_interval != self.periodic_interval:
                if self.periodic_task:
                    self.periodic_task.stop()
                    self.periodic_task = None
                if periodic_interval:
                    self.periodic_task = LoopingCall(periodicCheck,
                                                     self._reactor)
                    self.periodic_task.clock = self._reactor
                    self.periodic_task.start(periodic_interval)

        # upcall
        return util_service.ReconfigurableServiceMixin.reconfigServiceWithBuildbotConfig(self,
                                                                                         new_config)

    def stopService(self):
        self.disable()
        service.MultiService.stopService(self)

    def enable(self):
        if self.enabled:
            return
        log.addObserver(self.emit)
        self.enabled = True

    def disable(self):
        if not self.enabled:
            return

        if self.periodic_task:
            self.periodic_task.stop()
            self.periodic_task = None

        if self.log_task:
            self.log_task.stop()
            self.log_task = None

        log.removeObserver(self.emit)
        self.enabled = False

    def registerHandler(self, interface, handler):
        old = self.getHandler(interface)
        self.handlers[interface] = handler
        return old

    def getHandler(self, interface):
        return self.handlers.get(interface)

    def emit(self, eventDict):
        # Ignore non-statistic events
        metric = eventDict.get('metric')
        if not metric or not isinstance(metric, MetricEvent):
            return

        if metric.__class__ not in self.handlers:
            return

        h = self.handlers[metric.__class__]
        h.handle(eventDict, metric)
        for w in h.watchers:
            w.run()

    def asDict(self):
        retval = {}
        for interface, handler in iteritems(self.handlers):
            retval.update(handler.asDict())
        return retval

    def report(self):
        try:
            for interface, handler in iteritems(self.handlers):
                report = handler.report()
                if not report:
                    continue
                for line in report.split("\n"):
                    log.msg(line)
        except Exception:
            log.err(None, "generating metric report")
