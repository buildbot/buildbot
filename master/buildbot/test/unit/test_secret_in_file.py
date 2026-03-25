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
from typing import TYPE_CHECKING

from twisted.internet import defer
from twisted.python.filepath import FilePath
from twisted.trial import unittest

from buildbot.secrets.providers.file import SecretInAFile
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.util.misc import writeLocalFile

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class TestSecretInFile(ConfigErrorsMixin, unittest.TestCase):
    def createTempDir(self, dirname: str) -> str:
        tempdir = FilePath(self.mktemp())
        tempdir.createDirectory()
        return tempdir.path

    def createFileTemp(
        self, tempdir: str, filename: str, text: str = "", chmodRights: int = 0o700
    ) -> str:
        file_path = os.path.join(tempdir, filename)
        writeLocalFile(file_path, text, chmodRights)
        return file_path

    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.tmp_dir = self.createTempDir("temp")
        self.filepath = self.createFileTemp(self.tmp_dir, "tempfile.txt", text="key value\n")
        self.srvfile = SecretInAFile(self.tmp_dir)
        yield self.srvfile.startService()
        self.addCleanup(self.srvfile.stopService)

    def testCheckConfigSecretInAFileService(self) -> None:
        self.assertEqual(self.srvfile.name, "SecretInAFile")
        self.assertEqual(self.srvfile._dirname, self.tmp_dir)

    def testCheckConfigErrorSecretInAFileService(self) -> None:
        if os.name != "posix":
            self.skipTest("Permission checks only works on posix systems")
        filepath = self.createFileTemp(self.tmp_dir, "tempfile2.txt", chmodRights=stat.S_IROTH)
        expctd_msg_error = (
            " on file tempfile2.txt are too "
            "open. It is required that your secret files are"
            " NOT accessible by others!"
        )
        with self.assertRaisesConfigError(expctd_msg_error):
            self.srvfile.checkConfig(self.tmp_dir)
        os.remove(filepath)

    @defer.inlineCallbacks
    def testCheckConfigfileExtension(self) -> InlineCallbacksType[None]:
        filepath = self.createFileTemp(
            self.tmp_dir, "tempfile2.ini", text="test suffix", chmodRights=stat.S_IRWXU
        )
        filepath2 = self.createFileTemp(
            self.tmp_dir, "tempfile2.txt", text="some text", chmodRights=stat.S_IRWXU
        )
        yield self.srvfile.reconfigService(self.tmp_dir, suffixes=[".ini"])  # type: ignore[func-returns-value]
        self.assertEqual(self.srvfile.get("tempfile2"), "test suffix")
        self.assertEqual(self.srvfile.get("tempfile3"), None)
        os.remove(filepath)
        os.remove(filepath2)

    @defer.inlineCallbacks
    def testReconfigSecretInAFileService(self) -> InlineCallbacksType[None]:
        otherdir = self.createTempDir("temp2")
        yield self.srvfile.reconfigService(otherdir)  # type: ignore[func-returns-value]
        self.assertEqual(self.srvfile.name, "SecretInAFile")
        self.assertEqual(self.srvfile._dirname, otherdir)

    def testGetSecretInFile(self) -> None:
        value = self.srvfile.get("tempfile.txt")
        self.assertEqual(value, "key value")

    @defer.inlineCallbacks
    def testGetSecretInFileSuffixes(self) -> InlineCallbacksType[None]:
        yield self.srvfile.reconfigService(self.tmp_dir, suffixes=[".txt"])  # type: ignore[func-returns-value]
        value = self.srvfile.get("tempfile")
        self.assertEqual(value, "key value")

    def testGetSecretInFileNotFound(self) -> None:
        value = self.srvfile.get("tempfile2.txt")
        self.assertEqual(value, None)

    @defer.inlineCallbacks
    def testGetSecretInFileNoStrip(self) -> InlineCallbacksType[None]:
        yield self.srvfile.reconfigService(self.tmp_dir, strip=False)  # type: ignore[func-returns-value]
        value = self.srvfile.get("tempfile.txt")
        self.assertEqual(value, "key value\n")
