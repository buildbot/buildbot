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
from future.utils import iteritems

import os

from buildbot.test.util import dirs
from twisted.trial import unittest

from buildbot.status.persistent_queue import DiskQueue
from buildbot.status.persistent_queue import IQueue
from buildbot.status.persistent_queue import MemoryQueue
from buildbot.status.persistent_queue import PersistentQueue
from buildbot.status.persistent_queue import WriteFile


class test_Queues(dirs.DirsMixin, unittest.TestCase):

    def setUp(self):
        self.setUpDirs('fake_dir')

    def tearDown(self):
        self.assertEqual([], os.listdir('fake_dir'))
        self.tearDownDirs()

    def testQueued(self):
        # Verify behavior when starting up with queued items on disk.
        WriteFile(os.path.join('fake_dir', '3'), 'foo3')
        WriteFile(os.path.join('fake_dir', '5'), 'foo5')
        WriteFile(os.path.join('fake_dir', '8'), 'foo8')
        queue = PersistentQueue(MemoryQueue(3),
                                DiskQueue('fake_dir', 5, pickleFn=str, unpickleFn=str))
        self.assertEqual(['foo3', 'foo5', 'foo8'], list(iteritems(queue)))
        self.assertEqual(3, queue.nbItems())
        self.assertEqual(['foo3', 'foo5', 'foo8'], queue.popChunk())

    def _test_helper(self, q):
        self.assertTrue(IQueue.providedBy(q))
        self.assertEqual(8, q.maxItems())
        self.assertEqual(0, q.nbItems())
        self.assertEqual([], list(iteritems(q)))

        for i in range(4):
            self.assertEqual(None, q.pushItem(i), str(i))
            self.assertEqual(i + 1, q.nbItems(), str(i))
        self.assertEqual([0, 1, 2, 3], q.items())
        self.assertEqual(4, q.nbItems())
        if isinstance(q, PersistentQueue):
            self.assertEqual([0, 1, 2], list(iteritems(q.primaryQueue)))
            self.assertEqual([3], list(iteritems(q.secondaryQueue)))

        self.assertEqual(None, q.save())
        self.assertEqual([0, 1, 2, 3], list(iteritems(q)))
        self.assertEqual(4, q.nbItems())
        if isinstance(q, PersistentQueue):
            self.assertEqual([], list(iteritems(q.primaryQueue)))
            self.assertEqual([0, 1, 2, 3], list(iteritems(q.secondaryQueue)))

        for i in range(4):
            self.assertEqual(None, q.pushItem(i + 4), str(i + 4))
            self.assertEqual(i + 5, q.nbItems(), str(i + 4))
        self.assertEqual([0, 1, 2, 3, 4, 5, 6, 7], list(iteritems(q)))
        self.assertEqual(8, q.nbItems())
        if isinstance(q, PersistentQueue):
            self.assertEqual([0, 1, 2], list(iteritems(q.primaryQueue)))
            self.assertEqual([3, 4, 5, 6, 7], list(iteritems(q.secondaryQueue)))

        self.assertEqual(0, q.pushItem(8))
        self.assertEqual(8, q.nbItems())
        self.assertEqual([1, 2, 3, 4, 5, 6, 7, 8], list(iteritems(q)))
        if isinstance(q, PersistentQueue):
            self.assertEqual([1, 2, 3], list(iteritems(q.primaryQueue)))
            self.assertEqual([4, 5, 6, 7, 8], list(iteritems(q.secondaryQueue)))

        self.assertEqual([1, 2], q.popChunk(2))
        self.assertEqual([3, 4, 5, 6, 7, 8], list(iteritems(q)))
        self.assertEqual(6, q.nbItems())
        if isinstance(q, PersistentQueue):
            self.assertEqual([3], list(iteritems(q.primaryQueue)))
            self.assertEqual([4, 5, 6, 7, 8], list(iteritems(q.secondaryQueue)))

        self.assertEqual([3], q.popChunk(1))
        self.assertEqual([4, 5, 6, 7, 8], list(iteritems(q)))
        self.assertEqual(5, q.nbItems())
        if isinstance(q, PersistentQueue):
            self.assertEqual([], list(iteritems(q.primaryQueue)))
            self.assertEqual([4, 5, 6, 7, 8], list(iteritems(q.secondaryQueue)))

        self.assertEqual(None, q.save())
        self.assertEqual(5, q.nbItems())
        self.assertEqual([4, 5, 6, 7, 8], list(iteritems(q)))
        if isinstance(q, PersistentQueue):
            self.assertEqual([], list(iteritems(q.primaryQueue)))
            self.assertEqual([4, 5, 6, 7, 8], list(iteritems(q.secondaryQueue)))

        self.assertEqual(None, q.insertBackChunk([2, 3]))
        self.assertEqual([2, 3, 4, 5, 6, 7, 8], list(iteritems(q)))
        self.assertEqual(7, q.nbItems())
        if isinstance(q, PersistentQueue):
            self.assertEqual([2, 3], list(iteritems(q.primaryQueue)))
            self.assertEqual([4, 5, 6, 7, 8], list(iteritems(q.secondaryQueue)))

        self.assertEqual([0], q.insertBackChunk([0, 1]))
        self.assertEqual([1, 2, 3, 4, 5, 6, 7, 8], list(iteritems(q)))
        self.assertEqual(8, q.nbItems())
        if isinstance(q, PersistentQueue):
            self.assertEqual([1, 2, 3], list(iteritems(q.primaryQueue)))
            self.assertEqual([4, 5, 6, 7, 8], list(iteritems(q.secondaryQueue)))

        self.assertEqual([10, 11], q.insertBackChunk([10, 11]))
        self.assertEqual([1, 2, 3, 4, 5, 6, 7, 8], list(iteritems(q)))
        self.assertEqual(8, q.nbItems())
        if isinstance(q, PersistentQueue):
            self.assertEqual([1, 2, 3], list(iteritems(q.primaryQueue)))
            self.assertEqual([4, 5, 6, 7, 8], list(iteritems(q.secondaryQueue)))

        self.assertEqual([1, 2, 3, 4, 5, 6, 7, 8], q.popChunk(8))
        self.assertEqual([], list(iteritems(q)))
        self.assertEqual(0, q.nbItems())
        if isinstance(q, PersistentQueue):
            self.assertEqual([], list(iteritems(q.primaryQueue)))
            self.assertEqual([], list(iteritems(q.secondaryQueue)))

        self.assertEqual([], q.popChunk())
        self.assertEqual(0, q.nbItems())
        if isinstance(q, PersistentQueue):
            self.assertEqual([], list(iteritems(q.primaryQueue)))
            self.assertEqual([], list(iteritems(q.secondaryQueue)))

    def testMemoryQueue(self):
        self._test_helper(MemoryQueue(maxItems=8))

    def testDiskQueue(self):
        self._test_helper(DiskQueue('fake_dir', maxItems=8))

    def testPersistentQueue(self):
        self._test_helper(PersistentQueue(MemoryQueue(3),
                                          DiskQueue('fake_dir', 5)))

# vim: set ts=4 sts=4 sw=4 et:
