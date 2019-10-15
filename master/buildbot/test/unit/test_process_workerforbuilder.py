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

from twisted.trial.unittest import TestCase

from buildbot.process.workerforbuilder import AbstractWorkerForBuilder
from buildbot.worker.base import AbstractWorker


class TestAbstractWorkerForBuilder(TestCase):

    """
    Tests for ``AbstractWorkerForBuilder``.
    """

    def test_buildStarted_called(self):
        """
        If the worker associated to worker builder has a ``buildStarted`` method,
        calling ``buildStarted`` on the worker builder calls the method on the
        worker with the workerforbuilder as an argument.
        """
        class ConcreteWorker(AbstractWorker):
            _buildStartedCalls = []

            def buildStarted(self, workerforbuilder):
                self._buildStartedCalls.append(workerforbuilder)

        worker = ConcreteWorker("worker", "pass")
        workerforbuilder = AbstractWorkerForBuilder()
        # FIXME: This should call attached, instead of setting the attribute
        # directly
        workerforbuilder.worker = worker
        workerforbuilder.buildStarted()

        self.assertEqual(ConcreteWorker._buildStartedCalls, [workerforbuilder])

    def test_buildStarted_missing(self):
        """
        If the worker associated to worker builder doesn't not have a
        ``buildStarted`` method, calling ``buildStarted`` on the worker builder
        doesn't raise an exception.
        """
        class ConcreteWorker(AbstractWorker):
            pass

        worker = ConcreteWorker("worker", "pass")
        workerforbuilder = AbstractWorkerForBuilder()
        # FIXME: This should call attached, instead of setting the attribute
        # directly
        workerforbuilder.worker = worker

        # The following shouldn't raise an exception.
        workerforbuilder.buildStarted()
