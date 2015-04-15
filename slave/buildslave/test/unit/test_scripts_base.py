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

import sys
import mock
import __builtin__
import cStringIO
from twisted.trial import unittest
from buildslave.scripts import base

class TestIsBuildslaveDir(unittest.TestCase):
    """Test buildslave.scripts.base.isBuildslaveDir()"""

    def setUp(self):
        # capture output to stdout
        self.mocked_stdout = cStringIO.StringIO()
        self.patch(sys, "stdout", self.mocked_stdout)

    def assertReadErrorMessage(self, strerror):
        self.assertEqual(self.mocked_stdout.getvalue(),
                         "error reading 'testdir/buildbot.tac': %s\n"
                         "invalid buildslave directory 'testdir'\n" % strerror,
                         "unexpected error message on stdout")

    def setUpMockedTacFile(self, file_contents):
        """Patch open() to return a file object with specified contents."""

        fileobj_mock = mock.Mock()
        fileobj_mock.read = mock.Mock(return_value=file_contents)
        open_mock = mock.Mock(return_value=fileobj_mock)
        self.patch(__builtin__, "open", open_mock)

        return (fileobj_mock, open_mock)

    def test_open_error(self):
        """Test that open() errors are handled."""

        # patch open() to raise IOError
        open_mock = mock.Mock(side_effect=IOError(1, "open-error", "dummy"))
        self.patch(__builtin__, "open", open_mock)

        # check that isBuildslaveDir() flags directory as invalid
        self.assertFalse(base.isBuildslaveDir("testdir"))

        # check that correct error message was printed to stdout
        self.assertReadErrorMessage("open-error")

        # check that open() was called with correct path
        open_mock.assert_called_once_with("testdir/buildbot.tac")

    def test_read_error(self):
        """Test that read() errors on buildbot.tac file are handled."""

        # patch open() to return file object that raises IOError on read()
        fileobj_mock = mock.Mock()
        fileobj_mock.read = mock.Mock(side_effect=IOError(1, "read-error",
                                                          "dummy"))
        open_mock = mock.Mock(return_value=fileobj_mock)
        self.patch(__builtin__, "open", open_mock)

        # check that isBuildslaveDir() flags directory as invalid
        self.assertFalse(base.isBuildslaveDir("testdir"))

        # check that correct error message was printed to stdout
        self.assertReadErrorMessage("read-error")

        # check that open() was called with correct path
        open_mock.assert_called_once_with("testdir/buildbot.tac")

    def test_unexpected_tac_contents(self):
        """Test that unexpected contents in buildbot.tac is handled."""

        # patch open() to return file with unexpected contents
        (fileobj_mock, open_mock) = self.setUpMockedTacFile("dummy-contents")

        # check that isBuildslaveDir() flags directory as invalid
        self.assertFalse(base.isBuildslaveDir("testdir"))

        # check that correct error message was printed to stdout
        self.assertEqual(self.mocked_stdout.getvalue(),
                         "unexpected content in 'testdir/buildbot.tac'\n"
                         "invalid buildslave directory 'testdir'\n",
                         "unexpected error message on stdout")
        # check that open() was called with correct path
        open_mock.assert_called_once_with("testdir/buildbot.tac")

    def test_slavedir_good(self):
        """Test checking valid buildslave directory."""

        # patch open() to return file with valid buildslave tac contents
        (fileobj_mock, open_mock) = \
            self.setUpMockedTacFile("Application('buildslave')")

        # check that isBuildslaveDir() flags directory as good
        self.assertTrue(base.isBuildslaveDir("testdir"))

        # check that open() was called with correct path
        open_mock.assert_called_once_with("testdir/buildbot.tac")
