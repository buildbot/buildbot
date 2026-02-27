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

from typing import TYPE_CHECKING
from typing import Callable
from typing import Generic
from typing import TypeVar

from twisted.internet import defer
from twisted.python import failure
from twisted.python import log

from buildbot.util import Notifier

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from twisted.internet.defer import Deferred
    from twisted.internet.interfaces import IDelayedCall
    from twisted.internet.interfaces import IReactorTime

    from buildbot.util.twisted import InlineCallbacksType

_SelfResultT = TypeVar("_SelfResultT")


class DeferWaiter(Generic[_SelfResultT]):
    """This class manages a set of Deferred objects and allows waiting for their completion"""

    def __init__(self) -> None:
        self._waited_count = 0
        self._finish_notifier: Notifier[None] = Notifier()

    def _finished(self, result: _SelfResultT, d: Deferred) -> _SelfResultT:
        # most likely nothing is consuming the errors, so do it here
        if isinstance(result, failure.Failure):
            log.err(result)

        self._waited_count -= 1
        if self._waited_count == 0:
            self._finish_notifier.notify(None)
        return result

    def add(self, d: Deferred[_SelfResultT]) -> Deferred[_SelfResultT]:
        if not isinstance(d, defer.Deferred):
            return None

        self._waited_count += 1
        d.addBoth(self._finished, d)
        return d

    def has_waited(self) -> bool:
        return self._waited_count > 0

    @defer.inlineCallbacks
    def wait(self) -> InlineCallbacksType[None]:
        if self._waited_count == 0:
            return
        yield self._finish_notifier.wait()


class RepeatedActionHandler:
    """This class handles a repeated action such as submitting keepalive requests. It integrates
    with DeferWaiter to correctly control shutdown of such process.
    """

    def __init__(
        self,
        reactor: IReactorTime,
        waiter: DeferWaiter,
        interval: int,
        action: Callable[[], Awaitable[None]],
        start_timer_after_action_completes: bool = False,
    ) -> None:
        self._reactor = reactor
        self._waiter = waiter
        self._interval = interval
        self._action = action
        self._enabled = False
        self._timer: IDelayedCall | None = None
        self._start_timer_after_action_completes = start_timer_after_action_completes
        self._running = False

    def set_interval(self, interval: int) -> None:
        self._interval = interval

    def start(self) -> None:
        if self._enabled:
            return
        self._enabled = True
        self._start_timer()

    def stop(self) -> None:
        if not self._enabled:
            return

        self._enabled = False
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def delay(self) -> None:
        if not self._enabled or not self._timer:
            # If self._timer is None, then the action is running and timer will be started once
            # it's done.
            return
        self._timer.reset(self._interval)

    def force(self) -> None:
        if not self._enabled or self._running:
            return

        if self._timer is not None:
            self._timer.cancel()
        self._waiter.add(self._handle_action())

    def _start_timer(self) -> None:
        self._timer = self._reactor.callLater(self._interval, self._handle_timeout)

    @defer.inlineCallbacks
    def _do_action(self) -> InlineCallbacksType[None]:
        try:
            self._running = True
            yield self._action()
        except Exception as e:
            log.err(e, 'Got exception in RepeatedActionHandler')
        finally:
            self._running = False

    def _handle_timeout(self) -> None:
        self._waiter.add(self._handle_action())

    @defer.inlineCallbacks
    def _handle_action(self) -> InlineCallbacksType[None]:
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

    def __init__(
        self,
        reactor: IReactorTime,
        waiter: DeferWaiter[None],
        action: Callable[[], Awaitable[None]],
    ) -> None:
        self._reactor = reactor
        self._waiter = waiter
        self._action = action
        self._timer: IDelayedCall | None = None
        self._running = False
        self._repeat_after_finished = False

    def force(self, invoke_again_if_running: bool = False) -> None:
        if self._running:
            if not invoke_again_if_running:
                return
            self._repeat_after_finished = True
            return

        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

        self._waiter.add(self._do_action())

    def schedule(self, seconds_from_now: int, invoke_again_if_running: bool = False) -> None:
        if self._running and not invoke_again_if_running:
            return

        if self._timer is None:
            self._timer = self._reactor.callLater(seconds_from_now, self._handle_timeout)
            return

        target_time = self._reactor.seconds() + seconds_from_now
        if target_time > self._timer.getTime():
            return

        self._timer.reset(seconds_from_now)

    def stop(self) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None

    @defer.inlineCallbacks
    def _do_action(self) -> InlineCallbacksType[None]:
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

    def _handle_timeout(self) -> None:
        self._timer = None
        self._waiter.add(self._do_action())
