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

import mock

from buildworker.scripts import restart
from buildworker.scripts import start
from buildworker.scripts import stop
from buildworker.test.util import misc
from twisted.trial import unittest


class TestRestart(misc.IsBuildworkerDirMixin,
                  misc.LoggingMixin,
                  unittest.TestCase):

    """
    Test buildworker.scripts.restart.restart()
    """
    config = {"basedir": "dummy", "nodaemon": False, "quiet": False}

    def setUp(self):
        self.setUpLogging()

        # patch start.startWorker() to do nothing
        self.startWorker = mock.Mock()
        self.patch(start, "startWorker", self.startWorker)

    def test_bad_basedir(self):
        """
        test calling restart() with invalid basedir path
        """

        # patch isBuildworkerDir() to fail
        self.setupUpIsBuildworkerDir(False)

        # call startCommand() and check that correct exit code is returned
        self.assertEqual(restart.restart(self.config), 1,
                         "unexpected exit code")

        # check that isBuildworkerDir was called with correct argument
        self.isBuildworkerDir.assert_called_once_with(self.config["basedir"])

    def test_no_worker_running(self):
        """
        test calling restart() when no worker is running
        """
        # patch basedir check to always succeed
        self.setupUpIsBuildworkerDir(True)

        # patch stopWorker() to raise an exception
        mock_stopWorker = mock.Mock(side_effect=stop.WorkerNotRunning())
        self.patch(stop, "stopWorker", mock_stopWorker)

        # check that restart() calls startWorker() and outputs correct messages
        restart.restart(self.config)
        self.startWorker.assert_called_once_with(self.config["basedir"],
                                                self.config["quiet"],
                                                self.config["nodaemon"])

        self.assertLogged("no old buildworker process found to stop")
        self.assertLogged("now restarting buildworker process..")

    def test_restart(self):
        """
        test calling restart() when worker is running
        """
        # patch basedir check to always succeed
        self.setupUpIsBuildworkerDir(True)

        # patch stopWorker() to do nothing
        mock_stopWorker = mock.Mock()
        self.patch(stop, "stopWorker", mock_stopWorker)

        # check that restart() calls startWorker() and outputs correct messages
        restart.restart(self.config)
        self.startWorker.assert_called_once_with(self.config["basedir"],
                                                self.config["quiet"],
                                                self.config["nodaemon"])
        self.assertLogged("now restarting buildworker process..")
