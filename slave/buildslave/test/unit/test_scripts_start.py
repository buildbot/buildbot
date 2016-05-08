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
from twisted.trial import unittest

from buildslave.scripts import start
from buildslave.test.util import misc


class TestStartCommand(unittest.TestCase, misc.IsBuildslaveDirMixin):

    """
    Test buildslave.scripts.startup.startCommand()
    """

    def test_start_command_bad_basedir(self):
        """
        test calling startCommand() with invalid basedir path
        """

        # patch isBuildslaveDir() to fail
        self.setupUpIsBuildslaveDir(False)

        # call startCommand() and check that correct exit code is returned
        config = {"basedir": "dummy"}
        self.assertEqual(start.startCommand(config), 1, "unexpected exit code")

        # check that isBuildslaveDir was called with correct argument
        self.isBuildslaveDir.assert_called_once_with("dummy")

    def test_start_command_good(self):
        """
        test successful startCommand() call
        """

        # patch basedir check to always succeed
        self.setupUpIsBuildslaveDir(True)

        # patch startSlave() to do nothing
        mocked_startSlave = mock.Mock(return_value=0)
        self.patch(start, "startSlave", mocked_startSlave)

        config = {"basedir": "dummy", "nodaemon": False, "quiet": False}
        self.assertEqual(start.startCommand(config), 0, "unexpected exit code")

        # check that isBuildslaveDir() and startSlave() were called
        # with correct argument
        self.isBuildslaveDir.assert_called_once_with("dummy")
        mocked_startSlave.assert_called_once_with(config["basedir"],
                                                  config["quiet"],
                                                  config["nodaemon"])
