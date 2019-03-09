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

    @parameterized.expand(['counting', 'exclusive'])
    def test_is_available_empty(self, mode):
        req = Requester()
        lock = BaseLock('test', maxCount=1)
        access = mock.Mock(spec=LockAccess)
        access.mode = mode

        self.assertTrue(lock.isAvailable(req, access))

    @parameterized.expand(['counting', 'exclusive'])
    def test_is_available_without_waiter(self, mode):
        req = Requester()
        req_waiter = Requester()

        lock = BaseLock('test', maxCount=1)
        access = mock.Mock(spec=LockAccess)
        access.mode = mode

        lock.claim(req, access)
        lock.release(req, access)
        self.assertTrue(lock.isAvailable(req, access))
        self.assertTrue(lock.isAvailable(req_waiter, access))

    @parameterized.expand(['counting', 'exclusive'])
    def test_is_available_with_waiter(self, mode):
        req = Requester()
        req_waiter = Requester()

        lock = BaseLock('test', maxCount=1)
        access = mock.Mock(spec=LockAccess)
        access.mode = mode

        lock.claim(req, access)
        lock.waitUntilMaybeAvailable(req_waiter, access)
        lock.release(req, access)
        self.assertFalse(lock.isAvailable(req, access))
        self.assertTrue(lock.isAvailable(req_waiter, access))

        lock.claim(req_waiter, access)
        lock.release(req_waiter, access)
        self.assertTrue(lock.isAvailable(req, access))
        self.assertTrue(lock.isAvailable(req_waiter, access))

    @parameterized.expand(['counting', 'exclusive'])
    def test_is_available_with_multiple_waiters(self, mode):
        req = Requester()
        req_waiter1 = Requester()
        req_waiter2 = Requester()

        lock = BaseLock('test', maxCount=1)
        access = mock.Mock(spec=LockAccess)
        access.mode = mode

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

    @parameterized.expand(['counting', 'exclusive'])
    def test_stop_waiting_raises_after_release(self, mode):
        req = Requester()
        req_waiter = Requester()

        lock = BaseLock('test', maxCount=1)
        access = mock.Mock(spec=LockAccess)
        access.mode = mode

        lock.claim(req, access)
        d = lock.waitUntilMaybeAvailable(req_waiter, access)
        lock.release(req, access)
        self.assertFalse(lock.isAvailable(req, access))
        self.assertTrue(lock.isAvailable(req_waiter, access))

        with self.assertRaises(AssertionError):
            lock.stopWaitingUntilAvailable(req_waiter, access, d)

        lock.claim(req_waiter, access)
        lock.release(req_waiter, access)

    @parameterized.expand(['counting', 'exclusive'])
    def test_stop_waiting_removes_non_called_waiter(self, mode):
        req = Requester()
        req_waiter1 = Requester()
        req_waiter2 = Requester()

        lock = BaseLock('test', maxCount=1)
        access = mock.Mock(spec=LockAccess)
        access.mode = mode

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

    @parameterized.expand(['counting', 'exclusive'])
    def test_can_release_non_waited_lock(self, mode):
        req = Requester()
        req_not_waited = Requester()

        lock = BaseLock('test', maxCount=1)
        access = mock.Mock(spec=LockAccess)
        access.mode = mode

        lock.release(req_not_waited, access)

        lock.claim(req, access)
        lock.release(req, access)
        yield flushEventualQueue()

        lock.release(req_not_waited, access)

    @parameterized.expand([
        ('counting', 'counting'),
        ('counting', 'exclusive'),
        ('exclusive', 'counting'),
        ('exclusive', 'exclusive'),
    ])
    @defer.inlineCallbacks
    def test_release_calls_waiters_in_fifo_order(self, mode1, mode2):
        req = Requester()

        req_waiters = [Requester() for _ in range(5)]

        lock = BaseLock('test', maxCount=1)
        access1 = mock.Mock(spec=LockAccess)
        access1.mode = mode1
        access2 = mock.Mock(spec=LockAccess)
        access2.mode = mode2

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

    @defer.inlineCallbacks
    def test_release_calls_multiple_waiters_on_release(self):
        req = Requester()

        req_waiters = [Requester() for _ in range(5)]

        lock = BaseLock('test', maxCount=5)
        access_counting = mock.Mock(spec=LockAccess)
        access_counting.mode = 'counting'
        access_excl = mock.Mock(spec=LockAccess)
        access_excl.mode = 'exclusive'

        lock.claim(req, access_excl)
        deferreds = [lock.waitUntilMaybeAvailable(req_waiter, access_counting)
                     for req_waiter in req_waiters]
        self.assertEqual([d.called for d in deferreds], [False] * 5)

        lock.release(req, access_excl)
        yield flushEventualQueue()

        self.assertEqual([d.called for d in deferreds], [True] * 5)

    @defer.inlineCallbacks
    def test_release_calls_multiple_waiters_on_setMaxCount(self):
        req = Requester()

        req_waiters = [Requester() for _ in range(5)]

        lock = BaseLock('test', maxCount=1)
        access_counting = mock.Mock(spec=LockAccess)
        access_counting.mode = 'counting'

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


class RealLockTests(unittest.TestCase):

    def test_master_lock_init_from_lockid(self):
        lockid = MasterLock('lock1', maxCount=3)
        lock = RealMasterLock(lockid)

        self.assertEqual(lock.name, 'lock1')
        self.assertEqual(lock.maxCount, 3)
        self.assertEqual(lock.description, '<MasterLock(lock1, 3)>')

    def test_master_lock_update_from_lockid(self):
        lockid = MasterLock('lock1', maxCount=3)
        lock = RealMasterLock(lockid)

        lockid = MasterLock('lock1', maxCount=4)
        lock.updateFromLockId(lockid)

        self.assertEqual(lock.name, 'lock1')
        self.assertEqual(lock.maxCount, 4)
        self.assertEqual(lock.description, '<MasterLock(lock1, 4)>')

        with self.assertRaises(AssertionError):
            lockid = MasterLock('lock2', maxCount=4)
            lock.updateFromLockId(lockid)

    def test_worker_lock_init_from_lockid(self):
        lockid = WorkerLock('lock1', maxCount=3)
        lock = RealWorkerLock(lockid)

        self.assertEqual(lock.name, 'lock1')
        self.assertEqual(lock.maxCount, 3)
        self.assertEqual(lock.description, '<WorkerLock(lock1, 3, {})>')

        worker_lock = lock.getLockForWorker('worker1')
        self.assertEqual(worker_lock.name, 'lock1')
        self.assertEqual(worker_lock.maxCount, 3)
        self.assertTrue(worker_lock.description.startswith(
            '<WorkerLock(lock1, 3)[worker1]'))

    def test_worker_lock_init_from_lockid_count_for_worker(self):
        lockid = WorkerLock('lock1', maxCount=3,
                            maxCountForWorker={'worker2': 5})
        lock = RealWorkerLock(lockid)

        self.assertEqual(lock.name, 'lock1')
        self.assertEqual(lock.maxCount, 3)

        worker_lock = lock.getLockForWorker('worker1')
        self.assertEqual(worker_lock.maxCount, 3)
        worker_lock = lock.getLockForWorker('worker2')
        self.assertEqual(worker_lock.maxCount, 5)

    def test_worker_lock_update_from_lockid(self):
        lockid = WorkerLock('lock1', maxCount=3)
        lock = RealWorkerLock(lockid)

        worker_lock = lock.getLockForWorker('worker1')
        self.assertEqual(worker_lock.maxCount, 3)

        lockid = WorkerLock('lock1', maxCount=5)
        lock.updateFromLockId(lockid)

        self.assertEqual(lock.name, 'lock1')
        self.assertEqual(lock.maxCount, 5)
        self.assertEqual(lock.description, '<WorkerLock(lock1, 5, {})>')

        self.assertEqual(worker_lock.name, 'lock1')
        self.assertEqual(worker_lock.maxCount, 5)
        self.assertTrue(worker_lock.description.startswith(
            '<WorkerLock(lock1, 5)[worker1]'))

        with self.assertRaises(AssertionError):
            lockid = WorkerLock('lock2', maxCount=4)
            lock.updateFromLockId(lockid)

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

        lockid = WorkerLock('lock1', maxCount=3,
                            maxCountForWorker=max_count_before)
        lock = RealWorkerLock(lockid)

        if acquire_before:
            worker_lock = lock.getLockForWorker('worker1')
            self.assertEqual(worker_lock.maxCount,
                             5 if worker_count_before else 3)

        lockid = WorkerLock('lock1', maxCount=4,
                            maxCountForWorker=max_count_after)
        lock.updateFromLockId(lockid)

        if not acquire_before:
            worker_lock = lock.getLockForWorker('worker1')

        self.assertEqual(worker_lock.maxCount,
                         7 if worker_count_after else 4)
