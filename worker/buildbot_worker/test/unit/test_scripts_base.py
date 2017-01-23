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

from __future__ import absolute_import
from __future__ import print_function

import os
import sys

from twisted.trial import unittest

from buildbot_worker.compat import NativeStringIO
from buildbot_worker.scripts import base
from buildbot_worker.test.util import misc


class TestIsWorkerDir(misc.FileIOMixin, misc.StdoutAssertionsMixin,
                      unittest.TestCase):

    """Test buildbot_worker.scripts.base.isWorkerDir()"""

    def setUp(self):
        # capture output to stdout
        self.mocked_stdout = NativeStringIO()
        self.patch(sys, "stdout", self.mocked_stdout)

        # generate OS specific relative path to buildbot.tac inside basedir
        self.tac_file_path = os.path.join("testdir", "buildbot.tac")

    def assertReadErrorMessage(self, strerror):
        expected_message = "error reading '%s': %s\n" \
                           "invalid worker directory 'testdir'\n" \
            % (self.tac_file_path, strerror)
        self.assertEqual(self.mocked_stdout.getvalue(),
                         expected_message,
                         "unexpected error message on stdout")

    def test_open_error(self):
        """Test that open() errors are handled."""

        # patch open() to raise IOError
        self.setUpOpenError(1, "open-error", "dummy")

        # check that isWorkerDir() flags directory as invalid
        self.assertFalse(base.isWorkerDir("testdir"))

        # check that correct error message was printed to stdout
        self.assertReadErrorMessage("open-error")

        # check that open() was called with correct path
        self.open.assert_called_once_with(self.tac_file_path)

    def test_read_error(self):
        """Test that read() errors on buildbot.tac file are handled."""

        # patch open() to return file object that raises IOError on read()
        self.setUpReadError(1, "read-error", "dummy")

        # check that isWorkerDir() flags directory as invalid
        self.assertFalse(base.isWorkerDir("testdir"))

        # check that correct error message was printed to stdout
        self.assertReadErrorMessage("read-error")

        # check that open() was called with correct path
        self.open.assert_called_once_with(self.tac_file_path)

    def test_unexpected_tac_contents(self):
        """Test that unexpected contents in buildbot.tac is handled."""

        # patch open() to return file with unexpected contents
        self.setUpOpen("dummy-contents")

        # check that isWorkerDir() flags directory as invalid
        self.assertFalse(base.isWorkerDir("testdir"))

        # check that correct error message was printed to stdout
        self.assertEqual(self.mocked_stdout.getvalue(),
                         "unexpected content in '%s'\n" % self.tac_file_path +
                         "invalid worker directory 'testdir'\n",
                         "unexpected error message on stdout")
        # check that open() was called with correct path
        self.open.assert_called_once_with(self.tac_file_path)

    def test_workerdir_good(self):
        """Test checking valid worker directory."""

        # patch open() to return file with valid worker tac contents
        self.setUpOpen("Application('buildbot-worker')")

        # check that isWorkerDir() flags directory as good
        self.assertTrue(base.isWorkerDir("testdir"))

        # check that open() was called with correct path
        self.open.assert_called_once_with(self.tac_file_path)
