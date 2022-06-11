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
    """ This class manages a set of Deferred objects and allows waiting for their completion
    """
    def __init__(self):
        self._waited = {}
        self._finish_notifier = Notifier()

    def _finished(self, result, d):
        # most likely nothing is consuming the errors, so do it here
        if isinstance(result, failure.Failure):
            log.err(result)

        self._waited.pop(id(d))
        if not self._waited:
            self._finish_notifier.notify(None)
        return result

    def add(self, d):
        if not isinstance(d, defer.Deferred):
            return None

        self._waited[id(d)] = d
        d.addBoth(self._finished, d)
        return d

    def cancel(self):
        for d in list(self._waited.values()):
            d.cancel()
        self._waited.clear()

    def has_waited(self):
        return bool(self._waited)

    @defer.inlineCallbacks
    def wait(self):
        if not self._waited:
            return
        yield self._finish_notifier.wait()


class RepeatedActionHandler:
    """ This class handles a repeated action such as submitting keepalive requests. It integrates
        with DeferWaiter to correctly control shutdown of such process.
    """

    def __init__(self, reactor, waiter, interval, action,
                 start_timer_after_action_completes=False):
        self._reactor = reactor
        self._waiter = waiter
        self._interval = interval
        self._action = action
        self._enabled = False
        self._timer = None
        self._start_timer_after_action_completes = start_timer_after_action_completes

    def setInterval(self, interval):
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
        if self._timer and self._timer.active():
            self._timer.cancel()
            self._timer = None

    def _start_timer(self):
        self._timer = self._reactor.callLater(self._interval, self._handle_timeout)

    @defer.inlineCallbacks
    def _do_action(self):
        try:
            yield self._action()
        except Exception as e:
            log.err(e, 'Got exception in RepeatedActionHandler')

    def _handle_timeout(self):
        self._waiter.add(self._handle_action())

    @defer.inlineCallbacks
    def _handle_action(self):
        if self._start_timer_after_action_completes:
            yield self._do_action()

        if self._enabled:
            self._start_timer()

        if not self._start_timer_after_action_completes:
            yield self._do_action()
