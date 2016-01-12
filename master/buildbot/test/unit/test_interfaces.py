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

from buildbot.test.util.warnings import assertNotProducesWarnings
from buildbot.test.util.warnings import assertProducesWarning
from buildbot.worker_transition import DeprecatedWorkerAPIWarning
from buildbot.worker_transition import DeprecatedWorkerNameWarning


class TestNoSlaveError(unittest.TestCase):

    def test_use(self):
        from buildbot.interfaces import NoSlaveError

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'NoSlaveError' class is deprecated"):
            err = NoSlaveError()
            assert isinstance(err, NoSlaveError)


class TestWorkerTooOldError(unittest.TestCase):

    def test_use(self):
        from buildbot.interfaces import WorkerTooOldError
        from buildbot.interfaces import BuildSlaveTooOldError

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            err = WorkerTooOldError()
            self.assertIsInstance(err, Exception)

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'BuildSlaveTooOldError' class is deprecated"):
            err = BuildSlaveTooOldError()
            assert isinstance(err, Exception)


class TestLatentWorkerFailedToSubstantiate(unittest.TestCase):

    def test_use(self):
        from buildbot.interfaces import LatentWorkerFailedToSubstantiate
        from buildbot.interfaces import LatentBuildSlaveFailedToSubstantiate

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            err = LatentWorkerFailedToSubstantiate()
            self.assertIsInstance(err, Exception)

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'LatentBuildSlaveFailedToSubstantiate' class "
                                "is deprecated"):
            err = LatentBuildSlaveFailedToSubstantiate()
            assert isinstance(err, Exception)


class TestIWorker(unittest.TestCase):

    def test_use(self):
        from buildbot.interfaces import IWorker
        from buildbot.interfaces import IBuildSlave

        self.assertIs(IBuildSlave, IWorker)


class ILatentWorker(unittest.TestCase):

    def test_use(self):
        from buildbot.interfaces import ILatentWorker
        from buildbot.interfaces import ILatentBuildSlave

        self.assertIs(ILatentBuildSlave, ILatentWorker)
