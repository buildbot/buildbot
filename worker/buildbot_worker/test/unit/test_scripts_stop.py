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
import os
import signal
import time
from typing import Any

from twisted.trial import unittest

from buildbot_worker.scripts import stop
from buildbot_worker.test.util import compat
from buildbot_worker.test.util import misc

try:
    from unittest import mock
except ImportError:
    from unittest import mock


class TestStopWorker(misc.FileIOMixin, misc.StdoutAssertionsMixin, unittest.TestCase):
    """
    Test buildbot_worker.scripts.stop.stopWorker()
    """

    PID = 9876

    def setUp(self) -> None:
        self.setUpStdoutAssertions()

        # patch os.chdir() to do nothing
        self.patch(os, "chdir", mock.Mock())

    def test_no_pid_file(self) -> None:
        """
        test calling stopWorker() when no pid file is present
        """

        # patch open() to raise 'file not found' exception
        self.setUpOpenError(2)

        # check that stop() raises WorkerNotRunning exception
        with self.assertRaises(stop.WorkerNotRunning):
            stop.stopWorker("", False)

    @compat.skipUnlessPlatformIs("posix")
    def test_successful_stop(self) -> None:
        """
        test stopWorker() on a successful worker stop
        """

        def emulated_kill(pid: Any, sig: int) -> None:
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
        # and print correct message to stdout
        exit_code = stop.stopWorker("", False)
        self.assertEqual(exit_code, 0)
        mocked_kill.assert_has_calls([mock.call(self.PID, signal.SIGTERM), mock.call(self.PID, 0)])

        self.assertStdoutEqual(f"worker process {self.PID} is dead\n")

    @compat.skipUnlessPlatformIs("posix")
    def test_stop_timeout(self) -> None:
        """
        test stopWorker() when stop timeouts
        """

        # patch open() to return a pid file
        self.setUpOpen(str(self.PID))

        # patch os.kill to emulate successful kill
        mocked_kill = mock.Mock()
        self.patch(os, "kill", mocked_kill)

        # don't waste time
        self.patch(time, "sleep", mock.Mock())

        # check that stopWorker() sends expected signal to right PID
        # and print correct message to stdout
        exit_code = stop.stopWorker("", False)
        self.assertEqual(exit_code, 1)
        mocked_kill.assert_has_calls([mock.call(self.PID, signal.SIGTERM), mock.call(self.PID, 0)])

        self.assertStdoutEqual("never saw process go away\n")


class TestStop(misc.IsWorkerDirMixin, misc.StdoutAssertionsMixin, unittest.TestCase):
    """
    Test buildbot_worker.scripts.stop.stop()
    """

    config = {"basedir": "dummy", "quiet": False}

    def test_bad_basedir(self) -> None:
        """
        test calling stop() with invalid basedir path
        """

        # patch isWorkerDir() to fail
        self.setupUpIsWorkerDir(False)

        # call startCommand() and check that correct exit code is returned
        self.assertEqual(stop.stop(self.config), 1, "unexpected exit code")

        # check that isWorkerDir was called with correct argument
        self.isWorkerDir.assert_called_once_with(self.config["basedir"])

    def test_no_worker_running(self) -> None:
        """
        test calling stop() when no worker is running
        """
        self.setUpStdoutAssertions()

        # patch basedir check to always succeed
        self.setupUpIsWorkerDir(True)

        # patch stopWorker() to raise an exception
        mock_stopWorker = mock.Mock(side_effect=stop.WorkerNotRunning())
        self.patch(stop, "stopWorker", mock_stopWorker)

        exit_code = stop.stop(self.config)
        self.assertEqual(exit_code, 0)

        self.assertStdoutEqual("worker not running\n")

    def test_successful_stop(self) -> None:
        """
        test calling stop() when worker is running
        """

        # patch basedir check to always succeed
        self.setupUpIsWorkerDir(True)

        # patch stopWorker() to do nothing
        mock_stopWorker = mock.Mock(return_value=0)
        self.patch(stop, "stopWorker", mock_stopWorker)

        exit_code = stop.stop(self.config)
        self.assertEqual(exit_code, 0)
        mock_stopWorker.assert_called_once_with(
            self.config["basedir"], self.config["quiet"], "TERM"
        )

    def test_failed_stop(self) -> None:
        """
        test failing stop()
        """

        # patch basedir check to always succeed
        self.setupUpIsWorkerDir(True)

        # patch stopWorker() to do nothing
        mock_stopWorker = mock.Mock(return_value=17)
        self.patch(stop, "stopWorker", mock_stopWorker)

        exit_code = stop.stop(self.config)
        self.assertEqual(exit_code, 17)
        mock_stopWorker.assert_called_once_with(
            self.config["basedir"], self.config["quiet"], "TERM"
        )
