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
import os

from buildworker.scripts import upgrade_worker
from buildworker.test.util import misc
from twisted.trial import unittest

MODERN_BUILDBOT_TAC = \
"""# dummy buildbot.tac
import os

from buildworker.bot import BuildWorker
"""

OLD_BUILDBOT_TAC = \
"""# dummy buildbot.tac
import os

from buildbot.worker.bot import BuildWorker
"""


class TestUpgradeWorker(misc.IsBuildworkerDirMixin,
                       misc.FileIOMixin,
                       misc.LoggingMixin,
                       unittest.TestCase):

    """
    Test buildworker.scripts.runner.upgradeWorker()
    """
    config = {"basedir": "dummy"}

    def setUp(self):
        self.setUpLogging()

        # expected buildbot.tac relative path
        self.buildbot_tac = os.path.join(self.config["basedir"],
                                         "buildbot.tac")

    def test_upgradeWorker_bad_basedir(self):
        """
        test calling upgradeWorker() with bad base directory
        """
        # override isBuildworkerDir() to always fail
        self.setupUpIsBuildworkerDir(False)

        # call upgradeWorker() and check that correct exit code is returned
        self.assertEqual(upgrade_worker.upgradeWorker(self.config), 1,
                         "unexpected exit code")

        # check that isBuildworkerDir was called with correct argument
        self.isBuildworkerDir.assert_called_once_with("dummy")

    def test_upgradeWorker_no_changes(self):
        """
        test calling upgradeWorker() on a buildbot.tac that don't need to be
        upgraded
        """
        # patch basedir check to always succeed
        self.setupUpIsBuildworkerDir(True)

        # patch open() to return a modern buildbot.tac file
        self.setUpOpen(MODERN_BUILDBOT_TAC)

        # call upgradeWorker() and check the success exit code is returned
        self.assertEqual(upgrade_worker.upgradeWorker(self.config), 0,
                         "unexpected exit code")

        # check message to the log
        self.assertLogged("No changes made")

        # check that open() was called with correct path
        self.open.assert_called_once_with(self.buildbot_tac)

        # check that no writes where made
        self.assertFalse(self.fileobj.write.called,
                         "unexpected write to buildbot.tac file")

    def test_upgradeWorker_updated(self):
        """
        test calling upgradeWorker() on an older buildbot.tac, that need to
        be updated
        """
        # patch basedir check to always succeed
        self.setupUpIsBuildworkerDir(True)

        # patch open() to return older buildbot.tac file
        self.setUpOpen(OLD_BUILDBOT_TAC)

        # call upgradeWorker() and check the success exit code is returned
        self.assertEqual(upgrade_worker.upgradeWorker(self.config), 0,
                         "unexpected exit code")

        # check message to the log
        self.assertLogged("buildbot.tac updated")

        # check calls to open()
        self.open.assert_has_calls([mock.call(self.buildbot_tac),
                                    mock.call(self.buildbot_tac, "w")])

        # check that we wrote correct updated buildbot.tac file
        self.fileobj.write.assert_called_once_with(MODERN_BUILDBOT_TAC)
