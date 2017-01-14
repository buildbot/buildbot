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

from buildbot import interfaces
from buildbot.test.util.warnings import assertProducesWarning
from buildbot.worker_transition import DeprecatedWorkerNameWarning


class TestWorkerTransition(unittest.TestCase):

    def test_NoSlaveError_deprecated(self):
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="NoSlaveError was deprecated"):
            interfaces.NoSlaveError

    def test_IBuildSlave_deprecated(self):
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="IBuildSlave was deprecated"):
            deprecated = interfaces.IBuildSlave

        self.assertIdentical(deprecated, interfaces.IWorker)

    def test_ILatentBuildSlave_deprecated(self):
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="ILatentBuildSlave was deprecated"):
            deprecated = interfaces.ILatentBuildSlave

        self.assertIdentical(deprecated, interfaces.ILatentWorker)

    def test_ISlaveStatus_deprecated(self):
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="ISlaveStatus was deprecated"):
            deprecated = interfaces.ISlaveStatus

        self.assertIdentical(deprecated, interfaces.IWorkerStatus)

    def test_BuildSlaveTooOldError_deprecated(self):
        from buildbot.interfaces import WorkerTooOldError

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="BuildSlaveTooOldError was deprecated"):
            from buildbot.interfaces import BuildSlaveTooOldError

        self.assertIdentical(BuildSlaveTooOldError, WorkerTooOldError)

    def test_LatentBuildSlaveFailedToSubstantiate_deprecated(self):
        from buildbot.interfaces import LatentWorkerFailedToSubstantiate

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="LatentBuildSlaveFailedToSubstantiate "
                                "was deprecated"):
            from buildbot.interfaces import LatentBuildSlaveFailedToSubstantiate

        self.assertIdentical(LatentBuildSlaveFailedToSubstantiate,
                             LatentWorkerFailedToSubstantiate)
