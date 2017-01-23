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

from twisted.trial import unittest

from buildbot.util import subscription


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

        # subscribe
        self.subpt.subscribe(cb)
        try:
            self.subpt.deliver()
        except RuntimeError:
            self.fail("should not have seen exception here!")
        # log.err will cause Trial to complain about this error anyway, unless
        # we clean it up
        self.assertEqual(1, len(self.flushLoggedErrors(RuntimeError)))
