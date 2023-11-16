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

import os
import stat

from twisted.internet import defer
from twisted.python.filepath import FilePath
from twisted.trial import unittest

from buildbot.secrets.providers.file import SecretInAFile
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.util.misc import writeLocalFile


class TestSecretInFile(ConfigErrorsMixin, unittest.TestCase):

    def createTempDir(self, dirname):
        tempdir = FilePath(self.mktemp())
        tempdir.createDirectory()
        return tempdir.path

    def createFileTemp(self, tempdir, filename, text="", chmodRights=0o700):
        file_path = os.path.join(tempdir, filename)
        writeLocalFile(file_path, text, chmodRights)
        return file_path

    @defer.inlineCallbacks
    def setUp(self):
        self.tmp_dir = self.createTempDir("temp")
        self.filepath = self.createFileTemp(self.tmp_dir, "tempfile.txt",
                                            text="key value\n")
        self.srvfile = SecretInAFile(self.tmp_dir)
        yield self.srvfile.startService()

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.srvfile.stopService()

    def testCheckConfigSecretInAFileService(self):
        self.assertEqual(self.srvfile.name, "SecretInAFile")
        self.assertEqual(self.srvfile._dirname, self.tmp_dir)

    def testCheckConfigErrorSecretInAFileService(self):
        if os.name != "posix":
            self.skipTest("Permission checks only works on posix systems")
        filepath = self.createFileTemp(self.tmp_dir, "tempfile2.txt",
                                       chmodRights=stat.S_IROTH)
        expctd_msg_error = " on file tempfile2.txt are too " \
                           "open. It is required that your secret files are" \
                           " NOT accessible by others!"
        with self.assertRaisesConfigError(expctd_msg_error):
            self.srvfile.checkConfig(self.tmp_dir)
        os.remove(filepath)

    @defer.inlineCallbacks
    def testCheckConfigfileExtension(self):
        filepath = self.createFileTemp(self.tmp_dir, "tempfile2.ini",
                                       text="test suffix",
                                       chmodRights=stat.S_IRWXU)
        filepath2 = self.createFileTemp(self.tmp_dir, "tempfile2.txt",
                                        text="some text",
                                        chmodRights=stat.S_IRWXU)
        yield self.srvfile.reconfigService(self.tmp_dir, suffixes=[".ini"])
        self.assertEqual(self.srvfile.get("tempfile2"), "test suffix")
        self.assertEqual(self.srvfile.get("tempfile3"), None)
        os.remove(filepath)
        os.remove(filepath2)

    @defer.inlineCallbacks
    def testReconfigSecretInAFileService(self):
        otherdir = self.createTempDir("temp2")
        yield self.srvfile.reconfigService(otherdir)
        self.assertEqual(self.srvfile.name, "SecretInAFile")
        self.assertEqual(self.srvfile._dirname, otherdir)

    def testGetSecretInFile(self):
        value = self.srvfile.get("tempfile.txt")
        self.assertEqual(value, "key value")

    @defer.inlineCallbacks
    def testGetSecretInFileSuffixes(self):
        yield self.srvfile.reconfigService(self.tmp_dir, suffixes=[".txt"])
        value = self.srvfile.get("tempfile")
        self.assertEqual(value, "key value")

    def testGetSecretInFileNotFound(self):
        value = self.srvfile.get("tempfile2.txt")
        self.assertEqual(value, None)

    @defer.inlineCallbacks
    def testGetSecretInFileNoStrip(self):
        yield self.srvfile.reconfigService(self.tmp_dir, strip=False)
        value = self.srvfile.get("tempfile.txt")
        self.assertEqual(value, "key value\n")
