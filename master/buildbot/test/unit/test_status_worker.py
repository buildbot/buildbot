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
# Portions Copyright Buildbot Team Members
# Portions Copyright 2013 Cray Inc.

from buildbot.test.util.warnings import assertProducesWarning
from buildbot.test.util.warnings import ignoreWarning
from buildbot.worker_transition import DeprecatedWorkerModuleWarning
from buildbot.worker_transition import DeprecatedWorkerNameWarning
from twisted.trial import unittest


class TestWorkerTransition(unittest.TestCase):

    def test_worker_status(self):
        from buildbot.status.worker import WorkerStatus
        with ignoreWarning(DeprecatedWorkerModuleWarning):
            from buildbot.status.slave import SlaveStatus

        class WS(SlaveStatus):

            def __init__(self):
                pass

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'SlaveStatus' class is deprecated"):
            w = WS()
            self.assertIsInstance(w, WorkerStatus)
