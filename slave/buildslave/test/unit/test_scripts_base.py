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

import io
import os
import re
import sys

from twisted.trial import unittest

from buildslave.scripts import base
from buildslave.test.util import misc


class TestIsBuildslaveDir(misc.FileIOMixin, misc.LoggingMixin, unittest.TestCase):

    """Test buildslave.scripts.base.isBuildslaveDir()"""

    def setUp(self):
        # capture output to stdout
        self.mocked_stdout = io.BytesIO()
        self.patch(sys, "stdout", self.mocked_stdout)

        self.setUpLogging()

        # generate OS specific relative path to buildbot.tac inside basedir
        self.tac_file_path = os.path.join("testdir", "buildbot.tac")

    def assertReadErrorMessage(self, strerror):

        self.assertLogged(
            re.escape("error reading '%s': %s" % (
                self.tac_file_path, strerror)),
            "invalid buildslave directory 'testdir'")

    def test_open_error(self):
        """Test that open() errors are handled."""

        # patch open() to raise IOError
        self.setUpOpenError(1, "open-error", "dummy")

        # check that isBuildslaveDir() flags directory as invalid
        self.assertFalse(base.isBuildslaveDir("testdir"))

        # check that correct error message was printed to stdout
        self.assertReadErrorMessage("open-error")

        # check that open() was called with correct path
        self.open.assert_called_once_with(self.tac_file_path)

    def test_read_error(self):
        """Test that read() errors on buildbot.tac file are handled."""

        # patch open() to return file object that raises IOError on read()
        self.setUpReadError(1, "read-error", "dummy")

        # check that isBuildslaveDir() flags directory as invalid
        self.assertFalse(base.isBuildslaveDir("testdir"))

        # check that correct error message was printed to stdout
        self.assertReadErrorMessage("read-error")

        # check that open() was called with correct path
        self.open.assert_called_once_with(self.tac_file_path)

    def test_unexpected_tac_contents(self):
        """Test that unexpected contents in buildbot.tac is handled."""

        # patch open() to return file with unexpected contents
        self.setUpOpen("dummy-contents")

        # check that isBuildslaveDir() flags directory as invalid
        self.assertFalse(base.isBuildslaveDir("testdir"))

        # check that correct error message was printed to the log
        self.assertLogged(
            re.escape("unexpected content in '%s'" % self.tac_file_path),
            "invalid buildslave directory 'testdir'",
            "unexpected error message on stdout")
        # check that open() was called with correct path
        self.open.assert_called_once_with(self.tac_file_path)

    def test_slavedir_good(self):
        """Test checking valid buildslave directory."""

        # patch open() to return file with valid buildslave tac contents
        self.setUpOpen("Application('buildslave')")

        # check that isBuildslaveDir() flags directory as good
        self.assertTrue(base.isBuildslaveDir("testdir"))

        # check that open() was called with correct path
        self.open.assert_called_once_with(self.tac_file_path)
