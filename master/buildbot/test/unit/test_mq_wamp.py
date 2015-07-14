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

from autobahn.wamp.types import SubscribeOptions
from buildbot.mq import wamp
from twisted.internet import defer
from twisted.trial import unittest


class ComparableSubscribeOptions(SubscribeOptions):

    def __eq__(self, other):
        if not isinstance(other, SubscribeOptions):
            return False
        return self.match == other.match

    __repr__ = SubscribeOptions.__str__


class FakeWampConnector(object):
    # a fake wamp connector with only one queue

    def topic_match(self, topic):
        topic = topic.split(".")
        owntopic = self.topic.split(".")
        if len(topic) != len(owntopic):
            return False
        for i in xrange(len(topic)):
            if owntopic[i] != "" and topic[i] != owntopic[i]:
                return False
        return True

    def subscribe(self, callback, topic=None, options=None):
        # record the topic, and to make sure subsequent publish
        # are correct
        self.topic = topic
        # we record the qref_cb
        self.qref_cb = callback

    def publish(self, topic, data, options=None):
        # make sure the topic is compatible with what was subscribed
        assert self.topic_match(topic)
        self.last_data = data
        self.qref_cb(data)


class TopicMatch(unittest.TestCase):
    # test unit tests

    def test_topic_match(self):
        matches = [("a.b.c", "a.b.c"),
                   ("a..c", "a.c.c"),
                   ("a.b.", "a.b.c"),
                   (".b.", "a.b.c"),
                   ]
        for i, j in matches:
            w = FakeWampConnector()
            w.topic = i
            self.assertTrue(w.topic_match(j))

    def test_topic_not_match(self):
        matches = [("a.b.c", "a.b.d"),
                   ("a..c", "a.b.d"),
                   ("a.b.", "a.c.c"),
                   (".b.", "a.a.c"),
                   ]
        for i, j in matches:
            w = FakeWampConnector()
            w.topic = i
            self.assertFalse(w.topic_match(j))


class WampMQ(unittest.TestCase):

    def setUp(self):
        self.master = mock.Mock(name='master')
        self.master.wamp = FakeWampConnector()
        self.mq = wamp.WampMQ(self.master)

    @defer.inlineCallbacks
    def test_startConsuming_basic(self):
        self.master.wamp.subscribe = mock.Mock()
        yield self.mq.startConsuming(None, ('a', 'b'))
        self.master.wamp.subscribe.assert_called_with(mock.ANY, u'org.buildbot.mq.a.b', options=None)

    @defer.inlineCallbacks
    def test_startConsuming_wildcard(self):
        self.master.wamp.subscribe = mock.Mock()
        yield self.mq.startConsuming(None, ('a', None))
        options = ComparableSubscribeOptions(match=u"wildcard")
        self.master.wamp.subscribe.assert_called_with(mock.ANY, u'org.buildbot.mq.a.', options=options)

    @defer.inlineCallbacks
    def test_forward_data(self):
        callback = mock.Mock()
        yield self.mq.startConsuming(callback, ('a', 'b'))
        # _produce returns a deferred
        yield self.mq._produce(('a', 'b'), 'foo')
        # calling produce should eventually call the callback with decoding of topic
        callback.assert_called_with(('a', 'b'), 'foo')
        self.assertEqual(self.master.wamp.last_data, {'data': u'foo', 'topic': ('a', 'b')})

    @defer.inlineCallbacks
    def test_forward_data_wildcard(self):
        callback = mock.Mock()
        yield self.mq.startConsuming(callback, ('a', None))
        # _produce returns a deferred
        yield self.mq._produce(('a', 'b'), 'foo')
        # calling produce should eventually call the callback with decoding of topic
        callback.assert_called_with(('a', 'b'), 'foo')
        self.assertEqual(self.master.wamp.last_data, {'data': u'foo', 'topic': ('a', 'b')})
