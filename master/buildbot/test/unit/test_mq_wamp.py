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
from future.builtins import range

import json
import os
import textwrap

import mock

from autobahn.wamp.types import SubscribeOptions
from twisted.internet import defer
from twisted.trial import unittest

from buildbot.mq import wamp
from buildbot.test.fake import fakemaster
from buildbot.wamp import connector


class FakeEventDetails(object):
    def __init__(self, topic):
        self.topic = topic


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
        for i in range(len(topic)):
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
        details = FakeEventDetails(topic=topic)
        self.qref_cb(json.loads(json.dumps(data)), details=details)


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

    """
        Stimulate the code with a fake wamp router:
        A router which only accepts one subscriber on one topic
    """

    def setUp(self):
        self.master = fakemaster.make_master()
        self.master.wamp = FakeWampConnector()
        self.mq = wamp.WampMQ()
        self.mq.setServiceParent(self.master)

    @defer.inlineCallbacks
    def test_startConsuming_basic(self):
        self.master.wamp.subscribe = mock.Mock()
        yield self.mq.startConsuming(None, ('a', 'b'))
        options = ComparableSubscribeOptions(details_arg='details')
        self.master.wamp.subscribe.assert_called_with(
            mock.ANY, u'org.buildbot.mq.a.b', options=options)

    @defer.inlineCallbacks
    def test_startConsuming_wildcard(self):
        self.master.wamp.subscribe = mock.Mock()
        yield self.mq.startConsuming(None, ('a', None))
        options = ComparableSubscribeOptions(
            match=u"wildcard", details_arg='details')
        self.master.wamp.subscribe.assert_called_with(
            mock.ANY, u'org.buildbot.mq.a.', options=options)

    @defer.inlineCallbacks
    def test_forward_data(self):
        callback = mock.Mock()
        yield self.mq.startConsuming(callback, ('a', 'b'))
        # _produce returns a deferred
        yield self.mq._produce(('a', 'b'), 'foo')
        # calling produce should eventually call the callback with decoding of
        # topic
        callback.assert_called_with(('a', 'b'), 'foo')
        self.assertEqual(self.master.wamp.last_data, u'foo')

    @defer.inlineCallbacks
    def test_forward_data_wildcard(self):
        callback = mock.Mock()
        yield self.mq.startConsuming(callback, ('a', None))
        # _produce returns a deferred
        yield self.mq._produce(('a', 'b'), 'foo')
        # calling produce should eventually call the callback with decoding of
        # topic
        callback.assert_called_with(('a', 'b'), 'foo')
        self.assertEqual(self.master.wamp.last_data, u'foo')


class FakeConfig(object):
    mq = dict(type='wamp', router_url="wss://foo", realm="realm1")


class WampMQReal(unittest.TestCase):

    """
        Tests a little bit more painful to run, but which involve real communication with
        a wamp router
    """
    HOW_TO_RUN = textwrap.dedent("""\
        define WAMP_ROUTER_URL to a wamp router to run this test
        > crossbar init
        > crossbar start &
        > export WAMP_ROUTER_URL=ws://localhost:8080/ws
        > trial buildbot.unit.test_mq_wamp""")
    # if connection is bad, this test can timeout easily
    # we reduce the timeout to help maintain the sanity of the developer
    timeout = 2

    @defer.inlineCallbacks
    def setUp(self):
        if "WAMP_ROUTER_URL" not in os.environ:
            raise unittest.SkipTest(self.HOW_TO_RUN)
        self.master = fakemaster.make_master()
        self.mq = wamp.WampMQ()
        yield self.mq.setServiceParent(self.master)
        self.connector = self.master.wamp = connector.WampConnector()
        yield self.connector.setServiceParent(self.master)
        yield self.master.startService()
        config = FakeConfig()
        config.mq['router_url'] = os.environ["WAMP_ROUTER_URL"]
        yield self.connector.reconfigServiceWithBuildbotConfig(config)

    def tearDown(self):
        return self.master.stopService()

    @defer.inlineCallbacks
    def test_forward_data(self):
        d = defer.Deferred()
        callback = mock.Mock(side_effect=lambda *a, **kw: d.callback(None))
        yield self.mq.startConsuming(callback, ('a', 'b'))
        # _produce returns a deferred
        yield self.mq._produce(('a', 'b'), 'foo')
        # calling produce should eventually call the callback with decoding of
        # topic
        yield d
        callback.assert_called_with(('a', 'b'), 'foo')

    @defer.inlineCallbacks
    def test_forward_data_wildcard(self):
        d = defer.Deferred()
        callback = mock.Mock(side_effect=lambda *a, **kw: d.callback(None))
        yield self.mq.startConsuming(callback, ('a', None))
        # _produce returns a deferred
        yield self.mq._produce(('a', 'b'), 'foo')
        # calling produce should eventually call the callback with decoding of
        # topic
        yield d
        callback.assert_called_with(('a', 'b'), 'foo')
