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
# Portions Copyright Buildbot Team Members

from __future__ import annotations

import queue
import threading
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable
from typing import TypeVar
from typing import cast

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log
from typing_extensions import ParamSpec

from buildbot.util import backoff

if TYPE_CHECKING:
    from collections.abc import Mapping
    from collections.abc import Sequence

    from twisted.internet.defer import Deferred
    from twisted.internet.interfaces import IReactorFromThreads
    from twisted.python.failure import Failure

    _P = ParamSpec('_P')

_T = TypeVar('_T')


class UndoableQueue(queue.Queue[_T]):
    def unget(self, x: _T) -> None:
        with self.mutex:
            self.queue.appendleft(x)


class _TerminateRequest:
    pass


class ConnectableThreadQueue(threading.Thread):
    """
    This provides worker thread that is processing work given via execute_in_thread() method.
    The return value of the function submitted to execute_in_thread() is returned via Deferred.
    All work is performed in a "connection", which is established in create_connection() which
    is intended to be overridden by user. The user is expected to return an opaque connection
    object from create_connection(). create_connection() must not throw exceptions.
    The connection is from the user-side closed by calling close_connection().

    The connection is passed as the first argument to the functions submitted to
    execute_in_thread().

    When the thread is joined, it will execute all currently pending items and call
    on_close_connection() if needed to close the connection. Any work submitted after join() is
    called will be ignored.
    """

    def __init__(
        self,
        connect_backoff_start_seconds: float = 1,
        connect_backoff_multiplier: float = 1.1,
        connect_backoff_max_wait_seconds: float = 3600,
    ) -> None:
        self._queue: UndoableQueue[
            tuple[
                Deferred[Any],
                Callable[..., Any] | _TerminateRequest,
                Sequence[Any],
                Mapping[str, Any],
            ]
        ] = UndoableQueue()
        self._conn: Any | None = None
        self._backoff_engine = backoff.ExponentialBackoffEngineSync(
            start_seconds=connect_backoff_start_seconds,
            multiplier=connect_backoff_multiplier,
            max_wait_seconds=connect_backoff_max_wait_seconds,
        )

        super().__init__(daemon=True)
        self.connecting = False
        self.start()

    def join(self, timeout: float | None = None) -> None:
        self.execute_in_thread(_TerminateRequest())
        super().join(timeout=timeout)

    def execute_in_thread(
        self,
        cb: Callable[_P, _T] | _TerminateRequest,
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> Deferred[_T]:
        d: Deferred[_T] = defer.Deferred()
        self._queue.put((d, cb, args, kwargs))
        return d

    @property
    def conn(self) -> Any | None:
        return self._conn

    def close_connection(self) -> None:
        self._conn = None
        self.connecting = False

    def on_close_connection(self, conn: Any | None) -> None:
        # override to perform any additional connection closing tasks
        self.close_connection()

    def create_connection(self) -> Any | None:
        # override to create a new connection
        raise NotImplementedError()

    def _handle_backoff(self, msg: str) -> bool:
        # returns True if termination has been requested
        log.err(msg)
        try:
            self._backoff_engine.wait_on_failure()
        except backoff.BackoffTimeoutExceededError:
            self._backoff_engine.on_success()  # reset the timers
            if self._drain_queue_with_exception(backoff.BackoffTimeoutExceededError(msg)):
                return True
        return False

    def _drain_queue_with_exception(self, e: Failure | BaseException) -> bool:
        # returns True if termination has been requested
        try:
            _reactor = cast("IReactorFromThreads", reactor)
            while True:
                result_d, next_operation, _, __ = self._queue.get(block=False)
                if isinstance(next_operation, _TerminateRequest):
                    self._queue.task_done()
                    _reactor.callFromThread(result_d.callback, None)
                    return True
                else:
                    self._queue.task_done()
                    _reactor.callFromThread(result_d.errback, e)
        except queue.Empty:
            return False

    def run(self) -> None:
        _reactor = cast("IReactorFromThreads", reactor)
        while True:
            result_d, next_operation, args, kwargs = self._queue.get()

            if isinstance(next_operation, _TerminateRequest):
                self._queue.task_done()
                _reactor.callFromThread(result_d.callback, None)
                break

            if not self._conn:
                self.connecting = True
                self._queue.unget((result_d, next_operation, args, kwargs))
                try:
                    self._conn = self.create_connection()
                    self.connecting = False

                    if self._conn is not None:
                        self._backoff_engine.on_success()
                    elif self._handle_backoff('Did not receive connection'):
                        break

                except Exception as e:
                    self.connecting = False
                    if self._handle_backoff(f'Exception received: {e}'):
                        break
                continue
            try:
                result = next_operation(self._conn, *args, **kwargs)
                _reactor.callFromThread(result_d.callback, result)
            except Exception as e:
                _reactor.callFromThread(result_d.errback, e)
            self._queue.task_done()

        if self._conn is not None:
            self.on_close_connection(self._conn)
