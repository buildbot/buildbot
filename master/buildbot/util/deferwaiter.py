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

from twisted.internet import defer
from twisted.python import failure
from twisted.python import log

from buildbot.util import Notifier


class DeferWaiter:
    """This class manages a set of Deferred objects and allows waiting for their completion"""

    def __init__(self):
        self._waited_count = 0
        self._finish_notifier = Notifier()

    def _finished(self, result, d):
        # most likely nothing is consuming the errors, so do it here
        if isinstance(result, failure.Failure):
            log.err(result)

        self._waited_count -= 1
        if self._waited_count == 0:
            self._finish_notifier.notify(None)
        return result

    def add(self, d):
        if not isinstance(d, defer.Deferred):
            return None

        self._waited_count += 1
        d.addBoth(self._finished, d)
        return d

    def has_waited(self):
        return self._waited_count > 0

    @defer.inlineCallbacks
    def wait(self):
        if self._waited_count == 0:
            return
        yield self._finish_notifier.wait()


class RepeatedActionHandler:
    """This class handles a repeated action such as submitting keepalive requests. It integrates
    with DeferWaiter to correctly control shutdown of such process.
    """

    def __init__(self, reactor, waiter, interval, action, start_timer_after_action_completes=False):
        self._reactor = reactor
        self._waiter = waiter
        self._interval = interval
        self._action = action
        self._enabled = False
        self._timer = None
        self._start_timer_after_action_completes = start_timer_after_action_completes
        self._running = False

    def set_interval(self, interval):
        self._interval = interval

    def start(self):
        if self._enabled:
            return
        self._enabled = True
        self._start_timer()

    def stop(self):
        if not self._enabled:
            return

        self._enabled = False
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def delay(self):
        if not self._enabled or not self._timer:
            # If self._timer is None, then the action is running and timer will be started once
            # it's done.
            return
        self._timer.reset(self._interval)

    def force(self):
        if not self._enabled or self._running:
            return

        self._timer.cancel()
        self._waiter.add(self._handle_action())

    def _start_timer(self):
        self._timer = self._reactor.callLater(self._interval, self._handle_timeout)

    @defer.inlineCallbacks
    def _do_action(self):
        try:
            self._running = True
            yield self._action()
        except Exception as e:
            log.err(e, 'Got exception in RepeatedActionHandler')
        finally:
            self._running = False

    def _handle_timeout(self):
        self._waiter.add(self._handle_action())

    @defer.inlineCallbacks
    def _handle_action(self):
        self._timer = None
        if self._start_timer_after_action_completes:
            yield self._do_action()

        if self._enabled:
            self._start_timer()

        if not self._start_timer_after_action_completes:
            yield self._do_action()


class NonRepeatedActionHandler:
    """This class handles a single action that can be issued on demand. It ensures that multiple
    invocations of an action do not overlap.
    """

    def __init__(self, reactor, waiter, action):
        self._reactor = reactor
        self._waiter = waiter
        self._action = action
        self._timer = None
        self._running = False
        self._repeat_after_finished = False

    def force(self, invoke_again_if_running=False):
        if self._running:
            if not invoke_again_if_running:
                return
            self._repeat_after_finished = True
            return

        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

        self._waiter.add(self._do_action())

    def schedule(self, seconds_from_now, invoke_again_if_running=False):
        if self._running and not invoke_again_if_running:
            return

        if self._timer is None:
            self._timer = self._reactor.callLater(seconds_from_now, self._handle_timeout)
            return

        target_time = self._reactor.seconds() + seconds_from_now
        if target_time > self._timer.getTime():
            return

        self._timer.reset(seconds_from_now)

    def stop(self):
        if self._timer:
            self._timer.cancel()
            self._timer = None

    @defer.inlineCallbacks
    def _do_action(self):
        try:
            self._running = True
            yield self._action()
        except Exception as e:
            log.err(e, 'Got exception in NonRepeatedActionHandler')
        finally:
            self._running = False
        if self._repeat_after_finished:
            self._repeat_after_finished = False
            self._waiter.add(self._do_action())

    def _handle_timeout(self):
        self._timer = None
        self._waiter.add(self._do_action())
