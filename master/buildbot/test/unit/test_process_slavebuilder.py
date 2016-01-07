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


from buildbot.worker.base import AbstractWorker
from twisted.trial.unittest import TestCase

from buildbot.process.slavebuilder import AbstractSlaveBuilder


class TestAbstractSlaveBuilder(TestCase):
    """
    Tests for ``AbstractSlaveBuilder``.
    """

    def test_buildStarted_called(self):
        """
        If the slave associated to slave builder has a ``buildStarted`` method,
        calling ``buildStarted`` on the slave builder calls the method on the
        slave with the slavebuilder as an argument.
        """
        class ConcreteWorker(AbstractWorker):
            _buildStartedCalls = []

            def buildStarted(self, slavebuilder):
                self._buildStartedCalls.append(slavebuilder)

        slave = ConcreteWorker("slave", "pass")
        slavebuilder = AbstractSlaveBuilder()
        # FIXME: This should call attached, instead of setting the attribute
        # directly
        slavebuilder.slave = slave
        slavebuilder.buildStarted()

        self.assertEqual(ConcreteWorker._buildStartedCalls, [slavebuilder])

    def test_buildStarted_missing(self):
        """
        If the slave associated to slave builder doesn not have a
        ``buildStarted`` method, calling ``buildStarted`` on the slave builder
        doesn't raise an exception.
        """
        class ConcreteWorker(AbstractWorker):
            pass

        slave = ConcreteWorker("slave", "pass")
        slavebuilder = AbstractSlaveBuilder()
        # FIXME: This should call attached, instead of setting the attribute
        # directly
        slavebuilder.slave = slave

        # The following shouldn't raise an exception.
        slavebuilder.buildStarted()
