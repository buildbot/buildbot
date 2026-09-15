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

import os
import stat
import tempfile
from unittest.mock import Mock

from twisted.trial import unittest

from buildbot.process import remotetransfer


# Test buildbot.steps.remotetransfer.FileWriter class.
class TestFileWriter(unittest.TestCase):
    # test FileWriter.__init__() method.

    def testInit(self) -> None:
        #
        # patch functions called in constructor
        #

        # patch os.path.exists() to always return False
        mockedExists = Mock(return_value=False)
        self.patch(os.path, "exists", mockedExists)

        # capture calls to os.makedirs()
        mockedMakedirs = Mock()
        self.patch(os, 'makedirs', mockedMakedirs)

        # capture calls to tempfile.mkstemp()
        mockedMkstemp = Mock(return_value=(7, "tmpname"))
        self.patch(tempfile, "mkstemp", mockedMkstemp)

        # capture calls to os.fdopen()
        mockedFdopen = Mock()
        self.patch(os, "fdopen", mockedFdopen)

        #
        # call _FileWriter constructor
        #
        destfile = os.path.join("dir", "file")
        remotetransfer.FileWriter(destfile, 64, stat.S_IRUSR)

        #
        # validate captured calls
        #
        absdir = os.path.dirname(os.path.abspath(os.path.join("dir", "file")))
        mockedExists.assert_called_once_with(absdir)
        mockedMakedirs.assert_called_once_with(absdir)
        mockedMkstemp.assert_called_once_with(dir=absdir, prefix='buildbot-transfer-')
        mockedFdopen.assert_called_once_with(7, 'wb')


class TestStringFileWriter(unittest.TestCase):
    def testBasic(self) -> None:
        sfw = remotetransfer.StringFileWriter()
        # StringFileWriter takes bytes or native string and outputs native strings
        sfw.remote_write(b'bytes')
        sfw.remote_write(' or str')
        sfw.remote_close()
        self.assertEqual(sfw.buffer, 'bytes or str')

    def testMultiByteCharacterSplitAcrossChunks(self) -> None:
        # A multi-byte UTF-8 character (e.g. U+00E9, 'é', encoded as b'\xc3\xa9') can land on a
        # chunk boundary when data is split into fixed-size blocks for transfer. Decoding each
        # chunk independently would raise UnicodeDecodeError; an incremental decoder must
        # instead buffer the incomplete tail and complete it with the next chunk.
        sfw = remotetransfer.StringFileWriter()
        data = 'café'.encode()
        for i in range(len(data)):
            sfw.remote_write(data[i : i + 1])
        sfw.remote_close()
        self.assertEqual(sfw.buffer, 'café')

    def testInvalidUtf8IsReplacedNotRaised(self) -> None:
        # Genuinely invalid (e.g. mixed-encoding) input must not raise either: raising here
        # would escape through the same PB remote-message handler that causes the hang, so
        # errors='replace' is used instead of errors='strict'.
        sfw = remotetransfer.StringFileWriter()
        sfw.remote_write(b'\xff\xfe')
        sfw.remote_close()
        self.assertEqual(sfw.buffer, '��')

    def testTruncatedFinalCharacterIsReplacedOnClose(self) -> None:
        # A file that ends mid-character (the final chunk's trailing bytes are an incomplete
        # sequence) is only resolved when remote_close() flushes the decoder with final=True.
        sfw = remotetransfer.StringFileWriter()
        data = 'café'.encode()
        sfw.remote_write(data[:-1])  # drop the final byte of the trailing 'é'
        sfw.remote_close()
        self.assertEqual(sfw.buffer, 'caf�')
