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

from buildbot.locks import WorkerLock
from buildbot.test.util.warnings import assertNotProducesWarnings
from buildbot.test.util.warnings import assertProducesWarning
from buildbot.worker_transition import DeprecatedWorkerAPIWarning
from buildbot.worker_transition import DeprecatedWorkerNameWarning
from twisted.trial import unittest


class TestWorkerTransition(unittest.TestCase):

    def test_worker_status(self):
        from buildbot.locks import SlaveLock

        class WL(SlaveLock):

            def __init__(self):
                pass

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'SlaveLock' class is deprecated"):
            l = WL()
            self.assertIsInstance(l, WorkerLock)

    def test_maxCountForWorker_old_api(self):
        l = WorkerLock("lock")

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            new = l.maxCountForWorker

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'maxCountForSlave' attribute is deprecated"):
            old = l.maxCountForSlave

        self.assertIdentical(new, old)
