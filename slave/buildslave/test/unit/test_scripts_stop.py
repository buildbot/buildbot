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

import mock
from twisted.trial import unittest

from buildslave.scripts import stop
from buildslave.test.util import compat
from buildslave.test.util import misc


class TestStopSlave(misc.FileIOMixin,
                    misc.LoggingMixin,
                    unittest.TestCase):

    """
    Test buildslave.scripts.stop.stopSlave()
    """
    PID = 9876

    def setUp(self):
        self.setUpLogging()

        # patch os.chdir() to do nothing
        self.patch(os, "chdir", mock.Mock())

    def test_no_pid_file(self):
        """
        test calling stopSlave() when no pid file is present
        """

        # patch open() to raise 'file not found' exception
        self.setUpOpenError(2)

        # check that stop() raises SlaveNotRunning exception
        self.assertRaises(stop.SlaveNotRunning,
                          stop.stopSlave, None, False)

    @compat.skipUnlessPlatformIs("posix")
    def test_successful_stop(self):
        """
        test stopSlave() on a successful slave stop
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

        # check that stopSlave() sends expected signal to right PID
        # and print correct message to the log
        stop.stopSlave(None, False)
        mocked_kill.assert_has_calls([mock.call(self.PID, signal.SIGTERM),
                                      mock.call(self.PID, 0)])

        self.assertLogged("buildslave process %s is dead" % self.PID)


class TestStop(misc.IsBuildslaveDirMixin,
               misc.LoggingMixin,
               unittest.TestCase):

    """
    Test buildslave.scripts.stop.stop()
    """
    config = {"basedir": "dummy", "quiet": False}

    def test_bad_basedir(self):
        """
        test calling stop() with invalid basedir path
        """

        # patch isBuildslaveDir() to fail
        self.setupUpIsBuildslaveDir(False)

        # call startCommand() and check that correct exit code is returned
        self.assertEqual(stop.stop(self.config), 1, "unexpected exit code")

        # check that isBuildslaveDir was called with correct argument
        self.isBuildslaveDir.assert_called_once_with(self.config["basedir"])

    def test_no_slave_running(self):
        """
        test calling stop() when no slave is running
        """
        self.setUpLogging()

        # patch basedir check to always succeed
        self.setupUpIsBuildslaveDir(True)

        # patch stopSlave() to raise an exception
        mock_stopSlave = mock.Mock(side_effect=stop.SlaveNotRunning())
        self.patch(stop, "stopSlave", mock_stopSlave)

        stop.stop(self.config)

        self.assertLogged("buildslave not running")

    def test_successful_stop(self):
        """
        test calling stop() when slave is running
        """

        # patch basedir check to always succeed
        self.setupUpIsBuildslaveDir(True)

        # patch stopSlave() to do nothing
        mock_stopSlave = mock.Mock()
        self.patch(stop, "stopSlave", mock_stopSlave)

        stop.stop(self.config)
        mock_stopSlave.assert_called_once_with(self.config["basedir"],
                                               self.config["quiet"],
                                               "TERM")
