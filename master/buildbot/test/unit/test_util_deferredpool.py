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
from twisted.trial import unittest

from buildbot.util.deferredpool import DeferredPool


class TestPool(unittest.TestCase):

    """
    Test the L{DeferredPool} class used by L{ResizableDispatchQueue}.
    """

    def testEmptyPoolStatus(self):
        """
        A newly created (empty) pool should have no deferreds in progress
        and no deferreds waiting for the pool to drain.
        """
        pool = DeferredPool()
        self.assertEqual(pool.status(), (0, 0))

    def testPoolDeferredCount(self):
        """
        The pool must correctly report how many deferreds it has underway.
        """
        pool = DeferredPool()
        pool.add(defer.Deferred())
        pool.add(defer.Deferred())
        self.assertEqual(pool.status(), (2, 0))

    def testPoolWaitingCount(self):
        """
        The pool must correctly report how many deferreds are waiting
        for it to drain.
        """
        pool = DeferredPool()
        pool.notifyWhenEmpty(testImmediately=False)
        pool.notifyWhenEmpty(testImmediately=False)
        self.assertEqual(pool.status(), (0, 2))

    def testPoolStatus(self):
        """
        The pool must correctly report how many deferreds are underway
        and how many are waiting for it to drain.
        """
        pool = DeferredPool()
        pool.add(defer.Deferred())
        pool.add(defer.Deferred())
        pool.notifyWhenEmpty(testImmediately=False)
        self.assertEqual(pool.status(), (2, 1))

    def testPoolStatusAfterDeferredIsCallbacked(self):
        """
        The pool must correctly report how many deferreds are underway
        and how many are waiting for it to drain after one of its underway
        deferreds is callbacked.
        """
        pool = DeferredPool()
        d = defer.Deferred()
        pool.add(d)
        pool.add(defer.Deferred())
        self.assertEqual(pool.status(), (2, 0))
        d.callback(None)
        self.assertEqual(pool.status(), (1, 0))

    def testPoolStatusAfterDeferredIsErrbacked(self):
        """
        The pool must correctly report how many deferreds are underway
        and how many are waiting for it to drain after one of its underway
        deferreds is errbacked.
        """
        pool = DeferredPool()
        d = defer.Deferred()
        d.addErrback(lambda _: True)
        pool.add(d)
        pool.add(defer.Deferred())
        self.assertEqual(pool.status(), (2, 0))
        d.errback(Exception())
        self.assertEqual(pool.status(), (1, 0))

    def testCallbackedDeferredFiresWithTheRightResult(self):
        """
        The pool must correctly pass the original deferred callback result
        through any callbacks it might have added.
        """
        pool = DeferredPool()
        d = defer.Deferred()
        pool.add(d)
        pool.notifyWhenEmpty()
        expectedValue = object()
        d.callback(expectedValue)
        self.assertIdentical(d.result, expectedValue)

    def testErrbackedDeferredFiresWithTheRightResult(self):
        """
        The pool must correctly pass the original deferred errback result
        through any callbacks it might have added.
        """
        expectedValue = Exception()
        pool = DeferredPool()
        d = defer.Deferred()
        pool.add(d)
        pool.notifyWhenEmpty()
        d.errback(expectedValue)
        self.assertIdentical(d.result.value, expectedValue)
        return self.assertFailure(d, Exception)

    def testEmptyPoolWithTestImmediatelyTrue(self):
        """
        If the pool is empty and C{testImmediately} is C{True} when
        calling L{notifyWhenEmpty}, an already fired (with C{None} result)
        deferred must be returned and the pool should be empty.
        """
        pool = DeferredPool()
        d = pool.notifyWhenEmpty(testImmediately=True)
        self.assertEqual(d.called, True)
        self.assertEqual(d.result, None)
        self.assertEqual(pool.status(), (0, 0))

    def testEmptyPoolWithTestImmediatelyFalse(self):
        """
        If the pool is empty and C{testImmediately} is C{False} when
        calling L{notifyWhenEmpty}, the returned deferred must not have
        already fired and the pool should contain one waiting deferred.
        """
        pool = DeferredPool()
        d = pool.notifyWhenEmpty(testImmediately=False)
        self.assertEqual(d.called, False)
        self.assertEqual(pool.status(), (0, 1))

    def testNonEmptyPoolWithTestImmediatelyTrue(self):
        """
        If the pool is not empty and C{testImmediately} is C{True} when
        calling L{notifyWhenEmpty}, the returned deferred must not have
        already fired and the pool should contain one underway deferred
        and one waiting.
        """
        pool = DeferredPool()
        pool.add(defer.Deferred())
        d = pool.notifyWhenEmpty(testImmediately=True)
        self.assertEqual(d.called, False)
        self.assertEqual(pool.status(), (1, 1))

    def testPoolEmpties(self):
        """
        If all the deferreds in a pool fire, its underway list should be empty.
        """
        pool = DeferredPool()
        d1 = defer.Deferred()
        d2 = defer.Deferred()
        d3 = defer.Deferred()
        pool.add(d1)
        pool.add(d2)
        pool.add(d3)
        self.assertEqual(pool.status(), (3, 0))
        d1.callback(None)
        d2.callback(None)
        d3.callback(None)
        self.assertEqual(pool.status(), (0, 0))

    def testNotifyWhenPoolEmpties(self):
        """
        After all the deferreds in a pool fire, it should call all notify
        callbacks.
        """
        pool = DeferredPool()
        d1 = defer.Deferred()
        d2 = defer.Deferred()
        d3 = defer.Deferred()
        pool.add(d1)
        pool.add(d2)
        pool.add(d3)
        # There must be 3 deferreds underway.
        self.assertEqual(pool.status(), (3, 0))
        wait1 = pool.notifyWhenEmpty()
        wait2 = pool.notifyWhenEmpty()
        # There must be 3 deferreds underway and 2 waiting.
        self.assertEqual(pool.status(), (3, 2))
        d1.callback(None)
        d2.callback(None)
        # There must be 1 deferreds underway and 2 waiting.
        self.assertEqual(pool.status(), (1, 2))
        # The waiters must not have fired yet.
        self.assertEqual(wait1.called, False)
        self.assertEqual(wait2.called, False)
        d3.callback(None)
        # Both waiters must have fired (with None) & the pool must be empty.
        self.assertEqual(wait1.called, True)
        self.assertEqual(wait2.called, True)
        self.assertEqual(pool.status(), (0, 0))
        self.assertEqual(wait1.result, None)
        self.assertEqual(wait2.result, None)


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
