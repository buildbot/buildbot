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

from __future__ import absolute_import
from __future__ import print_function

import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.mq import simple
from buildbot.test.fake import fakemaster
from buildbot.test.util import interfaces
from buildbot.test.util import tuplematching


class Tests(interfaces.InterfaceTests):

    def setUp(self):
        raise NotImplementedError

    def test_empty_produce(self):
        self.mq.produce(('a', 'b', 'c'), dict(x=1))
        # ..nothing happens

    def test_signature_produce(self):
        @self.assertArgSpecMatches(self.mq.produce)
        def produce(self, routingKey, data):
            pass

    def test_signature_startConsuming(self):
        @self.assertArgSpecMatches(self.mq.startConsuming)
        def startConsuming(self, callback, filter, persistent_name=None):
            pass

    @defer.inlineCallbacks
    def test_signature_stopConsuming(self):
        cons = yield self.mq.startConsuming(lambda: None, ('a',))

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

    @defer.inlineCallbacks
    def do_test_match(self, routingKey, shouldMatch, filter):
        cb = mock.Mock()
        yield self.mq.startConsuming(cb, filter)
        self.mq.produce(routingKey, 'x')
        self.assertEqual(shouldMatch, cb.call_count == 1)
        if shouldMatch:
            cb.assert_called_once_with(routingKey, 'x')

    @defer.inlineCallbacks
    def test_stopConsuming(self):
        cb = mock.Mock()
        qref = yield self.mq.startConsuming(cb, ('abc',))
        self.mq.produce(('abc',), dict(x=1))
        qref.stopConsuming()
        self.mq.produce(('abc',), dict(x=1))
        cb.assert_called_once_with(('abc',), dict(x=1))

    @defer.inlineCallbacks
    def test_stopConsuming_twice(self):
        cb = mock.Mock()
        qref = yield self.mq.startConsuming(cb, ('abc',))
        qref.stopConsuming()
        qref.stopConsuming()
        # ..nothing bad happens

    @defer.inlineCallbacks
    def test_non_persistent(self):
        cb = mock.Mock()
        qref = yield self.mq.startConsuming(cb, ('abc',))

        cb2 = mock.Mock()
        qref2 = yield self.mq.startConsuming(cb2, ('abc',))

        qref.stopConsuming()
        self.mq.produce(('abc',), '{}')

        qref = yield self.mq.startConsuming(cb, ('abc',))
        qref.stopConsuming()
        qref2.stopConsuming()

        self.assertTrue(cb2.called)
        self.assertFalse(cb.called)

    @defer.inlineCallbacks
    def test_persistent(self):
        cb = mock.Mock()

        qref = yield self.mq.startConsuming(cb, ('abc',), persistent_name='ABC')
        qref.stopConsuming()

        self.mq.produce(('abc',), '{}')

        qref = yield self.mq.startConsuming(cb, ('abc',), persistent_name='ABC')
        qref.stopConsuming()

        self.assertTrue(cb.called)

    @defer.inlineCallbacks
    def test_waitUntilEvent_check_false(self):
        d = self.mq.waitUntilEvent(('abc',), lambda: False)
        self.assertEqual(d.called, False)
        self.mq.produce(('abc',), dict(x=1))
        self.assertEqual(d.called, True)
        res = yield d
        self.assertEqual(res, (('abc',), dict(x=1)))
    timeout = 3  # those tests should not run long


class TestFakeMQ(unittest.TestCase, Tests):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self, wantMq=True)
        self.mq = self.master.mq
        self.mq.verifyMessages = False


class TestSimpleMQ(unittest.TestCase, RealTests):

    def setUp(self):
        self.master = fakemaster.make_master()
        self.mq = simple.SimpleMQ()
        self.mq.setServiceParent(self.master)
