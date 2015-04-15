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
from buildslave.scripts import runner, base

class TestUpgradeSlave(unittest.TestCase):
    """
    Test buildslave.scripts.runner.upgradeSlave()
    """

    def test_upgradeSlave_bad_basedir(self):
        """
        test calling upgradeSlave() with bad base directory
        """
        # override isBuildslaveDir() to always fail
        mocked_isBuildslaveDir = mock.Mock(return_value=False)
        self.patch(base, "isBuildslaveDir", mocked_isBuildslaveDir)

        # call upgradeSlave() and check that SystemExit exception is raised
        config = {"basedir" : "dummy"}
        exception = self.assertRaises(SystemExit, runner.upgradeSlave, config)

        # check exit code
        self.assertEqual(exception.code, 1, "unexpected exit code")

        # check that isBuildslaveDir was called with correct argument
        mocked_isBuildslaveDir.assert_called_once_with("dummy")
