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

import inspect
from functools import wraps
from typing import Any
from typing import Callable
from typing import Coroutine
from typing import Generator
from typing import TypeVar
from typing import Union

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import threadpool
from typing_extensions import ParamSpec

_T = TypeVar('_T')
_P = ParamSpec('_P')


InlineCallbacksType = Generator[Union[Any, defer.Deferred[Any]], Any, _T]


def async_to_deferred(
    fn: Callable[_P, Coroutine[Any, Any, _T]],
) -> Callable[_P, defer.Deferred[_T]]:
    @wraps(fn)
    def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> defer.Deferred[_T]:
        try:
            return defer.ensureDeferred(fn(*args, **kwargs))
        except Exception as e:
            return defer.fail(e)

    return wrapper


async def any_to_async(value: Coroutine[Any, Any, _T] | defer.Deferred[_T] | _T) -> _T:
    if inspect.isawaitable(value):
        # defer.Deferred is awaitable too
        return await value
    return value


class ThreadPool(threadpool.ThreadPool):
    # This thread pool ensures that it stops on reactor shutdown

    _stop_event = None  # if not None, then pool is running

    def start(self):
        if self._stop_event:
            return

        super().start()
        self._stop_event = reactor.addSystemEventTrigger(
            'during', 'shutdown', self._stop_on_shutdown
        )

    def _stop_on_shutdown(self):
        self._stop_impl(remove_trigger=False)

    def stop(self):
        self._stop_impl(remove_trigger=True)

    def _stop_impl(self, remove_trigger):
        if not self._stop_event:
            return
        super().stop()
        if remove_trigger:
            reactor.removeSystemEventTrigger(self._stop_event)
        self._stop_event = None
