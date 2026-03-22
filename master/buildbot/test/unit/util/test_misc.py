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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot import util
from buildbot.test.reactor import TestReactorMixin
from buildbot.util import misc

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class deferredLocked(unittest.TestCase):
    def test_name(self) -> None:
        self.assertEqual(util.deferredLocked, misc.deferredLocked)

    @defer.inlineCallbacks
    def test_fn(self) -> InlineCallbacksType[None]:
        lock = defer.DeferredLock()

        @util.deferredLocked(lock)
        def check_locked(arg1: int, arg2: int) -> defer.Deferred[None]:
            self.assertEqual([lock.locked, arg1, arg2], [True, 1, 2])
            return defer.succeed(None)

        yield check_locked(1, 2)

        self.assertFalse(lock.locked)

    @defer.inlineCallbacks
    def test_fn_fails(self) -> InlineCallbacksType[None]:
        lock = defer.DeferredLock()

        @util.deferredLocked(lock)
        def do_fail() -> defer.Deferred[None]:
            return defer.fail(RuntimeError("oh noes"))

        try:
            yield do_fail()
            self.fail("didn't errback")
        except Exception:
            self.assertFalse(lock.locked)

    @defer.inlineCallbacks
    def test_fn_exception(self) -> InlineCallbacksType[None]:
        lock = defer.DeferredLock()

        @util.deferredLocked(lock)  # type: ignore[arg-type]
        def do_fail() -> None:
            raise RuntimeError("oh noes")

        # using decorators confuses pylint and gives a false positive below
        try:
            yield do_fail()  # pylint: disable=assignment-from-no-return
            self.fail("didn't errback")
        except Exception:
            self.assertFalse(lock.locked)

    @defer.inlineCallbacks
    def test_method(self) -> InlineCallbacksType[None]:
        testcase = self

        class C:
            @util.deferredLocked('aLock')
            def check_locked(self, arg1: int, arg2: int) -> defer.Deferred[None]:
                testcase.assertEqual([self.aLock.locked, arg1, arg2], [True, 1, 2])  # type: ignore[attr-defined]
                return defer.succeed(None)

        obj = C()
        obj.aLock = defer.DeferredLock()  # type: ignore[attr-defined]
        yield obj.check_locked(1, 2)

        self.assertFalse(obj.aLock.locked)  # type: ignore[attr-defined]


class TestCancelAfter(TestReactorMixin, unittest.TestCase):
    def setUp(self) -> None:
        self.setup_test_reactor()
        self.d = defer.Deferred()  # type: ignore[var-annotated]

    def test_succeeds(self) -> None:
        d = misc.cancelAfter(10, self.d, self.reactor)
        self.assertIdentical(d, self.d)

        @d.addCallback
        def check(r: str) -> None:
            self.assertEqual(r, "result")

        self.assertFalse(d.called)
        self.d.callback("result")
        self.assertTrue(d.called)

    @defer.inlineCallbacks
    def test_fails(self) -> InlineCallbacksType[None]:
        d = misc.cancelAfter(10, self.d, self.reactor)
        self.assertFalse(d.called)
        self.d.errback(RuntimeError("oh noes"))
        self.assertTrue(d.called)
        with self.assertRaises(RuntimeError):
            yield d

    @defer.inlineCallbacks
    def test_timeout_succeeds(self) -> InlineCallbacksType[None]:
        d = misc.cancelAfter(10, self.d, self.reactor)
        self.assertFalse(d.called)
        self.reactor.advance(11)
        d.callback("result")  # ignored
        self.assertTrue(d.called)
        with self.assertRaises(defer.CancelledError):
            yield d

    @defer.inlineCallbacks
    def test_timeout_fails(self) -> InlineCallbacksType[None]:
        d = misc.cancelAfter(10, self.d, self.reactor)
        self.assertFalse(d.called)
        self.reactor.advance(11)
        self.d.errback(RuntimeError("oh noes"))  # ignored
        self.assertTrue(d.called)
        with self.assertRaises(defer.CancelledError):
            yield d


class TestChunkifyList(unittest.TestCase):
    def test_all(self) -> None:
        self.assertEqual(list(misc.chunkify_list([], 0)), [])
        self.assertEqual(list(misc.chunkify_list([], 1)), [])
        self.assertEqual(list(misc.chunkify_list([1], 0)), [[1]])
        self.assertEqual(list(misc.chunkify_list([1], 1)), [[1]])
        self.assertEqual(list(misc.chunkify_list([1], 2)), [[1]])
        self.assertEqual(list(misc.chunkify_list([1, 2], 0)), [[1], [2]])
        self.assertEqual(list(misc.chunkify_list([1, 2], 1)), [[1], [2]])
        self.assertEqual(list(misc.chunkify_list([1, 2], 2)), [[1, 2]])
        self.assertEqual(list(misc.chunkify_list([1, 2], 3)), [[1, 2]])
        self.assertEqual(list(misc.chunkify_list([1, 2, 3], 0)), [[1], [2], [3]])
        self.assertEqual(list(misc.chunkify_list([1, 2, 3], 1)), [[1], [2], [3]])
        self.assertEqual(list(misc.chunkify_list([1, 2, 3], 2)), [[1, 2], [3]])
        self.assertEqual(list(misc.chunkify_list([1, 2, 3], 3)), [[1, 2, 3]])
        self.assertEqual(list(misc.chunkify_list([1, 2, 3], 4)), [[1, 2, 3]])

        self.assertEqual(
            list(misc.chunkify_list([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0)),
            [[1], [2], [3], [4], [5], [6], [7], [8], [9], [10]],
        )
        self.assertEqual(
            list(misc.chunkify_list([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 1)),
            [[1], [2], [3], [4], [5], [6], [7], [8], [9], [10]],
        )
        self.assertEqual(
            list(misc.chunkify_list([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 2)),
            [[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]],
        )
        self.assertEqual(
            list(misc.chunkify_list([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 3)),
            [[1, 2, 3], [4, 5, 6], [7, 8, 9], [10]],
        )
        self.assertEqual(
            list(misc.chunkify_list([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 4)),
            [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10]],
        )
        self.assertEqual(
            list(misc.chunkify_list([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 5)),
            [[1, 2, 3, 4, 5], [6, 7, 8, 9, 10]],
        )
        self.assertEqual(
            list(misc.chunkify_list([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 6)),
            [[1, 2, 3, 4, 5, 6], [7, 8, 9, 10]],
        )
        self.assertEqual(
            list(misc.chunkify_list([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 7)),
            [[1, 2, 3, 4, 5, 6, 7], [8, 9, 10]],
        )
        self.assertEqual(
            list(misc.chunkify_list([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 8)),
            [[1, 2, 3, 4, 5, 6, 7, 8], [9, 10]],
        )
        self.assertEqual(
            list(misc.chunkify_list([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 9)),
            [[1, 2, 3, 4, 5, 6, 7, 8, 9], [10]],
        )
        self.assertEqual(
            list(misc.chunkify_list([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 10)),
            [[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]],
        )
