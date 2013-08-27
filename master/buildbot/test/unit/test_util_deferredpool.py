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

from twisted.trial import unittest
from twisted.internet import defer

from buildbot.util.deferredpool import DeferredPool

class TestDeferredPool(unittest.TestCase):
    
    def test_trivial(self):
        dp = DeferredPool()
        d = dp.notifyWhenEmpty()
        # This should be a trival deferred
        self.assertEqual(d.called, True)
        self.assertEqual(d.result, None)
        return d

    def test_trivial_not_immediately(self):
        dp = DeferredPool()
        d = dp.notifyWhenEmpty(testImmediately=False)
        self.assertNoResult(d)

    def test_simple(self):
        dp = DeferredPool()
        d1 = dp.notifyWhenEmpty(testImmediately=False)
        self.assertNoResult(d1)

        deferred = defer.Deferred()
        expected_value = object()

        dp.add(deferred)
        d2 = dp.notifyWhenEmpty()

        # These deferreds haven't been called yet.
        self.assertNoResult(deferred)
        self.assertNoResult(d1)
        self.assertNoResult(d2)

        deferred.callback(expected_value)

        # These deferreds have now been called.
        self.assertIdentical(d1.result, None)
        self.assertIdentical(d2.result, None)
        self.assertIdentical(deferred.result, expected_value)
    
    def test_errback(self):
        dp = DeferredPool()
        d1 = dp.notifyWhenEmpty(testImmediately=False)
        self.assertNoResult(d1)

        deferred = defer.Deferred()
        expected_value = Exception('wat')

        dp.add(deferred)
        d2 = dp.notifyWhenEmpty()

        # These deferreds haven't been called yet.
        self.assertNoResult(deferred)
        self.assertNoResult(d1)
        self.assertNoResult(d2)

        deferred.errback(expected_value)

        # These deferreds have now been called.
        self.assertIdentical(d1.result, None)
        self.assertIdentical(d2.result, None)
        self.assertFailure(deferred, Exception)
        self.assertIdentical(deferred.result, expected_value)

    def test_multiple(self):
        dp = DeferredPool()
        d1 = dp.notifyWhenEmpty(testImmediately=False)
        self.assertNoResult(d1)

        d_list = []
        for i in range(10):
            d_list.append(defer.Deferred())
            dp.add(d_list[i])
        d2 = dp.notifyWhenEmpty()

        # These deferreds haven't been called yet.
        for i, d in enumerate(d_list):
            self.assertNoResult(d)
            self.assertNoResult(d1)
            self.assertNoResult(d2)
            d.callback(i)
            self.assertEqual(d.result, i)

        # These deferreds have now been called.
        self.assertEqual(d1.result, None)
        self.assertEqual(d2.result, None)

    def test_multiple_chained(self):
        dp = DeferredPool()
        d1 = dp.notifyWhenEmpty(testImmediately=False)
        self.assertNoResult(d1)

        prev_deferred = defer.Deferred()
        dp.add(prev_deferred)
        d2 = dp.notifyWhenEmpty()

        # These deferreds haven't been called yet.
        for i in range(10):
            self.assertNoResult(prev_deferred)
            self.assertNoResult(d1)
            self.assertNoResult(d2)
            curr_deferred = defer.Deferred()
            dp.add(curr_deferred)
            prev_deferred.callback(i)
            self.assertEqual(prev_deferred.result, i)
            prev_deferred = curr_deferred

        self.assertNoResult(prev_deferred)
        self.assertNoResult(d1)
        self.assertNoResult(d2)

        prev_deferred.callback(10)
        self.assertEqual(prev_deferred.result, 10)

        # These deferreds have now been called.
        self.assertEqual(d1.result, None)
        self.assertEqual(d2.result, None)

    def test_reuse(self):
        dp = DeferredPool()

        for i in range(10):
            d1 = dp.notifyWhenEmpty(testImmediately=False)
            self.assertNoResult(d1)
            d = defer.Deferred()
            dp.add(d)
            d2 = dp.notifyWhenEmpty()

            # These deferreds haven't been called yet.
            self.assertNoResult(d)
            self.assertNoResult(d1)
            self.assertNoResult(d2)

            d.callback(i)

            # These deferreds have now been called.
            self.assertEqual(d.result, i)
            self.assertEqual(d1.result, None)
            self.assertEqual(d2.result, None)
