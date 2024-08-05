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

import builtins
import errno
import os
import re
import shutil
import sys
from io import StringIO
from unittest import mock

from twisted.python import log

from buildbot_worker.scripts import base


def nl(s):
    """Convert the given string to the native newline format, assuming it is
    already in normal UNIX newline format (\n).  Use this to create the
    appropriate expectation in an assertEqual"""
    if not isinstance(s, str):
        return s
    return s.replace('\n', os.linesep)


class BasedirMixin:
    """Mix this in and call setUpBasedir and tearDownBasedir to set up
    a clean basedir with a name given in self.basedir."""

    def setUpBasedir(self):
        self.basedir = "test-basedir"
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)

    def tearDownBasedir(self):
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)


class IsWorkerDirMixin:
    """
    Mixin for setting up mocked base.isWorkerDir() function
    """

    def setupUpIsWorkerDir(self, return_value):
        self.isWorkerDir = mock.Mock(return_value=return_value)
        self.patch(base, "isWorkerDir", self.isWorkerDir)


class PatcherMixin:
    """
    Mix this in to get a few special-cased patching methods
    """

    def patch_os_uname(self, replacement):
        # twisted's 'patch' doesn't handle the case where an attribute
        # doesn't exist..
        if hasattr(os, 'uname'):
            self.patch(os, 'uname', replacement)
        else:

            def cleanup():
                del os.uname

            self.addCleanup(cleanup)
            os.uname = replacement


class FileIOMixin:
    """
    Mixin for patching open(), read() and write() to simulate successful
    I/O operations and various I/O errors.
    """

    def setUpOpen(self, file_contents="dummy-contents"):
        """
        patch open() to return file object with provided contents.

        @param file_contents: contents that will be returned by file object's
                              read() method
        """
        # Use mock.mock_open() to create a substitute for
        # open().
        fakeOpen = mock.mock_open(read_data=file_contents)

        # When fakeOpen() is called, it returns a Mock
        # that has these methods: read(), write(), __enter__(), __exit__().
        # read() will always return the value of the 'file_contents variable.
        self.fileobj = fakeOpen()

        # patch open() to always return our Mock file object
        self.open = mock.Mock(return_value=self.fileobj)
        self.patch(builtins, "open", self.open)

    def setUpOpenError(self, errno=errno.ENOENT, strerror="dummy-msg", filename="dummy-file"):
        """
        patch open() to raise IOError

        @param    errno: exception's errno value
        @param strerror: exception's strerror value
        @param filename: exception's filename value
        """
        # Use mock.mock_open() to create a substitute for
        # open().
        fakeOpen = mock.mock_open()

        # Add side_effect so that calling fakeOpen() will always
        # raise an IOError.
        fakeOpen.side_effect = OSError(errno, strerror, filename)
        self.open = fakeOpen
        self.patch(builtins, "open", self.open)

    def setUpReadError(self, errno=errno.EIO, strerror="dummy-msg", filename="dummy-file"):
        """
        patch open() to return a file object that will raise IOError on read()

        @param    errno: exception's errno value
        @param strerror: exception's strerror value
        @param filename: exception's filename value

        """
        # Use mock.mock_open() to create a substitute for
        # open().
        fakeOpen = mock.mock_open()

        # When fakeOpen() is called, it returns a Mock
        # that has these methods: read(), write(), __enter__(), __exit__().
        self.fileobj = fakeOpen()

        # Add side_effect so that calling read() will always
        # raise an IOError.
        self.fileobj.read.side_effect = OSError(errno, strerror, filename)

        # patch open() to always return our Mock file object
        self.open = mock.Mock(return_value=self.fileobj)
        self.patch(builtins, "open", self.open)

    def setUpWriteError(self, errno=errno.ENOSPC, strerror="dummy-msg", filename="dummy-file"):
        """
        patch open() to return a file object that will raise IOError on write()

        @param    errno: exception's errno value
        @param strerror: exception's strerror value
        @param filename: exception's filename value
        """
        # Use mock.mock_open() to create a substitute for
        # open().
        fakeOpen = mock.mock_open()

        # When fakeOpen() is called, it returns a Mock
        # that has these methods: read(), write(), __enter__(), __exit__().
        self.fileobj = fakeOpen()

        # Add side_effect so that calling write() will always
        # raise an IOError.
        self.fileobj.write.side_effect = OSError(errno, strerror, filename)

        # patch open() to always return our Mock file object
        self.open = mock.Mock(return_value=self.fileobj)
        self.patch(builtins, "open", self.open)


class LoggingMixin:
    def setUpLogging(self):
        self._logEvents = []
        log.addObserver(self._logEvents.append)
        self.addCleanup(log.removeObserver, self._logEvents.append)

    def assertLogged(self, *args):
        for regexp in args:
            r = re.compile(regexp)
            for event in self._logEvents:
                msg = log.textFromEventDict(event)
                if msg is not None and r.search(msg):
                    return
            self.fail(f"{regexp!r} not matched in log output.\n{self._logEvents} ")

    def assertWasQuiet(self):
        self.assertEqual(self._logEvents, [])


class StdoutAssertionsMixin:
    """
    Mix this in to be able to assert on stdout during the test
    """

    def setUpStdoutAssertions(self):
        self.stdout = StringIO()
        self.patch(sys, 'stdout', self.stdout)

    def assertWasQuiet(self):
        self.assertEqual(self.stdout.getvalue(), '')

    def assertInStdout(self, exp):
        self.assertIn(exp, self.stdout.getvalue())

    def assertStdoutEqual(self, exp, msg=None):
        self.assertEqual(exp, self.stdout.getvalue(), msg)

    def getStdout(self):
        return self.stdout.getvalue().strip()
