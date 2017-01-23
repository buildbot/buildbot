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
from future.utils import itervalues

from twisted.internet import defer
from twisted.internet import task
from twisted.python import failure
from twisted.python import log
from twisted.trial import unittest

from buildbot.util import debounce


class DebouncedClass(object):

    def __init__(self, reactor):
        self.callDeferred = None
        self.calls = 0
        self.expCalls = 0
        self.stopDeferreds = []
        self.reactor = reactor

    @debounce.method(wait=4.0, get_reactor=lambda self: self.reactor)
    def maybe(self):
        assert not self.callDeferred
        self.calls += 1
        log.msg('debounced function called')
        self.callDeferred = defer.Deferred()

        @self.callDeferred.addBoth
        def unset(x):
            log.msg('debounced function complete')
            self.callDeferred = None
            return x
        return self.callDeferred


class DebounceTest(unittest.TestCase):

    def setUp(self):
        self.clock = task.Clock()

    def scenario(self, events):
        dbs = dict((k, DebouncedClass(self.clock))
                   for k in set([n for n, _, _ in events]))
        while events:
            n, t, e = events.pop(0)
            db = dbs[n]
            log.msg('time=%f, event=%s' % (t, e))
            if t > self.clock.seconds():
                self.clock.advance(t - self.clock.seconds())
            if e == 'maybe':
                db.maybe()
            elif e == 'called':
                db.expCalls += 1
            elif e == 'complete':
                db.callDeferred.callback(None)
            elif e == 'fail':
                db.callDeferred.errback(failure.Failure(RuntimeError()))
            elif e == 'failure_logged':
                self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)
            elif e == 'check':
                pass  # just check the expCalls
            elif e == 'start':
                db.maybe.start()
            elif e in ('stop', 'stop-and-called'):
                db.stopDeferreds.append(db.maybe.stop())
                if e == 'stop-and-called':
                    db.expCalls += 1
            elif e == 'stopNotComplete':
                self.assertFalse(db.stopDeferreds[-1].called)
            elif e == 'stopComplete':
                self.assertTrue(db.stopDeferreds[-1].called)
                db.stopDeferreds.pop()
            else:
                self.fail("unknown scenario event %s" % e)
            for db in itervalues(dbs):
                self.assertEqual(db.calls, db.expCalls)

    def test_called_once(self):
        """The debounced method is called only after 4 seconds"""
        self.scenario([
            (1, 0.0, 'maybe'),
            (1, 2.0, 'check'),
            (1, 4.0, 'called'),
            (1, 5.0, 'check'),
            (1, 6.0, 'complete'),
            (1, 7.0, 'check')
        ])

    def test_coalesce_calls(self):
        """Multiple calls are coalesced during 4 seconds, but the function
        runs 4 seconds after the first call."""
        self.scenario([
            (1, 0.0, 'maybe'),
            (1, 1.0, 'maybe'),
            (1, 2.0, 'maybe'),
            (1, 3.0, 'maybe'),
            (1, 4.0, 'called'),
            (1, 5.0, 'check'),
            (1, 6.0, 'complete'),
            (1, 7.0, 'check'),
        ])

    def test_second_call_during_first(self):
        """If the debounced method is called after an execution has begun, then
        a second execution will take place 4 seconds after the execution
        finishes, with intervening calls coalesced."""
        self.scenario([
            (1, 0.0, 'maybe'),
            (1, 4.0, 'called'),
            (1, 5.0, 'maybe'),
            (1, 6.0, 'complete'),
            (1, 7.0, 'maybe'),
            (1, 9.0, 'maybe'),
            (1, 10.0, 'called'),
            (1, 11.0, 'check'),
        ])

    def test_failure_logged(self):
        """If the debounced method fails, the error is logged, but otherwise it
        behaves as if it had succeeded."""
        self.scenario([
            (1, 0.0, 'maybe'),
            (1, 4.0, 'called'),
            (1, 5.0, 'maybe'),
            (1, 6.0, 'fail'),
            (1, 6.0, 'failure_logged'),
            (1, 10.0, 'called'),
            (1, 11.0, 'check'),
        ])

    def test_instance_independence(self):
        """The timers for two instances are independent."""
        self.scenario([
            (1, 0.0, 'maybe'),
            (2, 2.0, 'maybe'),
            (1, 4.0, 'called'),
            (2, 6.0, 'called'),
            (1, 6.0, 'complete'),
            (2, 6.0, 'complete'),
            (1, 7.0, 'check'),
        ])

    def test_start_when_started(self):
        """Calling meth.start when already started has no effect"""
        self.scenario([
            (1, 0.0, 'start'),
            (1, 1.0, 'start'),
        ])

    def test_stop_while_idle(self):
        """If the debounced method is stopped while idle, subsequent calls do
        nothing."""
        self.scenario([
            (1, 0.0, 'stop'),
            (1, 0.0, 'stopComplete'),
            (1, 1.0, 'maybe'),
            (1, 6.0, 'check'),  # not called
        ])

    def test_stop_while_waiting(self):
        """If the debounced method is stopped while waiting, the waiting call
        occurs immediately, stop returns immediately, and subsequent calls do
        nothing."""
        self.scenario([
            (1, 0.0, 'maybe'),
            (1, 2.0, 'stop-and-called'),
            (1, 2.1, 'complete'),
            (1, 2.1, 'stopComplete'),
            (1, 3.0, 'maybe'),
            (1, 8.0, 'check'),  # not called
        ])

    def test_stop_while_running(self):
        """If the debounced method is stopped while running, the running call
        completes, stop returns only after the call completes, and subsequent
        calls do nothing."""
        self.scenario([
            (1, 0.0, 'maybe'),
            (1, 4.0, 'called'),
            (1, 5.0, 'stop'),
            (1, 5.0, 'stopNotComplete'),
            (1, 6.0, 'complete'),
            (1, 6.0, 'stopComplete'),
            (1, 6.0, 'maybe'),
            (1, 10.0, 'check'),  # not called
        ])

    def test_multiple_stops(self):
        """Multiple stop calls will return individually when the method
        completes."""
        self.scenario([
            (1, 0.0, 'maybe'),
            (1, 4.0, 'called'),
            (1, 5.0, 'stop'),
            (1, 5.0, 'stop'),
            (1, 5.0, 'stopNotComplete'),
            (1, 6.0, 'complete'),
            (1, 6.0, 'stopComplete'),
            (1, 6.0, 'stopComplete'),
            (1, 6.0, 'maybe'),
            (1, 10.0, 'check'),  # not called
        ])

    def test_stop_while_running_queued(self):
        """If the debounced method is stopped while running with another call
        queued, the running call completes, stop returns only after the call
        completes, the queued call never occurs, and subsequent calls do
        nothing."""
        self.scenario([
            (1, 0.0, 'maybe'),
            (1, 4.0, 'called'),
            (1, 4.5, 'maybe'),
            (1, 5.0, 'stop'),
            (1, 5.0, 'stopNotComplete'),
            (1, 6.0, 'complete'),
            (1, 6.0, 'stopComplete'),
            (1, 6.0, 'maybe'),
            (1, 10.0, 'check'),  # not called
        ])

    def test_start_after_stop(self):
        """After a stop and subsequent start, a call to the debounced method
        causes an invocation 4 seconds later."""
        self.scenario([
            (1, 0.0, 'stop'),
            (1, 1.0, 'maybe'),
            (1, 2.0, 'start'),
            (1, 2.0, 'maybe'),
            (1, 5.0, 'check'),  # not called
            (1, 6.0, 'called'),
        ])
