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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.mq import simple
from buildbot.test.fake import fakemaster
from buildbot.test.util.misc import TestReactorMixin


class SimpleMQ(TestReactorMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self.setUpTestReactor()
        self.master = fakemaster.make_master(self)
        self.mq = simple.SimpleMQ()
        self.mq.setServiceParent(self.master)
        yield self.mq.startService()

    @defer.inlineCallbacks
    def tearDown(self):
        if self.mq.running:
            yield self.mq.stopService()

    @defer.inlineCallbacks
    def test_forward_data(self):
        callback = mock.Mock()
        yield self.mq.startConsuming(callback, ('a', 'b'))
        # _produce returns a deferred
        yield self.mq.produce(('a', 'b'), 'foo')
        # calling produce should eventually call the callback with decoding of
        # topic
        callback.assert_called_with(('a', 'b'), 'foo')

    @defer.inlineCallbacks
    def test_forward_data_wildcard(self):
        callback = mock.Mock()
        yield self.mq.startConsuming(callback, ('a', None))
        # _produce returns a deferred
        yield self.mq.produce(('a', 'b'), 'foo')
        # calling produce should eventually call the callback with decoding of
        # topic
        callback.assert_called_with(('a', 'b'), 'foo')

    @defer.inlineCallbacks
    def test_waits_for_called_callback(self):
        def callback(_, __):
            return defer.succeed(None)

        yield self.mq.startConsuming(callback, ('a', None))
        yield self.mq.produce(('a', 'b'), 'foo')

        d = self.mq.stopService()
        self.assertTrue(d.called)

    @defer.inlineCallbacks
    def test_waits_for_non_called_callback(self):
        d1 = defer.Deferred()

        def callback(_, __):
            return d1

        yield self.mq.startConsuming(callback, ('a', None))
        yield self.mq.produce(('a', 'b'), 'foo')

        d = self.mq.stopService()
        self.assertFalse(d.called)
        d1.callback(None)
        self.assertTrue(d.called)
