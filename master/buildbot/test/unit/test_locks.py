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

from buildbot.locks import WorkerLock
from buildbot.test.util.warnings import assertNotProducesWarnings
from buildbot.test.util.warnings import assertProducesWarning
from buildbot.worker_transition import DeprecatedWorkerAPIWarning
from buildbot.worker_transition import DeprecatedWorkerNameWarning


class TestWorkerTransition(unittest.TestCase):

    def test_SlaveLock_deprecated(self):
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="SlaveLock was deprecated"):
            from buildbot.locks import SlaveLock

        self.assertIdentical(SlaveLock, WorkerLock)

    def test_maxCountForWorker_old_api(self):
        lock = WorkerLock("lock")

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            new = lock.maxCountForWorker

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'maxCountForSlave' attribute is deprecated"):
            old = lock.maxCountForSlave

        self.assertIdentical(new, old)

    def test_init_maxCountForWorker_old_api_no_warns(self):
        counts = {'w1': 10, 'w2': 20}
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            lock = WorkerLock("name", maxCount=1, maxCountForWorker=counts)

        self.assertEqual(lock.maxCountForWorker, counts)

    def test_init_maxCountForWorker_old_api_warns(self):
        counts = {'w1': 10, 'w2': 20}
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'maxCountForSlave' keyword argument is deprecated"):
            lock = WorkerLock("name", maxCount=1, maxCountForSlave=counts)

        self.assertEqual(lock.maxCountForWorker, counts)
