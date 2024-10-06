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

from unittest import mock

from twisted.trial import unittest

from buildbot.mq import simple
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import interfaces
from buildbot.test.util import tuplematching


class Tests(interfaces.InterfaceTests):
    def setUp(self):
        raise NotImplementedError

    def test_empty_produce(self):
        self.mq.produce(('a', 'b', 'c'), {"x": 1})
        # ..nothing happens

    def test_signature_produce(self):
        @self.assertArgSpecMatches(self.mq.produce)
        def produce(self, routingKey, data):
            pass

    def test_signature_startConsuming(self):
        @self.assertArgSpecMatches(self.mq.startConsuming)
        def startConsuming(self, callback, filter, persistent_name=None):
            pass

    async def test_signature_stopConsuming(self):
        cons = await self.mq.startConsuming(lambda: None, ('a',))

        @self.assertArgSpecMatches(cons.stopConsuming)
        def stopConsuming(self):
            pass

    def test_signature_waitUntilEvent(self):
        @self.assertArgSpecMatches(self.mq.waitUntilEvent)
        def waitUntilEvent(self, filter, check_callback):
            pass


class RealTests(tuplematching.TupleMatchingMixin, Tests):
    # tests that only "real" implementations will pass

    # called by the TupleMatchingMixin methods

    async def do_test_match(self, routingKey, shouldMatch, filter):
        cb = mock.Mock()
        await self.mq.startConsuming(cb, filter)
        self.mq.produce(routingKey, 'x')
        self.assertEqual(shouldMatch, cb.call_count == 1)
        if shouldMatch:
            cb.assert_called_once_with(routingKey, 'x')

    async def test_stopConsuming(self):
        cb = mock.Mock()
        qref = await self.mq.startConsuming(cb, ('abc',))
        self.mq.produce(('abc',), {"x": 1})
        qref.stopConsuming()
        self.mq.produce(('abc',), {"x": 1})
        cb.assert_called_once_with(('abc',), {"x": 1})

    async def test_stopConsuming_twice(self):
        cb = mock.Mock()
        qref = await self.mq.startConsuming(cb, ('abc',))
        qref.stopConsuming()
        qref.stopConsuming()
        # ..nothing bad happens

    async def test_non_persistent(self):
        cb = mock.Mock()
        qref = await self.mq.startConsuming(cb, ('abc',))

        cb2 = mock.Mock()
        qref2 = await self.mq.startConsuming(cb2, ('abc',))

        qref.stopConsuming()
        self.mq.produce(('abc',), '{}')

        qref = await self.mq.startConsuming(cb, ('abc',))
        qref.stopConsuming()
        qref2.stopConsuming()

        self.assertTrue(cb2.called)
        self.assertFalse(cb.called)

    async def test_persistent(self):
        cb = mock.Mock()

        qref = await self.mq.startConsuming(cb, ('abc',), persistent_name='ABC')
        qref.stopConsuming()

        self.mq.produce(('abc',), '{}')

        qref = await self.mq.startConsuming(cb, ('abc',), persistent_name='ABC')
        qref.stopConsuming()

        self.assertTrue(cb.called)

    async def test_waitUntilEvent_check_false(self):
        d = self.mq.waitUntilEvent(('abc',), lambda: False)
        self.assertEqual(d.called, False)
        self.mq.produce(('abc',), {"x": 1})
        self.assertEqual(d.called, True)
        res = await d
        self.assertEqual(res, (('abc',), {"x": 1}))


class TestFakeMQ(TestReactorMixin, unittest.TestCase, Tests):
    def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self, wantMq=True)
        self.mq = self.master.mq
        self.mq.verifyMessages = False


class TestSimpleMQ(TestReactorMixin, unittest.TestCase, RealTests):
    async def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self)
        self.mq = simple.SimpleMQ()
        await self.mq.setServiceParent(self.master)
