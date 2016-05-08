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

import __builtin__
import errno
import os
import re
import shutil

import mock
from twisted.python import log

from buildslave.scripts import base


def nl(s):
    """Convert the given string to the native newline format, assuming it is
    already in normal UNIX newline format (\n).  Use this to create the
    appropriate expectation in a failUnlessEqual"""
    if not isinstance(s, basestring):
        return s
    return s.replace('\n', os.linesep)


class BasedirMixin(object):

    """Mix this in and call setUpBasedir and tearDownBasedir to set up
    a clean basedir with a name given in self.basedir."""

    def setUpBasedir(self):
        self.basedir = "test-basedir"
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)

    def tearDownBasedir(self):
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)


class IsBuildslaveDirMixin(object):

    """
    Mixin for setting up mocked base.isBuildslaveDir() function
    """

    def setupUpIsBuildslaveDir(self, return_value):
        self.isBuildslaveDir = mock.Mock(return_value=return_value)
        self.patch(base, "isBuildslaveDir", self.isBuildslaveDir)


class PatcherMixin(object):

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


class FileIOMixin(object):

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
        # create mocked file object that returns 'file_contents' on read()
        # and tracks any write() calls
        self.fileobj = mock.Mock()
        self.fileobj.read = mock.Mock(return_value=file_contents)
        self.fileobj.write = mock.Mock()

        # patch open() to return mocked object
        self.open = mock.Mock(return_value=self.fileobj)
        self.patch(__builtin__, "open", self.open)

    def setUpOpenError(self, errno=errno.ENOENT, strerror="dummy-msg",
                       filename="dummy-file"):
        """
        patch open() to raise IOError

        @param    errno: exception's errno value
        @param strerror: exception's strerror value
        @param filename: exception's filename value
        """
        self.open = mock.Mock(side_effect=IOError(errno, strerror, filename))
        self.patch(__builtin__, "open", self.open)

    def setUpReadError(self, errno=errno.EIO, strerror="dummy-msg",
                       filename="dummy-file"):
        """
        patch open() to return a file object that will raise IOError on read()

        @param    errno: exception's errno value
        @param strerror: exception's strerror value
        @param filename: exception's filename value

        """
        self.fileobj = mock.Mock()
        self.fileobj.read = mock.Mock(side_effect=IOError(errno, strerror,
                                                          filename))
        self.open = mock.Mock(return_value=self.fileobj)
        self.patch(__builtin__, "open", self.open)

    def setUpWriteError(self, errno=errno.ENOSPC, strerror="dummy-msg",
                        filename="dummy-file"):
        """
        patch open() to return a file object that will raise IOError on write()

        @param    errno: exception's errno value
        @param strerror: exception's strerror value
        @param filename: exception's filename value
        """
        self.fileobj = mock.Mock()
        self.fileobj.write = mock.Mock(side_effect=IOError(errno, strerror,
                                                           filename))
        self.open = mock.Mock(return_value=self.fileobj)
        self.patch(__builtin__, "open", self.open)


class LoggingMixin(object):

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
            self.fail(
                "%r not matched in log output.\n%s " % (regexp, self._logEvents))

    def assertWasQuiet(self):
        self.assertEqual(self._logEvents, [])
