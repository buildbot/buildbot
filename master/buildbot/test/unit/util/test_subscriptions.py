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

from twisted.internet import defer
from twisted.python import failure
from twisted.trial import unittest

from buildbot.util import subscription


class TestException(Exception):
    pass


class subscriptions(unittest.TestCase):

    def setUp(self):
        self.subpt = subscription.SubscriptionPoint('test_sub')

    def test_str(self):
        self.assertIn('test_sub', str(self.subpt))

    def test_subscribe_unsubscribe(self):
        state = []

        def cb(*args, **kwargs):
            state.append((args, kwargs))

        # subscribe
        sub = self.subpt.subscribe(cb)
        self.assertTrue(isinstance(sub, subscription.Subscription))
        self.assertEqual(state, [])

        # deliver
        self.subpt.deliver(1, 2, a=3, b=4)
        self.assertEqual(state, [((1, 2), dict(a=3, b=4))])
        state.pop()

        # unsubscribe
        sub.unsubscribe()

        # don't receive events anymore
        self.subpt.deliver(3, 4)
        self.assertEqual(state, [])

    def test_exception(self):
        def cb(*args, **kwargs):
            raise RuntimeError('mah bucket!')

        self.subpt.subscribe(cb)
        self.subpt.deliver()  # should not raise

        exceptions = self.subpt.pop_exceptions()
        self.assertEqual(len(exceptions), 1)
        self.assertIsInstance(exceptions[0], RuntimeError)

        # log.err will cause Trial to complain about this error anyway, unless
        # we clean it up
        self.assertEqual(1, len(self.flushLoggedErrors(RuntimeError)))

    def test_deferred_exception(self):

        d = defer.Deferred()

        @defer.inlineCallbacks
        def cb_deferred(*args, **kwargs):
            yield d
            raise RuntimeError('msg')

        self.subpt.subscribe(cb_deferred)
        self.subpt.deliver()

        d.callback(None)

        exceptions = self.subpt.pop_exceptions()
        self.assertEqual(len(exceptions), 1)
        self.assertIsInstance(exceptions[0], failure.Failure)

        self.assertEqual(1, len(self.flushLoggedErrors(RuntimeError)))

    def test_deferred_exception_after_pop_exceptions(self):
        # waitForDeliveriesToFinish is forgotten to be called and exception happens after
        # pop_exceptions.
        d = defer.Deferred()

        @defer.inlineCallbacks
        def cb_deferred(*args, **kwargs):
            yield d
            raise TestException('msg')

        self.subpt.subscribe(cb_deferred)
        self.subpt.deliver()

        exceptions = self.subpt.pop_exceptions()

        d.callback(None)

        self.assertEqual(len(exceptions), 0)
        self.assertEqual(2, len(self.flushLoggedErrors(TestException)))

    def test_multiple_exceptions(self):

        d = defer.Deferred()

        @defer.inlineCallbacks
        def cb_deferred(*args, **kwargs):
            yield d
            raise RuntimeError('msg')

        def cb(*args, **kwargs):
            raise RuntimeError('msg')

        self.subpt.subscribe(cb_deferred)
        self.subpt.subscribe(cb)
        self.subpt.deliver()

        d.callback(None)

        exceptions = self.subpt.pop_exceptions()
        self.assertEqual(len(exceptions), 2)
        self.assertIsInstance(exceptions[0], RuntimeError)
        self.assertIsInstance(exceptions[1], failure.Failure)

        self.assertEqual(2, len(self.flushLoggedErrors(RuntimeError)))

    def test_deliveries_finished(self):
        state = []

        def create_cb(d):
            def cb(*args):
                state.append(args)
                return d
            return cb

        d1 = defer.Deferred()
        d2 = defer.Deferred()
        self.subpt.subscribe(create_cb(d1))
        self.subpt.subscribe(create_cb(d2))
        self.assertEqual(state, [])

        self.subpt.deliver(1, 2)
        self.assertEqual(state, [(1, 2), (1, 2)])

        d = self.subpt.waitForDeliveriesToFinish()
        self.assertFalse(d.called)

        d1.callback(None)
        self.assertFalse(d.called)

        d2.callback(None)
        self.assertTrue(d.called)

        # when there are no waiting deliveries, should call the callback immediately
        d = self.subpt.waitForDeliveriesToFinish()
        self.assertTrue(d.called)

    def test_deliveries_not_finished_within_callback(self):
        state = []

        def cb(*args):
            state.append(args)
            d = self.subpt.waitForDeliveriesToFinish()
            self.assertFalse(d.called)

        self.subpt.subscribe(cb)
        self.assertEqual(state, [])

        self.subpt.deliver(1, 2)
        self.assertEqual(state, [(1, 2)])
