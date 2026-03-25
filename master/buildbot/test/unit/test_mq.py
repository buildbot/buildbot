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
from unittest import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.mq import base
from buildbot.mq import simple
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import interfaces
from buildbot.test.util import tuplematching

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class Tests(interfaces.InterfaceTests):
    mq: base.MQBase

    def setUp(self) -> None:
        raise NotImplementedError

    def test_empty_produce(self) -> None:
        self.mq.produce(('a', 'b', 'c'), {"x": 1})
        # ..nothing happens

    def test_signature_produce(self) -> None:
        @self.assertArgSpecMatches(self.mq.produce)
        def produce(self: Any, routingKey: object, data: object) -> None:
            pass

    def test_signature_startConsuming(self) -> None:
        @self.assertArgSpecMatches(self.mq.startConsuming)
        def startConsuming(
            self: Any, callback: object, filter: object, persistent_name: object = None
        ) -> None:
            pass

    @defer.inlineCallbacks
    def test_signature_stopConsuming(self) -> InlineCallbacksType[None]:
        cons = yield self.mq.startConsuming(lambda: None, ('a',))

        @self.assertArgSpecMatches(cons.stopConsuming)
        def stopConsuming(self: Any) -> None:
            pass

    def test_signature_waitUntilEvent(self) -> None:
        @self.assertArgSpecMatches(self.mq.waitUntilEvent)
        def waitUntilEvent(self: Any, filter: object, check_callback: object) -> None:
            pass


class RealTests(tuplematching.TupleMatchingMixin, Tests):
    # tests that only "real" implementations will pass

    # called by the TupleMatchingMixin methods

    @defer.inlineCallbacks
    def do_test_match(  # type: ignore[override]
        self, routingKey: tuple[str | None, ...], shouldMatch: bool, filter: tuple[str | None, ...]
    ) -> InlineCallbacksType[None]:
        cb = mock.Mock()
        yield self.mq.startConsuming(cb, filter)
        self.mq.produce(routingKey, 'x')  # type: ignore[arg-type]
        self.assertEqual(shouldMatch, cb.call_count == 1)
        if shouldMatch:
            cb.assert_called_once_with(routingKey, 'x')

    @defer.inlineCallbacks
    def test_stopConsuming(self) -> InlineCallbacksType[None]:
        cb = mock.Mock()
        qref = yield self.mq.startConsuming(cb, ('abc',))
        self.mq.produce(('abc',), {"x": 1})
        qref.stopConsuming()
        self.mq.produce(('abc',), {"x": 1})
        cb.assert_called_once_with(('abc',), {"x": 1})

    @defer.inlineCallbacks
    def test_stopConsuming_twice(self) -> InlineCallbacksType[None]:
        cb = mock.Mock()
        qref = yield self.mq.startConsuming(cb, ('abc',))
        qref.stopConsuming()
        qref.stopConsuming()
        # ..nothing bad happens

    @defer.inlineCallbacks
    def test_non_persistent(self) -> InlineCallbacksType[None]:
        cb = mock.Mock()
        qref = yield self.mq.startConsuming(cb, ('abc',))

        cb2 = mock.Mock()
        qref2 = yield self.mq.startConsuming(cb2, ('abc',))

        qref.stopConsuming()
        self.mq.produce(('abc',), '{}')  # type: ignore[arg-type]

        qref = yield self.mq.startConsuming(cb, ('abc',))
        qref.stopConsuming()
        qref2.stopConsuming()

        self.assertTrue(cb2.called)
        self.assertFalse(cb.called)

    @defer.inlineCallbacks
    def test_persistent(self) -> InlineCallbacksType[None]:
        cb = mock.Mock()

        qref = yield self.mq.startConsuming(cb, ('abc',), persistent_name='ABC')
        qref.stopConsuming()

        self.mq.produce(('abc',), '{}')  # type: ignore[arg-type]

        qref = yield self.mq.startConsuming(cb, ('abc',), persistent_name='ABC')
        qref.stopConsuming()

        self.assertTrue(cb.called)

    @defer.inlineCallbacks
    def test_waitUntilEvent_check_false(self) -> InlineCallbacksType[None]:
        d = self.mq.waitUntilEvent(('abc',), lambda: False)  # type: ignore[arg-type, return-value]
        self.assertEqual(d.called, False)
        self.mq.produce(('abc',), {"x": 1})
        self.assertEqual(d.called, True)
        res = yield d
        self.assertEqual(res, (('abc',), {"x": 1}))


class TestFakeMQ(TestReactorMixin, Tests, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantMq=True)
        self.mq = self.master.mq
        self.mq.verifyMessages = False  # type: ignore[attr-defined]


class TestSimpleMQ(TestReactorMixin, RealTests, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self)
        self.mq = simple.SimpleMQ()
        yield self.mq.setServiceParent(self.master)
