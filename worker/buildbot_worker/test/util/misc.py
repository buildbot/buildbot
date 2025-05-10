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
from __future__ import annotations

import builtins
import errno
import os
import re
import shutil
import sys
from io import StringIO
from typing import TYPE_CHECKING
from unittest import mock

from twisted.python import log
from twisted.trial.unittest import TestCase

from buildbot_worker.scripts import base

if TYPE_CHECKING:
    from typing import Any
    from typing import Callable


def nl(s: str | Any) -> str | Any:
    """Convert the given string to the native newline format, assuming it is
    already in normal UNIX newline format (\n).  Use this to create the
    appropriate expectation in an assertEqual"""
    if not isinstance(s, str):
        return s
    return s.replace('\n', os.linesep)


class BasedirMixin:
    """Mix this in and call setUpBasedir and tearDownBasedir to set up
    a clean basedir with a name given in self.basedir."""

    def setUpBasedir(self) -> None:
        self.basedir = "test-basedir"
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)

    def tearDownBasedir(self) -> None:
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)


class IsWorkerDirMixin:
    """
    Mixin for setting up mocked base.isWorkerDir() function
    """

    def setupUpIsWorkerDir(self, return_value: bool) -> None:
        self.isWorkerDir = mock.Mock(return_value=return_value)
        assert isinstance(self, TestCase)
        self.patch(base, "isWorkerDir", self.isWorkerDir)


class PatcherMixin:
    """
    Mix this in to get a few special-cased patching methods
    """

    def patch_os_uname(self, replacement: Callable[[], os.uname_result]) -> None:
        # twisted's 'patch' doesn't handle the case where an attribute
        # doesn't exist..
        assert isinstance(self, TestCase)
        if hasattr(os, 'uname'):
            self.patch(os, 'uname', replacement)
        else:

            def cleanup() -> None:
                del os.uname

            self.addCleanup(cleanup)
            os.uname = replacement


class FileIOMixin:
    """
    Mixin for patching open(), read() and write() to simulate successful
    I/O operations and various I/O errors.
    """

    def setUpOpen(self, file_contents: str = "dummy-contents") -> None:
        """
        patch open() to return file object with provided contents.

        @param file_contents: contents that will be returned by file object's
                              read() method
        """
        assert isinstance(self, TestCase)
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

    def setUpOpenError(
        self,
        errno: int = errno.ENOENT,
        strerror: str = "dummy-msg",
        filename: str = "dummy-file",
    ) -> None:
        """
        patch open() to raise IOError

        @param    errno: exception's errno value
        @param strerror: exception's strerror value
        @param filename: exception's filename value
        """
        assert isinstance(self, TestCase)
        # Use mock.mock_open() to create a substitute for
        # open().
        fakeOpen = mock.mock_open()

        # Add side_effect so that calling fakeOpen() will always
        # raise an IOError.
        fakeOpen.side_effect = OSError(errno, strerror, filename)
        self.open = fakeOpen
        self.patch(builtins, "open", self.open)

    def setUpReadError(
        self,
        errno: int = errno.EIO,
        strerror: str = "dummy-msg",
        filename: str = "dummy-file",
    ) -> None:
        """
        patch open() to return a file object that will raise IOError on read()

        @param    errno: exception's errno value
        @param strerror: exception's strerror value
        @param filename: exception's filename value

        """
        assert isinstance(self, TestCase)
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

    def setUpWriteError(
        self,
        errno: int = errno.ENOSPC,
        strerror: str = "dummy-msg",
        filename: str = "dummy-file",
    ) -> None:
        """
        patch open() to return a file object that will raise IOError on write()

        @param    errno: exception's errno value
        @param strerror: exception's strerror value
        @param filename: exception's filename value
        """
        assert isinstance(self, TestCase)
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
    def setUpLogging(self) -> None:
        assert isinstance(self, TestCase)
        self._logEvents: list[log.EventDict] = []
        log.addObserver(self._logEvents.append)
        self.addCleanup(log.removeObserver, self._logEvents.append)

    def assertLogged(self, *args: str) -> None:
        assert isinstance(self, TestCase)
        for regexp in args:
            r = re.compile(regexp)
            for event in self._logEvents:
                msg = log.textFromEventDict(event)
                if msg is not None and r.search(msg):
                    return
            self.fail(f"{regexp!r} not matched in log output.\n{self._logEvents} ")

    def assertWasQuiet(self) -> None:
        assert isinstance(self, TestCase)
        self.assertEqual(self._logEvents, [])


class StdoutAssertionsMixin:
    """
    Mix this in to be able to assert on stdout during the test
    """

    def setUpStdoutAssertions(self) -> None:
        assert isinstance(self, TestCase)
        self.stdout = StringIO()
        self.patch(sys, 'stdout', self.stdout)

    def assertWasQuiet(self) -> None:
        assert isinstance(self, TestCase)
        self.assertEqual(self.stdout.getvalue(), '')

    def assertInStdout(self, exp: str) -> None:
        assert isinstance(self, TestCase)
        self.assertIn(exp, self.stdout.getvalue())

    def assertStdoutEqual(self, exp: str, msg: str | None = None) -> None:
        assert isinstance(self, TestCase)
        self.assertEqual(exp, self.stdout.getvalue(), msg)

    def getStdout(self) -> str:
        return self.stdout.getvalue().strip()
