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
from buildbot.process.workerforbuilder import AbstractWorkerForBuilder
from buildbot.test.util.warnings import assertNotProducesWarnings
from buildbot.test.util.warnings import assertProducesWarning
from buildbot.test.util.warnings import ignoreWarning
from buildbot.worker.base import AbstractWorker
from buildbot.worker_transition import DeprecatedWorkerAPIWarning
from buildbot.worker_transition import DeprecatedWorkerModuleWarning
from buildbot.worker_transition import DeprecatedWorkerNameWarning
from twisted.trial.unittest import TestCase


class TestAbstractWorkerForBuilder(TestCase):
    """
    Tests for ``AbstractWorkerForBuilder``.
    """

    def test_buildStarted_called(self):
        """
        If the worker associated to worker builder has a ``buildStarted`` method,
        calling ``buildStarted`` on the worker builder calls the method on the
        worker with the slavebuilder as an argument.
        """
        class ConcreteWorker(AbstractWorker):
            _buildStartedCalls = []

            def buildStarted(self, slavebuilder):
                self._buildStartedCalls.append(slavebuilder)

        slave = ConcreteWorker("worker", "pass")
        slavebuilder = AbstractWorkerForBuilder()
        # FIXME: This should call attached, instead of setting the attribute
        # directly
        slavebuilder.worker = slave
        slavebuilder.buildStarted()

        self.assertEqual(ConcreteWorker._buildStartedCalls, [slavebuilder])

    def test_buildStarted_missing(self):
        """
        If the worker associated to worker builder doesn not have a
        ``buildStarted`` method, calling ``buildStarted`` on the worker builder
        doesn't raise an exception.
        """
        class ConcreteWorker(AbstractWorker):
            pass

        slave = ConcreteWorker("worker", "pass")
        slavebuilder = AbstractWorkerForBuilder()
        # FIXME: This should call attached, instead of setting the attribute
        # directly
        slavebuilder.worker = slave

        # The following shouldn't raise an exception.
        slavebuilder.buildStarted()

    def test_worker_old_api(self):
        w = AbstractWorkerForBuilder()

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            new_worker = w.worker

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'slave' attribute is deprecated"):
            old_worker = w.slave

        self.assertTrue(new_worker is old_worker)


class TestWorkerTransition(TestCase):

    def test_abstract_worker_for_builder(self):
        with ignoreWarning(DeprecatedWorkerModuleWarning):
            from buildbot.process.slavebuilder import AbstractSlaveBuilder

        class WB(AbstractSlaveBuilder):

            def __init__(self):
                pass

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'AbstractSlaveBuilder' class is deprecated"):
            w = WB()
            self.assertIsInstance(w, AbstractWorkerForBuilder)

    def test_worker_for_builder(self):
        from buildbot.process.workerforbuilder import WorkerForBuilder
        with ignoreWarning(DeprecatedWorkerModuleWarning):
            from buildbot.process.slavebuilder import SlaveBuilder

        class WB(SlaveBuilder):

            def __init__(self):
                pass

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'SlaveBuilder' class is deprecated"):
            w = WB()
            self.assertIsInstance(w, WorkerForBuilder)

    def test_latent_worker_for_builder(self):
        from buildbot.process.workerforbuilder import LatentWorkerForBuilder
        with ignoreWarning(DeprecatedWorkerModuleWarning):
            from buildbot.process.slavebuilder import LatentSlaveBuilder

        class WB(LatentSlaveBuilder):

            def __init__(self):
                pass

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'LatentSlaveBuilder' class is deprecated"):
            w = WB()
            self.assertIsInstance(w, LatentWorkerForBuilder)
