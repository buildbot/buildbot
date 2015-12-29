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

import errno
import mock
import os
import signal
import time

from buildbot_worker.scripts import stop
from buildbot_worker.test.util import compat
from buildbot_worker.test.util import misc
from twisted.trial import unittest


class TestStopWorker(misc.FileIOMixin,
                     misc.LoggingMixin,
                     unittest.TestCase):

    """
    Test buildbot_worker.scripts.stop.stopWorker()
    """
    PID = 9876

    def setUp(self):
        self.setUpLogging()

        # patch os.chdir() to do nothing
        self.patch(os, "chdir", mock.Mock())

    def test_no_pid_file(self):
        """
        test calling stopWorker() when no pid file is present
        """

        # patch open() to raise 'file not found' exception
        self.setUpOpenError(2)

        # check that stop() raises WorkerNotRunning exception
        self.assertRaises(stop.WorkerNotRunning,
                          stop.stopWorker, None, False)

    @compat.skipUnlessPlatformIs("posix")
    def test_successful_stop(self):
        """
        test stopWorker() on a successful slave stop
        """

        def emulated_kill(pid, sig):
            if sig == 0:
                # when probed if a signal can be send to the process
                # emulate that it is dead with 'No such process' error
                raise OSError(errno.ESRCH, "dummy")

        # patch open() to return a pid file
        self.setUpOpen(str(self.PID))

        # patch os.kill to emulate successful kill
        mocked_kill = mock.Mock(side_effect=emulated_kill)
        self.patch(os, "kill", mocked_kill)

        # don't waste time
        self.patch(time, "sleep", mock.Mock())

        # check that stopWorker() sends expected signal to right PID
        # and print correct message to the log
        stop.stopWorker(None, False)
        mocked_kill.assert_has_calls([mock.call(self.PID, signal.SIGTERM),
                                      mock.call(self.PID, 0)])

        self.assertLogged("buildbot_worker process %s is dead" % self.PID)


class TestStop(misc.IsWorkerDirMixin,
               misc.LoggingMixin,
               unittest.TestCase):

    """
    Test buildbot_worker.scripts.stop.stop()
    """
    config = {"basedir": "dummy", "quiet": False}

    def test_bad_basedir(self):
        """
        test calling stop() with invalid basedir path
        """

        # patch isWorkerDir() to fail
        self.setupUpIsWorkerDir(False)

        # call startCommand() and check that correct exit code is returned
        self.assertEqual(stop.stop(self.config), 1, "unexpected exit code")

        # check that isWorkerDir was called with correct argument
        self.isWorkerDir.assert_called_once_with(self.config["basedir"])

    def test_no_slave_running(self):
        """
        test calling stop() when no slave is running
        """
        self.setUpLogging()

        # patch basedir check to always succeed
        self.setupUpIsWorkerDir(True)

        # patch stopWorker() to raise an exception
        mock_stopWorker = mock.Mock(side_effect=stop.WorkerNotRunning())
        self.patch(stop, "stopWorker", mock_stopWorker)

        stop.stop(self.config)

        self.assertLogged("buildbot_worker not running")

    def test_successful_stop(self):
        """
        test calling stop() when slave is running
        """

        # patch basedir check to always succeed
        self.setupUpIsWorkerDir(True)

        # patch stopWorker() to do nothing
        mock_stopWorker = mock.Mock()
        self.patch(stop, "stopWorker", mock_stopWorker)

        stop.stop(self.config)
        mock_stopWorker.assert_called_once_with(self.config["basedir"],
                                               self.config["quiet"],
                                               "TERM")
