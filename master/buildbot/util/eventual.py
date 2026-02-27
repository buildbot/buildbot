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
#
# copied from foolscap

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from typing import Callable
from typing import TypeVar
from typing import cast

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log

if TYPE_CHECKING:
    from twisted.internet.defer import Deferred
    from twisted.internet.interfaces import IDelayedCall
    from twisted.internet.interfaces import IReactorTime
    from typing_extensions import ParamSpec

    _T = TypeVar('_T')
    _P = ParamSpec('_P')


class _SimpleCallQueue:
    _reactor: IReactorTime = cast("IReactorTime", reactor)

    def __init__(self) -> None:
        self._events: list[tuple[Callable[..., Any], Any, dict[str, Any]]] = []
        self._flushObservers: list[Deferred[None]] = []
        self._timer: IDelayedCall | None = None
        self._in_turn = False

    def append(self, cb: Callable[..., Any], args: Any, kwargs: dict[str, Any]) -> None:
        self._events.append((cb, args, kwargs))
        if not self._timer:
            self._timer = self._reactor.callLater(0, self._turn)

    def _turn(self) -> None:
        self._timer = None
        self._in_turn = True
        # flush all the messages that are currently in the queue. If anything
        # gets added to the queue while we're doing this, those events will
        # be put off until the next turn.
        events = self._events
        self._events = []
        for cb, args, kwargs in events:
            try:
                cb(*args, **kwargs)
            except Exception:
                log.err()
        self._in_turn = False
        if self._events and not self._timer:
            self._timer = self._reactor.callLater(0, self._turn)
        if not self._events:
            observers = self._flushObservers
            self._flushObservers = []
            for o in observers:
                o.callback(None)

    def flush(self) -> Deferred[None]:
        if not self._events and not self._in_turn:
            return defer.succeed(None)
        d: Deferred[None] = defer.Deferred()
        self._flushObservers.append(d)
        return d


_theSimpleQueue = _SimpleCallQueue()


def eventually(cb: Callable[_P, _T], *args: _P.args, **kwargs: _P.kwargs) -> None:
    _theSimpleQueue.append(cb, args, kwargs)


def fireEventually(value: _T | None = None) -> Deferred[_T | None]:
    d: Deferred[_T | None] = defer.Deferred()
    eventually(d.callback, value)
    return d


def flushEventualQueue(_ignored: None = None) -> Deferred:
    return _theSimpleQueue.flush()


def _setReactor(r: IReactorTime | None = None) -> None:
    # This sets the reactor used to schedule future events to r.  If r is None
    # (the default), the reactor is reset to its default value.
    # This should only be used for unit tests.
    if r is None:
        r = cast("IReactorTime", reactor)
    _theSimpleQueue._reactor = r
