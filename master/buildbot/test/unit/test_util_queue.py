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

import threading
from typing import TYPE_CHECKING

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.util.backoff import BackoffTimeoutExceededError
from buildbot.util.queue import ConnectableThreadQueue

if TYPE_CHECKING:
    from twisted.python.failure import Failure
    from twisted.trial import unittest as _unittest

    from buildbot.util.twisted import InlineCallbacksType

    _ConnectionErrorTestsBase = _unittest.TestCase
else:
    _ConnectionErrorTestsBase = object


class FakeConnection:
    pass


class TestableConnectableThreadQueue(ConnectableThreadQueue):
    def __init__(
        self,
        case: unittest.TestCase,
        connect_backoff_start_seconds: float = 1,
        connect_backoff_multiplier: float = 1.1,
        connect_backoff_max_wait_seconds: float = 3600,
    ) -> None:
        super().__init__(
            connect_backoff_start_seconds=connect_backoff_start_seconds,
            connect_backoff_multiplier=connect_backoff_multiplier,
            connect_backoff_max_wait_seconds=connect_backoff_max_wait_seconds,
        )
        self.case = case
        self.create_connection_called_count = 0
        self.close_connection_called_count = 0
        self._test_conn: FakeConnection | None = None

    def create_connection(self) -> FakeConnection:
        self.case.assertTrue(self.connecting)
        self.create_connection_called_count += 1
        self.case.assertIsNone(self._test_conn)
        self._test_conn = FakeConnection()
        return self._test_conn

    def on_close_connection(self, conn: object) -> None:
        self.case.assertIs(conn, self._test_conn)
        self._test_conn = None
        self.close_connection()

    def close_connection(self) -> None:
        self.case.assertFalse(self.connecting)
        self._test_conn = None
        self.close_connection_called_count += 1
        super().close_connection()


class TestException(Exception):
    pass


class TestConnectableThreadQueue(unittest.TestCase):
    timeout = 10

    def setUp(self) -> None:
        self.queue = TestableConnectableThreadQueue(
            self,
            connect_backoff_start_seconds=0,
            connect_backoff_multiplier=0,
            connect_backoff_max_wait_seconds=0,
        )

    def tearDown(self) -> None:
        self.join_queue()

    def join_queue(self, connection_called_count: int | None = None) -> None:
        self.queue.join(timeout=self.timeout)
        if self.queue.is_alive():
            raise AssertionError('Thread is still alive')
        if connection_called_count is not None:
            self.assertEqual(self.queue.create_connection_called_count, connection_called_count)
            self.assertEqual(self.queue.close_connection_called_count, connection_called_count)

    def test_no_work(self) -> None:
        self.join_queue(0)

    @defer.inlineCallbacks
    def test_single_item_called(self) -> InlineCallbacksType[None]:
        def work(conn: object, *args: object, **kwargs: object) -> str:
            self.assertIs(conn, self.queue.conn)
            self.assertEqual(args, ('arg',))
            self.assertEqual(kwargs, {'kwarg': 'kwvalue'})
            return 'work_result'

        result = yield self.queue.execute_in_thread(work, 'arg', kwarg='kwvalue')
        self.assertEqual(result, 'work_result')

        self.join_queue(1)

    @defer.inlineCallbacks
    def test_single_item_called_exception(self) -> InlineCallbacksType[None]:
        def work(conn: object) -> None:
            raise TestException()

        with self.assertRaises(TestException):
            yield self.queue.execute_in_thread(work)

        self.join_queue(1)

    @defer.inlineCallbacks
    def test_exception_does_not_break_further_work(self) -> InlineCallbacksType[None]:
        def work_exception(conn: object) -> None:
            raise TestException()

        def work_success(conn: object) -> str:
            return 'work_result'

        with self.assertRaises(TestException):
            yield self.queue.execute_in_thread(work_exception)

        result = yield self.queue.execute_in_thread(work_success)
        self.assertEqual(result, 'work_result')

        self.join_queue(1)

    @defer.inlineCallbacks
    def test_single_item_called_disconnect(self) -> InlineCallbacksType[None]:
        def work(conn: object) -> None:
            pass

        yield self.queue.execute_in_thread(work)

        self.queue.close_connection()

        yield self.queue.execute_in_thread(work)

        self.join_queue(2)

    @defer.inlineCallbacks
    def test_many_items_called_in_order(self) -> InlineCallbacksType[None]:
        self.expected_work_index = 0

        def work(conn: object, work_index: int) -> int:
            self.assertEqual(self.expected_work_index, work_index)
            self.expected_work_index = work_index + 1
            return work_index

        work_deferreds = [self.queue.execute_in_thread(work, i) for i in range(0, 100)]

        for i, d in enumerate(work_deferreds):
            self.assertEqual((yield d), i)

        self.join_queue(1)


class FailingConnectableThreadQueue(ConnectableThreadQueue):
    def __init__(
        self,
        case: unittest.TestCase,
        lock: threading.Lock,
        connect_backoff_start_seconds: float = 1,
        connect_backoff_multiplier: float = 1.1,
        connect_backoff_max_wait_seconds: float = 3600,
    ) -> None:
        super().__init__(
            connect_backoff_start_seconds=connect_backoff_start_seconds,
            connect_backoff_multiplier=connect_backoff_multiplier,
            connect_backoff_max_wait_seconds=connect_backoff_max_wait_seconds,
        )
        self.case = case
        self.lock = lock
        self.create_connection_called_count = 0

    def on_close_connection(self, conn: object) -> None:
        raise AssertionError("on_close_connection should not have been called")

    def close_connection(self) -> None:
        raise AssertionError("close_connection should not have been called")

    def _drain_queue_with_exception(self, e: Failure | BaseException) -> bool:
        with self.lock:
            return super()._drain_queue_with_exception(e)


class ThrowingConnectableThreadQueue(FailingConnectableThreadQueue):
    def create_connection(self) -> None:
        with self.lock:
            self.create_connection_called_count += 1
            self.case.assertTrue(self.connecting)
            raise TestException()


class NoneReturningConnectableThreadQueue(FailingConnectableThreadQueue):
    def create_connection(self) -> None:
        with self.lock:
            self.create_connection_called_count += 1
            self.case.assertTrue(self.connecting)
            return None


class ConnectionErrorTests(_ConnectionErrorTestsBase):
    timeout = 10
    QueueClass: type[FailingConnectableThreadQueue]

    def setUp(self) -> None:
        self.lock = threading.Lock()
        self.queue = self.QueueClass(
            self,
            self.lock,
            connect_backoff_start_seconds=0.001,
            connect_backoff_multiplier=1,
            connect_backoff_max_wait_seconds=0.0039,
        )

    def tearDown(self) -> None:
        self.queue.join(timeout=self.timeout)
        if self.queue.is_alive():
            raise AssertionError('Thread is still alive')

    @defer.inlineCallbacks
    def test_resets_after_reject(self) -> InlineCallbacksType[None]:
        def work(conn: object) -> None:
            raise AssertionError('work should not be executed')

        with self.lock:
            d = self.queue.execute_in_thread(work)

        with self.assertRaises(BackoffTimeoutExceededError):
            yield d

        self.assertEqual(self.queue.create_connection_called_count, 5)

        with self.lock:
            d = self.queue.execute_in_thread(work)

        with self.assertRaises(BackoffTimeoutExceededError):
            yield d

        self.assertEqual(self.queue.create_connection_called_count, 10)
        self.flushLoggedErrors(TestException)

    @defer.inlineCallbacks
    def test_multiple_work_rejected(self) -> InlineCallbacksType[None]:
        def work(conn: object) -> None:
            raise AssertionError('work should not be executed')

        with self.lock:
            d1 = self.queue.execute_in_thread(work)
            d2 = self.queue.execute_in_thread(work)
            d3 = self.queue.execute_in_thread(work)

        with self.assertRaises(BackoffTimeoutExceededError):
            yield d1
        with self.assertRaises(BackoffTimeoutExceededError):
            yield d2
        with self.assertRaises(BackoffTimeoutExceededError):
            yield d3

        self.assertEqual(self.queue.create_connection_called_count, 5)
        self.flushLoggedErrors(TestException)


class TestConnectionErrorThrow(ConnectionErrorTests, unittest.TestCase):
    QueueClass = ThrowingConnectableThreadQueue


class TestConnectionErrorReturnNone(ConnectionErrorTests, unittest.TestCase):
    QueueClass = NoneReturningConnectableThreadQueue
