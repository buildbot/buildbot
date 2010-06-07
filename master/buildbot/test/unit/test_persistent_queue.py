# -*- test-case-name: buildbot.test.test_persistent_queue -*-

import os
import shutil
from twisted.trial import unittest

from buildbot.status.persistent_queue import DequeMemoryQueue, DiskQueue, \
    IQueue, ListMemoryQueue, MemoryQueue, PersistentQueue, WriteFile

class test_Queues(unittest.TestCase):
    def setUp(self):
        if os.path.isdir('fake_dir'):
            shutil.rmtree('fake_dir')

    def tearDown(self):
        if os.path.isdir('fake_dir'):
            self.assertEqual([], os.listdir('fake_dir'))

    def testQueued(self):
        # Verify behavior when starting up with queued items on disk.
        os.mkdir('fake_dir')
        WriteFile(os.path.join('fake_dir', '3'), 'foo3')
        WriteFile(os.path.join('fake_dir', '5'), 'foo5')
        WriteFile(os.path.join('fake_dir', '8'), 'foo8')
        queue = PersistentQueue(MemoryQueue(3),
            DiskQueue('fake_dir', 5, pickleFn=str, unpickleFn=str))
        self.assertEqual(['foo3', 'foo5', 'foo8'], queue.items())
        self.assertEqual(3, queue.nbItems())
        self.assertEqual(['foo3', 'foo5', 'foo8'], queue.popChunk())

    def _test_helper(self, q):
        self.assertTrue(IQueue.providedBy(q))
        self.assertEqual(8, q.maxItems())
        self.assertEqual(0, q.nbItems())
        self.assertEqual([], q.items())

        for i in range(4):
            self.assertEqual(None, q.pushItem(i), str(i))
            self.assertEqual(i + 1, q.nbItems(), str(i))
        self.assertEqual([0, 1, 2, 3], q.items())
        self.assertEqual(4, q.nbItems())
        if isinstance(q, PersistentQueue):
            self.assertEqual([0, 1, 2], q.primaryQueue.items())
            self.assertEqual([3], q.secondaryQueue.items())

        self.assertEqual(None, q.save())
        self.assertEqual([0, 1, 2, 3], q.items())
        self.assertEqual(4, q.nbItems())
        if isinstance(q, PersistentQueue):
            self.assertEqual([], q.primaryQueue.items())
            self.assertEqual([0, 1, 2, 3], q.secondaryQueue.items())

        for i in range(4):
            self.assertEqual(None, q.pushItem(i + 4), str(i + 4))
            self.assertEqual(i + 5, q.nbItems(), str(i + 4))
        self.assertEqual([0, 1, 2, 3, 4, 5, 6, 7], q.items())
        self.assertEqual(8, q.nbItems())
        if isinstance(q, PersistentQueue):
            self.assertEqual([0, 1, 2], q.primaryQueue.items())
            self.assertEqual([3, 4, 5, 6, 7], q.secondaryQueue.items())

        self.assertEqual(0, q.pushItem(8))
        self.assertEqual(8, q.nbItems())
        self.assertEqual([1, 2, 3, 4, 5, 6, 7, 8], q.items())
        if isinstance(q, PersistentQueue):
            self.assertEqual([1, 2, 3], q.primaryQueue.items())
            self.assertEqual([4, 5, 6, 7, 8], q.secondaryQueue.items())

        self.assertEqual([1, 2], q.popChunk(2))
        self.assertEqual([3, 4, 5, 6, 7, 8], q.items())
        self.assertEqual(6, q.nbItems())
        if isinstance(q, PersistentQueue):
            self.assertEqual([3], q.primaryQueue.items())
            self.assertEqual([4, 5, 6, 7, 8], q.secondaryQueue.items())

        self.assertEqual([3], q.popChunk(1))
        self.assertEqual([4, 5, 6, 7, 8], q.items())
        self.assertEqual(5, q.nbItems())
        if isinstance(q, PersistentQueue):
            self.assertEqual([], q.primaryQueue.items())
            self.assertEqual([4, 5, 6, 7, 8], q.secondaryQueue.items())

        self.assertEqual(None, q.save())
        self.assertEqual(5, q.nbItems())
        self.assertEqual([4, 5, 6, 7, 8], q.items())
        if isinstance(q, PersistentQueue):
            self.assertEqual([], q.primaryQueue.items())
            self.assertEqual([4, 5, 6, 7, 8], q.secondaryQueue.items())

        self.assertEqual(None, q.insertBackChunk([2, 3]))
        self.assertEqual([2, 3, 4, 5, 6, 7, 8], q.items())
        self.assertEqual(7, q.nbItems())
        if isinstance(q, PersistentQueue):
            self.assertEqual([2, 3], q.primaryQueue.items())
            self.assertEqual([4, 5, 6, 7, 8], q.secondaryQueue.items())

        self.assertEqual([0], q.insertBackChunk([0, 1]))
        self.assertEqual([1, 2, 3, 4, 5, 6, 7, 8], q.items())
        self.assertEqual(8, q.nbItems())
        if isinstance(q, PersistentQueue):
            self.assertEqual([1, 2, 3], q.primaryQueue.items())
            self.assertEqual([4, 5, 6, 7, 8], q.secondaryQueue.items())

        self.assertEqual([10, 11], q.insertBackChunk([10, 11]))
        self.assertEqual([1, 2, 3, 4, 5, 6, 7, 8], q.items())
        self.assertEqual(8, q.nbItems())
        if isinstance(q, PersistentQueue):
            self.assertEqual([1, 2, 3], q.primaryQueue.items())
            self.assertEqual([4, 5, 6, 7, 8], q.secondaryQueue.items())

        self.assertEqual([1, 2, 3, 4, 5, 6, 7, 8], q.popChunk(8))
        self.assertEqual([], q.items())
        self.assertEqual(0, q.nbItems())
        if isinstance(q, PersistentQueue):
            self.assertEqual([], q.primaryQueue.items())
            self.assertEqual([], q.secondaryQueue.items())

        self.assertEqual([], q.popChunk())
        self.assertEqual(0, q.nbItems())
        if isinstance(q, PersistentQueue):
            self.assertEqual([], q.primaryQueue.items())
            self.assertEqual([], q.secondaryQueue.items())

    def testListMemoryQueue(self):
        self._test_helper(ListMemoryQueue(maxItems=8))

    def testDequeMemoryQueue(self):
        # Will fail on python 2.3.
        self._test_helper(DequeMemoryQueue(maxItems=8))

    def testDiskQueue(self):
        self._test_helper(DiskQueue('fake_dir', maxItems=8))

    def testPersistentQueue(self):
        self._test_helper(PersistentQueue(MemoryQueue(3),
                                          DiskQueue('fake_dir', 5)))

# vim: set ts=4 sts=4 sw=4 et:
