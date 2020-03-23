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

from parameterized import parameterized

import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.locks import BaseLock
from buildbot.locks import LockAccess
from buildbot.locks import MasterLock
from buildbot.locks import RealMasterLock
from buildbot.locks import RealWorkerLock
from buildbot.locks import WorkerLock
from buildbot.util.eventual import flushEventualQueue


class Requester:
    pass


class BaseLockTests(unittest.TestCase):

    @parameterized.expand([
        ('counting', 0, 0),
        ('counting', 0, 1),
        ('counting', 1, 1),
        ('counting', 0, 2),
        ('counting', 1, 2),
        ('counting', 2, 2),
        ('counting', 0, 3),
        ('counting', 1, 3),
        ('counting', 2, 3),
        ('counting', 3, 3),
        ('exclusive', 1, 1),
    ])
    def test_is_available_empty(self, mode, count, maxCount):
        req = Requester()
        lock = BaseLock('test', maxCount=maxCount)
        access = mock.Mock(spec=LockAccess)
        access.mode = mode
        access.count = count

        self.assertTrue(lock.isAvailable(req, access))

    @parameterized.expand([
        ('counting', 0, 0),
        ('counting', 0, 1),
        ('counting', 1, 1),
        ('counting', 0, 2),
        ('counting', 1, 2),
        ('counting', 2, 2),
        ('counting', 0, 3),
        ('counting', 1, 3),
        ('counting', 2, 3),
        ('counting', 3, 3),
        ('exclusive', 1, 1),
    ])
    def test_is_available_without_waiter(self, mode, count, maxCount):
        req = Requester()
        req_waiter = Requester()

        lock = BaseLock('test', maxCount=maxCount)
        access = mock.Mock(spec=LockAccess)
        access.mode = mode
        access.count = count

        lock.claim(req, access)
        lock.release(req, access)
        self.assertTrue(lock.isAvailable(req, access))
        self.assertTrue(lock.isAvailable(req_waiter, access))

    @parameterized.expand([
        ('counting', 1, 1),
        ('counting', 2, 2),
        ('counting', 3, 3),
        ('exclusive', 1, 1),
    ])
    def test_is_available_with_waiter(self, mode, count, maxCount):
        req = Requester()
        req_waiter = Requester()

        lock = BaseLock('test', maxCount=maxCount)
        access = mock.Mock(spec=LockAccess)
        access.mode = mode
        access.count = count

        lock.claim(req, access)
        lock.waitUntilMaybeAvailable(req_waiter, access)
        lock.release(req, access)
        self.assertFalse(lock.isAvailable(req, access))
        self.assertTrue(lock.isAvailable(req_waiter, access))

        lock.claim(req_waiter, access)
        lock.release(req_waiter, access)
        self.assertTrue(lock.isAvailable(req, access))
        self.assertTrue(lock.isAvailable(req_waiter, access))

    @parameterized.expand([
        ('counting', 1, 1),
        ('counting', 2, 2),
        ('counting', 3, 3),
        ('exclusive', 1, 1),
    ])
    def test_is_available_with_multiple_waiters(self, mode, count, maxCount):
        req = Requester()
        req_waiter1 = Requester()
        req_waiter2 = Requester()

        lock = BaseLock('test', maxCount=maxCount)
        access = mock.Mock(spec=LockAccess)
        access.mode = mode
        access.count = count

        lock.claim(req, access)
        lock.waitUntilMaybeAvailable(req_waiter1, access)
        lock.waitUntilMaybeAvailable(req_waiter2, access)
        lock.release(req, access)
        self.assertFalse(lock.isAvailable(req, access))
        self.assertTrue(lock.isAvailable(req_waiter1, access))
        self.assertFalse(lock.isAvailable(req_waiter2, access))

        lock.claim(req_waiter1, access)
        lock.release(req_waiter1, access)
        self.assertFalse(lock.isAvailable(req, access))
        self.assertFalse(lock.isAvailable(req_waiter1, access))
        self.assertTrue(lock.isAvailable(req_waiter2, access))

        lock.claim(req_waiter2, access)
        lock.release(req_waiter2, access)
        self.assertTrue(lock.isAvailable(req, access))
        self.assertTrue(lock.isAvailable(req_waiter1, access))
        self.assertTrue(lock.isAvailable(req_waiter2, access))

    def test_is_available_with_multiple_waiters_multiple_counting(self):
        req1 = Requester()
        req2 = Requester()
        req_waiter1 = Requester()
        req_waiter2 = Requester()
        req_waiter3 = Requester()

        lock = BaseLock('test', maxCount=2)
        access = mock.Mock(spec=LockAccess)
        access.mode = 'counting'
        access.count = 1

        lock.claim(req1, access)
        lock.claim(req2, access)
        lock.waitUntilMaybeAvailable(req_waiter1, access)
        lock.waitUntilMaybeAvailable(req_waiter2, access)
        lock.waitUntilMaybeAvailable(req_waiter3, access)
        lock.release(req1, access)
        lock.release(req2, access)
        self.assertFalse(lock.isAvailable(req1, access))
        self.assertTrue(lock.isAvailable(req_waiter1, access))
        self.assertTrue(lock.isAvailable(req_waiter2, access))
        self.assertFalse(lock.isAvailable(req_waiter3, access))

        lock.claim(req_waiter1, access)
        lock.release(req_waiter1, access)
        self.assertFalse(lock.isAvailable(req1, access))
        self.assertFalse(lock.isAvailable(req_waiter1, access))
        self.assertTrue(lock.isAvailable(req_waiter2, access))
        self.assertTrue(lock.isAvailable(req_waiter3, access))

        lock.claim(req_waiter2, access)
        lock.release(req_waiter2, access)
        self.assertTrue(lock.isAvailable(req1, access))
        self.assertTrue(lock.isAvailable(req_waiter1, access))
        self.assertTrue(lock.isAvailable(req_waiter2, access))
        self.assertTrue(lock.isAvailable(req_waiter3, access))

        lock.claim(req_waiter3, access)
        lock.release(req_waiter3, access)
        self.assertTrue(lock.isAvailable(req1, access))
        self.assertTrue(lock.isAvailable(req_waiter1, access))
        self.assertTrue(lock.isAvailable(req_waiter2, access))
        self.assertTrue(lock.isAvailable(req_waiter3, access))

    def test_is_available_with_mult_waiters_mult_counting_set_maxCount(self):
        req1 = Requester()
        req2 = Requester()
        req_waiter1 = Requester()
        req_waiter2 = Requester()
        req_waiter3 = Requester()

        lock = BaseLock('test', maxCount=2)
        access = mock.Mock(spec=LockAccess)
        access.mode = 'counting'
        access.count = 1

        lock.claim(req1, access)
        lock.claim(req2, access)
        lock.waitUntilMaybeAvailable(req_waiter1, access)
        lock.waitUntilMaybeAvailable(req_waiter2, access)
        lock.waitUntilMaybeAvailable(req_waiter3, access)
        lock.release(req1, access)
        lock.release(req2, access)
        self.assertFalse(lock.isAvailable(req1, access))
        self.assertTrue(lock.isAvailable(req_waiter1, access))
        self.assertTrue(lock.isAvailable(req_waiter2, access))
        self.assertFalse(lock.isAvailable(req_waiter3, access))

        lock.setMaxCount(4)
        self.assertTrue(lock.isAvailable(req1, access))
        self.assertTrue(lock.isAvailable(req_waiter1, access))
        self.assertTrue(lock.isAvailable(req_waiter2, access))
        self.assertTrue(lock.isAvailable(req_waiter3, access))

        lock.claim(req_waiter1, access)
        lock.release(req_waiter1, access)
        self.assertTrue(lock.isAvailable(req1, access))
        self.assertTrue(lock.isAvailable(req_waiter1, access))
        self.assertTrue(lock.isAvailable(req_waiter2, access))
        self.assertTrue(lock.isAvailable(req_waiter3, access))

        lock.setMaxCount(2)
        lock.waitUntilMaybeAvailable(req_waiter1, access)
        lock.claim(req_waiter2, access)
        lock.release(req_waiter2, access)
        self.assertFalse(lock.isAvailable(req1, access))
        self.assertTrue(lock.isAvailable(req_waiter1, access))
        self.assertFalse(lock.isAvailable(req_waiter2, access))
        self.assertTrue(lock.isAvailable(req_waiter3, access))

        lock.claim(req_waiter3, access)
        lock.release(req_waiter3, access)
        self.assertTrue(lock.isAvailable(req1, access))
        self.assertTrue(lock.isAvailable(req_waiter1, access))
        self.assertTrue(lock.isAvailable(req_waiter2, access))
        self.assertTrue(lock.isAvailable(req_waiter3, access))

        lock.claim(req_waiter1, access)
        lock.release(req_waiter1, access)

    @parameterized.expand([
        ('counting', 1, 1),
        ('counting', 2, 2),
        ('counting', 3, 3),
        ('exclusive', 1, 1),
    ])
    def test_duplicate_wait_until_maybe_available_throws(self, mode, count,
            maxCount):
        req = Requester()
        req_waiter = Requester()

        lock = BaseLock('test', maxCount=maxCount)
        access = mock.Mock(spec=LockAccess)
        access.mode = mode
        access.count = count

        lock.claim(req, access)
        lock.waitUntilMaybeAvailable(req_waiter, access)
        with self.assertRaises(AssertionError):
            lock.waitUntilMaybeAvailable(req_waiter, access)
        lock.release(req, access)

    @parameterized.expand([
        ('counting', 1, 1),
        ('counting', 2, 2),
        ('counting', 3, 3),
        ('exclusive', 1, 1),
    ])
    def test_stop_waiting_ensures_deferred_was_previous_result_of_wait(self,
            mode, count, maxCount):
        req = Requester()
        req_waiter = Requester()

        lock = BaseLock('test', maxCount=maxCount)
        access = mock.Mock(spec=LockAccess)
        access.mode = mode
        access.count = count

        lock.claim(req, access)

        lock.waitUntilMaybeAvailable(req_waiter, access)
        with self.assertRaises(AssertionError):
            wrong_d = defer.Deferred()
            lock.stopWaitingUntilAvailable(req_waiter, access, wrong_d)

        lock.release(req, access)

    @parameterized.expand([
        ('counting', 1, 1),
        ('counting', 2, 2),
        ('counting', 3, 3),
        ('exclusive', 1, 1),
    ])
    def test_stop_waiting_fires_deferred_if_not_woken(self, mode, count,
            maxCount):
        req = Requester()
        req_waiter = Requester()

        lock = BaseLock('test', maxCount=maxCount)
        access = mock.Mock(spec=LockAccess)
        access.mode = mode
        access.count = count

        lock.claim(req, access)
        d = lock.waitUntilMaybeAvailable(req_waiter, access)
        lock.stopWaitingUntilAvailable(req_waiter, access, d)
        self.assertTrue(d.called)

        lock.release(req, access)

    @parameterized.expand([
        ('counting', 1, 1),
        ('counting', 2, 2),
        ('counting', 3, 3),
        ('exclusive', 1, 1),
    ])
    @defer.inlineCallbacks
    def test_stop_waiting_does_not_fire_deferred_if_already_woken(self, mode,
            count, maxCount):
        req = Requester()
        req_waiter = Requester()

        lock = BaseLock('test', maxCount=maxCount)
        access = mock.Mock(spec=LockAccess)
        access.mode = mode
        access.count = count

        lock.claim(req, access)
        d = lock.waitUntilMaybeAvailable(req_waiter, access)
        lock.release(req, access)
        yield flushEventualQueue()
        self.assertTrue(d.called)

        # note that if the function calls the deferred again, an exception would be thrown from
        # inside Twisted.
        lock.stopWaitingUntilAvailable(req_waiter, access, d)

    @parameterized.expand([
        ('counting', 1, 1),
        ('counting', 2, 2),
        ('counting', 3, 3),
        ('exclusive', 1, 1),
    ])
    def test_stop_waiting_does_not_raise_after_release(self, mode, count,
            maxCount):
        req = Requester()
        req_waiter = Requester()

        lock = BaseLock('test', maxCount=maxCount)
        access = mock.Mock(spec=LockAccess)
        access.mode = mode
        access.count = count

        lock.claim(req, access)
        d = lock.waitUntilMaybeAvailable(req_waiter, access)
        lock.release(req, access)
        self.assertFalse(lock.isAvailable(req, access))
        self.assertTrue(lock.isAvailable(req_waiter, access))

        lock.stopWaitingUntilAvailable(req_waiter, access, d)

        lock.claim(req_waiter, access)
        lock.release(req_waiter, access)

    @parameterized.expand([
        ('counting', 1, 1),
        ('counting', 2, 2),
        ('counting', 3, 3),
        ('exclusive', 1, 1),
    ])
    def test_stop_waiting_removes_non_called_waiter(self, mode, count, maxCount):
        req = Requester()
        req_waiter1 = Requester()
        req_waiter2 = Requester()

        lock = BaseLock('test', maxCount=maxCount)
        access = mock.Mock(spec=LockAccess)
        access.mode = mode
        access.count = count

        lock.claim(req, access)
        d1 = lock.waitUntilMaybeAvailable(req_waiter1, access)
        d2 = lock.waitUntilMaybeAvailable(req_waiter2, access)
        lock.release(req, access)
        yield flushEventualQueue()

        self.assertFalse(lock.isAvailable(req, access))
        self.assertTrue(lock.isAvailable(req_waiter1, access))
        self.assertFalse(lock.isAvailable(req_waiter2, access))
        self.assertTrue(d1.called)

        lock.stopWaitingUntilAvailable(req_waiter2, access, d2)
        self.assertFalse(lock.isAvailable(req, access))
        self.assertTrue(lock.isAvailable(req_waiter1, access))
        self.assertFalse(lock.isAvailable(req_waiter2, access))

        lock.claim(req_waiter1, access)
        lock.release(req_waiter1, access)
        self.assertTrue(lock.isAvailable(req, access))
        self.assertTrue(lock.isAvailable(req_waiter1, access))
        self.assertTrue(lock.isAvailable(req_waiter2, access))

    @parameterized.expand([
        ('counting', 1, 1),
        ('counting', 2, 2),
        ('counting', 3, 3),
        ('exclusive', 1, 1),
    ])
    @defer.inlineCallbacks
    def test_stop_waiting_wakes_up_next_deferred_if_already_woken(self, mode,
            count, maxCount):
        req = Requester()
        req_waiter1 = Requester()
        req_waiter2 = Requester()

        lock = BaseLock('test', maxCount=maxCount)
        access = mock.Mock(spec=LockAccess)
        access.mode = mode
        access.count = count

        lock.claim(req, access)
        d1 = lock.waitUntilMaybeAvailable(req_waiter1, access)
        d2 = lock.waitUntilMaybeAvailable(req_waiter2, access)
        lock.release(req, access)
        yield flushEventualQueue()

        self.assertTrue(d1.called)
        self.assertFalse(d2.called)

        lock.stopWaitingUntilAvailable(req_waiter1, access, d1)

        yield flushEventualQueue()
        self.assertTrue(d2.called)

    @parameterized.expand([
        ('counting', 1, 1),
        ('counting', 2, 2),
        ('counting', 3, 3),
        ('exclusive', 1, 1),
    ])
    def test_can_release_non_waited_lock(self, mode, count, maxCount):
        req = Requester()
        req_not_waited = Requester()

        lock = BaseLock('test', maxCount=maxCount)
        access = mock.Mock(spec=LockAccess)
        access.mode = mode
        access.count = count

        lock.release(req_not_waited, access)

        lock.claim(req, access)
        lock.release(req, access)
        yield flushEventualQueue()

        lock.release(req_not_waited, access)

    @parameterized.expand([
        ('counting', 'counting', 1, 1, 1),
        ('counting', 'exclusive', 1, 1, 1),
        ('exclusive', 'counting', 1, 1, 1),
        ('exclusive', 'exclusive', 1, 1, 1),
    ])
    @defer.inlineCallbacks
    def test_release_calls_waiters_in_fifo_order(self, mode1, mode2, count1,
            count2, maxCount):
        req = Requester()

        req_waiters = [Requester() for _ in range(5)]

        lock = BaseLock('test', maxCount=maxCount)
        access1 = mock.Mock(spec=LockAccess)
        access1.mode = mode1
        access1.count = count1
        access2 = mock.Mock(spec=LockAccess)
        access2.mode = mode2
        access2.count = count2

        accesses = [access1, access2, access1, access2, access1]
        expected_called = [False] * 5

        lock.claim(req, access1)
        deferreds = [lock.waitUntilMaybeAvailable(req_waiter, access)
                     for req_waiter, access in zip(req_waiters, accesses)]
        self.assertEqual([d.called for d in deferreds], expected_called)

        lock.release(req, access1)
        yield flushEventualQueue()

        expected_called[0] = True
        self.assertEqual([d.called for d in deferreds], expected_called)

        for i in range(4):
            self.assertTrue(lock.isAvailable(req_waiters[i], accesses[i]))

            lock.claim(req_waiters[i], accesses[i])
            self.assertEqual([d.called for d in deferreds], expected_called)

            lock.release(req_waiters[i], accesses[i])
            yield flushEventualQueue()

            expected_called[i + 1] = True
            self.assertEqual([d.called for d in deferreds], expected_called)

        lock.claim(req_waiters[4], accesses[4])
        lock.release(req_waiters[4], accesses[4])

    @parameterized.expand([
        (1, ),
    ])
    @defer.inlineCallbacks
    def test_release_calls_multiple_waiters_on_release(self, count):
        req = Requester()

        req_waiters = [Requester() for _ in range(5)]

        lock = BaseLock('test', maxCount=5)
        access_counting = mock.Mock(spec=LockAccess)
        access_counting.mode = 'counting'
        access_counting.count = count
        access_excl = mock.Mock(spec=LockAccess)
        access_excl.mode = 'exclusive'
        access_excl.count = 1

        lock.claim(req, access_excl)
        deferreds = [lock.waitUntilMaybeAvailable(req_waiter, access_counting)
                     for req_waiter in req_waiters]
        self.assertEqual([d.called for d in deferreds], [False] * 5)

        lock.release(req, access_excl)
        yield flushEventualQueue()

        self.assertEqual([d.called for d in deferreds], [True] * 5)

    @parameterized.expand([
        (1, 1),
    ])
    @defer.inlineCallbacks
    def test_release_calls_multiple_waiters_on_setMaxCount(self, count,
            maxCount):
        req = Requester()

        req_waiters = [Requester() for _ in range(5)]

        lock = BaseLock('test', maxCount=maxCount)
        access_counting = mock.Mock(spec=LockAccess)
        access_counting.mode = 'counting'
        access_counting.count = count

        lock.claim(req, access_counting)
        deferreds = [lock.waitUntilMaybeAvailable(req_waiter, access_counting)
                     for req_waiter in req_waiters]
        self.assertEqual([d.called for d in deferreds], [False] * 5)

        lock.release(req, access_counting)
        yield flushEventualQueue()

        self.assertEqual([d.called for d in deferreds], [True] + [False] * 4)

        lock.setMaxCount(5)
        yield flushEventualQueue()

        self.assertEqual([d.called for d in deferreds], [True] * 5)

    @parameterized.expand([
        (2, 2),
        (3, 3),
        (4, 4),
        (5, 5),
    ])
    def test_exclusive_must_have_count_one(self, count,
            maxCount):
        req = Requester()

        lock = BaseLock('test', maxCount=maxCount)
        access = mock.Mock(spec=LockAccess)
        access.mode = 'exclusive'
        access.count = count

        with self.assertRaises(AssertionError):
            lock.claim(req, access)

    @parameterized.expand([
        (0, 1),
        (1, 1),
        (0, 2),
        (1, 2),
        (2, 2),
        (0, 3),
        (1, 3),
        (2, 3),
        (3, 3),
    ])
    def test_counting_count_zero_always_succeeds(self, count,
            maxCount):

        reqs = [Requester() for _ in range(10)]
        req_waiters = [Requester() for _ in range(10)]
        req_nonzero = Requester()

        lock = BaseLock('test', maxCount=maxCount)
        access_zero = mock.Mock(spec=LockAccess)
        access_zero.mode = 'counting'
        access_zero.count = 0

        access_nonzero = mock.Mock(spec=LockAccess)
        access_nonzero.mode = 'counting'
        access_nonzero.count = count

        lock.claim(req_nonzero, access_nonzero)
        for req in reqs:
            self.assertTrue(lock.isAvailable(req, access_zero))
            lock.claim(req, access_zero)
        for req_waiter in req_waiters:
            self.assertTrue(lock.isAvailable(req_waiter, access_zero))
        for req in reqs:
            self.assertTrue(lock.isAvailable(req, access_zero))
            lock.release(req, access_zero)
        lock.release(req_nonzero, access_nonzero)

    @parameterized.expand([
        (1, 0),
        (2, 0),
        (2, 1),
        (3, 0),
        (3, 1),
        (3, 2),
    ])
    def test_count_cannot_be_larger_than_maxcount(self, count,
            maxCount):

        req = Requester()

        lock = BaseLock('test', maxCount=maxCount)
        access = mock.Mock(spec=LockAccess)
        access.mode = 'counting'
        access.count = count

        self.assertFalse(lock.isAvailable(req, access))

    @parameterized.expand([
        (0, 1, 1),
        (0, 1, 2),
        (1, 2, 3),
        (1, 2, 4),
        (1, 3, 4),
        (1, 3, 5),
        (2, 3, 5),
        (2, 3, 6),
    ])
    def test_different_counts_below_limit(self, count1, count2,
            maxCount):

        req1 = Requester()
        req2 = Requester()

        lock = BaseLock('test', maxCount=maxCount)
        access1 = mock.Mock(spec=LockAccess)
        access1.mode = 'counting'
        access1.count = count1
        access2 = mock.Mock(spec=LockAccess)
        access2.mode = 'counting'
        access2.count = count2

        self.assertTrue(lock.isAvailable(req1, access1))
        lock.claim(req1, access1)
        self.assertTrue(lock.isAvailable(req2, access2))
        lock.release(req1, access1)

    @parameterized.expand([
        (0, 2, 1),
        (0, 3, 1),
        (0, 3, 2),
        (1, 2, 2),
        (1, 3, 3),
        (1, 4, 3),
        (2, 3, 2),
        (2, 3, 3),
        (2, 3, 4),
        (2, 4, 4),
    ])
    def test_different_counts_over_limit(self, count1, count2,
            maxCount):

        req1 = Requester()
        req2 = Requester()

        lock = BaseLock('test', maxCount=maxCount)
        access1 = mock.Mock(spec=LockAccess)
        access1.mode = 'counting'
        access1.count = count1
        access2 = mock.Mock(spec=LockAccess)
        access2.mode = 'counting'
        access2.count = count2

        self.assertTrue(lock.isAvailable(req1, access1))
        lock.claim(req1, access1)
        self.assertFalse(lock.isAvailable(req2, access2))
        lock.release(req1, access1)


class RealLockTests(unittest.TestCase):

    def test_master_lock_init_from_lockid(self):
        lock = RealMasterLock('lock1')
        lock.updateFromLockId(MasterLock('lock1', maxCount=3), 0)

        self.assertEqual(lock.lockName, 'lock1')
        self.assertEqual(lock.maxCount, 3)
        self.assertEqual(lock.description, '<MasterLock(lock1, 3)>')

    def test_master_lock_update_from_lockid(self):
        lock = RealMasterLock('lock1')
        lock.updateFromLockId(MasterLock('lock1', maxCount=3), 0)
        lock.updateFromLockId(MasterLock('lock1', maxCount=4), 0)

        self.assertEqual(lock.lockName, 'lock1')
        self.assertEqual(lock.maxCount, 4)
        self.assertEqual(lock.description, '<MasterLock(lock1, 4)>')

        with self.assertRaises(AssertionError):
            lock.updateFromLockId(MasterLock('lock2', maxCount=4), 0)

    def test_worker_lock_init_from_lockid(self):
        lock = RealWorkerLock('lock1')
        lock.updateFromLockId(WorkerLock('lock1', maxCount=3), 0)

        self.assertEqual(lock.lockName, 'lock1')
        self.assertEqual(lock.maxCount, 3)
        self.assertEqual(lock.description, '<WorkerLock(lock1, 3, {})>')

        worker_lock = lock.getLockForWorker('worker1')
        self.assertEqual(worker_lock.lockName, 'lock1')
        self.assertEqual(worker_lock.maxCount, 3)
        self.assertTrue(worker_lock.description.startswith(
            '<WorkerLock(lock1, 3)[worker1]'))

    def test_worker_lock_init_from_lockid_count_for_worker(self):
        lock = RealWorkerLock('lock1')
        lock.updateFromLockId(WorkerLock('lock1', maxCount=3,
                                         maxCountForWorker={'worker2': 5}), 0)

        self.assertEqual(lock.lockName, 'lock1')
        self.assertEqual(lock.maxCount, 3)

        worker_lock = lock.getLockForWorker('worker1')
        self.assertEqual(worker_lock.maxCount, 3)
        worker_lock = lock.getLockForWorker('worker2')
        self.assertEqual(worker_lock.maxCount, 5)

    def test_worker_lock_update_from_lockid(self):
        lock = RealWorkerLock('lock1')
        lock.updateFromLockId(WorkerLock('lock1', maxCount=3), 0)

        worker_lock = lock.getLockForWorker('worker1')
        self.assertEqual(worker_lock.maxCount, 3)

        lock.updateFromLockId(WorkerLock('lock1', maxCount=5), 0)

        self.assertEqual(lock.lockName, 'lock1')
        self.assertEqual(lock.maxCount, 5)
        self.assertEqual(lock.description, '<WorkerLock(lock1, 5, {})>')

        self.assertEqual(worker_lock.lockName, 'lock1')
        self.assertEqual(worker_lock.maxCount, 5)
        self.assertTrue(worker_lock.description.startswith(
            '<WorkerLock(lock1, 5)[worker1]'))

        with self.assertRaises(AssertionError):
            lock.updateFromLockId(WorkerLock('lock2', maxCount=4), 0)

    @parameterized.expand([
        (True, True, True),
        (True, True, False),
        (True, False, True),
        (True, False, False),
        (False, True, True),
        (False, True, False),
        (False, False, True),
        (False, False, False),
    ])
    def test_worker_lock_update_from_lockid_count_for_worker(
            self, acquire_before, worker_count_before, worker_count_after):

        max_count_before = {}
        if worker_count_before:
            max_count_before = {'worker1': 5}
        max_count_after = {}
        if worker_count_after:
            max_count_after = {'worker1': 7}

        lock = RealWorkerLock('lock1')
        lock.updateFromLockId(WorkerLock('lock1', maxCount=3,
                                         maxCountForWorker=max_count_before), 0)

        if acquire_before:
            worker_lock = lock.getLockForWorker('worker1')
            self.assertEqual(worker_lock.maxCount,
                             5 if worker_count_before else 3)

        lockid = WorkerLock('lock1', maxCount=4,
                            maxCountForWorker=max_count_after)
        lock.updateFromLockId(lockid, 0)

        if not acquire_before:
            worker_lock = lock.getLockForWorker('worker1')

        self.assertEqual(worker_lock.maxCount,
                         7 if worker_count_after else 4)
