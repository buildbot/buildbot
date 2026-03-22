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

from random import randint
from typing import TYPE_CHECKING
from typing import Any

from twisted.internet import defer
from twisted.python import log

if TYPE_CHECKING:
    from collections.abc import Callable

    from twisted.internet.base import DelayedCall
    from twisted.internet.interfaces import IReactorTime

    from buildbot.util.twisted import InlineCallbacksType
_poller_instances: list[tuple[Any, str]] | None = None


class Poller:
    def __init__(self, fn: Callable[..., Any], instance: Any, reactor: IReactorTime) -> None:
        self.fn = fn
        self.instance = instance

        self.running = False
        self.pending = False

        # Invariants:
        #   - If self._call is not None or self._currently_executing then it is guaranteed that
        #     self.pending and self._run_complete_deferreds will be handled at some point in the
        #     future.
        #   - If self._call is not None then _run will be executed at some point, but it's not being
        #     executed now.
        self._currently_executing = False
        self._call: DelayedCall | None = None
        self._next_call_time: float | None = None  # valid when self._call is not None

        self._start_time: float = 0
        self._interval: float = 0
        self._random_delay_min: int = 0
        self._random_delay_max: int = 0
        self._run_complete_deferreds: list[defer.Deferred[None]] = []

        self._reactor = reactor

    @defer.inlineCallbacks
    def _run(self) -> InlineCallbacksType[None]:
        self._call = None
        self._currently_executing = True

        try:
            yield self.fn(self.instance)
        except Exception as e:
            log.err(e, f'while executing {self.fn}')
        finally:
            self._currently_executing = False

        was_pending = self.pending
        self.pending = False

        if self.running:
            self._schedule(force_now=was_pending)

        while self._run_complete_deferreds:
            self._run_complete_deferreds.pop(0).callback(None)

    def _get_wait_time(
        self, curr_time: float, force_now: bool = False, force_initial_now: bool = False
    ) -> float:
        if force_now:
            return 0

        extra_wait = randint(self._random_delay_min, self._random_delay_max)

        if force_initial_now or self._interval == 0:
            return extra_wait

        # note that differently from twisted.internet.task.LoopingCall, we don't care about
        # floating-point precision issues as we don't have the withCount feature.
        running_time = curr_time - self._start_time
        return self._interval - (running_time % self._interval) + extra_wait

    def _schedule(self, force_now: bool = False, force_initial_now: bool = False) -> None:
        curr_time = self._reactor.seconds()
        wait_time = self._get_wait_time(
            curr_time, force_now=force_now, force_initial_now=force_initial_now
        )
        next_call_time = curr_time + wait_time

        if self._call is not None:
            # Note that self._call can ever be moved to earlier time, so we can always cancel it.
            self._call.cancel()

        self._next_call_time = next_call_time
        self._call = self._reactor.callLater(wait_time, self._run)  # type: ignore[assignment]

    def __call__(self) -> None:
        if not self.running:
            return
        if self._currently_executing:
            self.pending = True
        else:
            self._schedule(force_now=True)

    def start(
        self,
        interval: float,
        now: bool = False,
        random_delay_min: int = 0,
        random_delay_max: int = 0,
    ) -> None:
        assert not self.running
        self._interval = interval
        self._random_delay_min = random_delay_min
        self._random_delay_max = random_delay_max
        self._start_time = self._reactor.seconds()

        self.running = True
        self._schedule(force_initial_now=now)

    @defer.inlineCallbacks
    def stop(self) -> InlineCallbacksType[None]:
        self.running = False
        if self._call is not None:
            self._call.cancel()
            self._call = None
        if self._currently_executing:
            d: defer.Deferred[None] = defer.Deferred()
            self._run_complete_deferreds.append(d)
            yield d


class _Descriptor:
    def __init__(self, fn: Callable[..., Any], attrName: str) -> None:
        self.fn = fn
        self.attrName = attrName

    def __get__(self, instance: Any, cls: type[Any]) -> Poller:
        try:
            poller = getattr(instance, self.attrName)
        except AttributeError:
            poller = Poller(self.fn, instance, instance.master.reactor)
            setattr(instance, self.attrName, poller)
            # track instances when testing
            if _poller_instances is not None:
                _poller_instances.append((instance, self.attrName))
        return poller


def method(fn: Callable[..., Any]) -> _Descriptor:
    stateName = "__poll_" + fn.__name__ + "__"
    return _Descriptor(fn, stateName)


def track_poll_methods() -> None:
    global _poller_instances
    _poller_instances = []


def reset_poll_methods() -> None:
    global _poller_instances
    for instance, attrname in _poller_instances:  # type: ignore[union-attr]  # pylint: disable=not-an-iterable
        delattr(instance, attrname)
    _poller_instances = None
