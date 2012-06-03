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

import mock
from twisted.trial import unittest
from buildbot.test.fake import fakemaster, fakemq
from buildbot.test.util import interfaces, topicmatching
from buildbot.mq import simple

class Tests(interfaces.InterfaceTests):

    def setUp(self):
        raise NotImplementedError

    def test_empty_produce(self):
        self.mq.produce(_type='a', _event='b', x=1)
        # ..nothing happens

    def test_signature_produce(self):
        @self.assertArgSpecMatches(self.mq.produce)
        def produce(self, **data):
            pass

    def test_signature_startConsuming(self):
        @self.assertArgSpecMatches(self.mq.startConsuming)
        # note that kwargs is really persistent_name=, but Python2's syntax
        # doesn't allow keyword args and *args to be mixed very well
        def startConsuming(self, callback, *topics, **kwargs):
            pass

    def test_signature_stopConsuming(self):
        cons = self.mq.startConsuming(lambda : None, 'topic')
        @self.assertArgSpecMatches(cons.stopConsuming)
        def stopConsuming(self):
            pass


class RealTests(topicmatching.TopicMatchingMixin, Tests):

    # tests that only "real" implementations will pass

    # called by the TopicMatchingMixin methods
    def do_test_match(self, routingKey, shouldMatch, *topics):
        cb = mock.Mock()
        self.mq.startConsuming(cb, *topics)
        self.mq.produce(routingKey, 'x')
        self.assertEqual(shouldMatch, cb.call_count == 1)
        if shouldMatch:
            cb.assert_called_once_with(routingKey, 'x')

    def test_stopConsuming(self):
        cb = mock.Mock()
        qref = self.mq.startConsuming(cb, 'abc')
        self.mq.produce('abc', dict(x=1))
        qref.stopConsuming()
        self.mq.produce('abc', dict(x=1))
        cb.assert_called_once_with('abc', dict(x=1))

    def test_stopConsuming_twice(self):
        cb = mock.Mock()
        qref = self.mq.startConsuming(cb, 'abc')
        qref.stopConsuming()
        qref.stopConsuming()
        # ..nothing bad happens

    def test_non_persistent(self):
        cb = mock.Mock()
        qref = self.mq.startConsuming(cb, 'abc')

        cb2 = mock.Mock()
        qref2 = self.mq.startConsuming(cb2, 'abc')

        qref.stopConsuming()
        self.mq.produce('abc', '{}')

        qref = self.mq.startConsuming(cb, 'abc')
        qref.stopConsuming()
        qref2.stopConsuming()

        self.assertTrue(cb2.called)
        self.assertFalse(cb.called)

    def test_persistent(self):
        cb = mock.Mock()

        qref = self.mq.startConsuming(cb, 'abc', persistent_name='ABC')
        qref.stopConsuming()

        self.mq.produce('abc', '{}')

        qref = self.mq.startConsuming(cb, 'abc', persistent_name='ABC')
        qref.stopConsuming()

        self.assertTrue(cb.called)


class TestFakeMQ(unittest.TestCase, Tests):

    def setUp(self):
        self.master = fakemaster.make_master()
        self.mq = fakemq.FakeMQConnector(self.master)

class TestSimpleMQ(unittest.TestCase, RealTests):

    def setUp(self):
        self.master = fakemaster.make_master()
        self.mq = simple.SimpleMQ(self.master)
