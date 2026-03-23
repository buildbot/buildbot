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
from typing import Any
from typing import NoReturn

from twisted.internet import defer
from twisted.python import log
from twisted.trial import unittest

from buildbot.util import eventual

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class Eventually(unittest.TestCase):
    def setUp(self) -> None:
        # reset the queue to its base state
        eventual._theSimpleQueue = eventual._SimpleCallQueue()
        self.old_log_err = log.err
        self.results: list[Any] = []

    def tearDown(self) -> defer.Deferred[None]:  # type: ignore[override]
        log.err = self.old_log_err
        return eventual.flushEventualQueue()

    # utility callback
    def cb(self, *args: Any, **kwargs: Any) -> None:
        r = args
        if kwargs:
            r = (*r, kwargs)
        self.results.append(r)

    # flush the queue and assert results
    @defer.inlineCallbacks
    def assertResults(self, exp: list[Any]) -> InlineCallbacksType[None]:
        yield eventual.flushEventualQueue()

        self.assertEqual(self.results, exp)

    # tests

    def test_eventually_calls(self) -> defer.Deferred[None]:
        eventual.eventually(self.cb)
        return self.assertResults([()])

    def test_eventually_args(self) -> defer.Deferred[None]:
        eventual.eventually(self.cb, 1, 2, a='a')
        return self.assertResults([(1, 2, {"a": 'a'})])

    def test_eventually_err(self) -> defer.Deferred[None]:
        # monkey-patch log.err; this is restored by tearDown
        def cb_err() -> None:
            self.results.append("err")

        log.err = cb_err  # type: ignore[assignment]

        def cb_fails() -> NoReturn:
            raise RuntimeError("should not cause test failure")

        eventual.eventually(cb_fails)
        return self.assertResults(['err'])

    def test_eventually_butNotNow(self) -> defer.Deferred[None]:
        eventual.eventually(self.cb, 1)
        self.assertFalse(self.results)
        return self.assertResults([(1,)])

    def test_eventually_order(self) -> defer.Deferred[None]:
        eventual.eventually(self.cb, 1)
        eventual.eventually(self.cb, 2)
        eventual.eventually(self.cb, 3)
        return self.assertResults([(1,), (2,), (3,)])

    def test_flush_waitForChainedEventuallies(self) -> defer.Deferred[None]:
        def chain(n: int) -> None:
            self.results.append(n)
            if n <= 0:
                return
            eventual.eventually(chain, n - 1)

        chain(3)
        # (the flush this tests is implicit in assertResults)
        return self.assertResults([3, 2, 1, 0])

    def test_flush_waitForTreeEventuallies(self) -> defer.Deferred[None]:
        # a more complex set of eventualities
        def tree(n: int) -> None:
            self.results.append(n)
            if n <= 0:
                return
            eventual.eventually(tree, n - 1)
            eventual.eventually(tree, n - 1)

        tree(2)
        # (the flush this tests is implicit in assertResults)
        return self.assertResults([2, 1, 1, 0, 0, 0, 0])

    def test_flush_duringTurn(self) -> defer.Deferred[None]:
        testd = defer.Deferred()  # type: ignore[var-annotated]

        def cb() -> None:
            d = eventual.flushEventualQueue()
            d.addCallback(testd.callback)

        eventual.eventually(cb)
        return testd

    def test_fireEventually_call(self) -> defer.Deferred[None]:
        d = eventual.fireEventually(13)
        d.addCallback(self.cb)
        return self.assertResults([(13,)])
