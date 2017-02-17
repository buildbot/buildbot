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
import stat

from twisted.internet import defer
from twisted.python.filepath import FilePath
from twisted.trial import unittest

from buildbot.secrets.providers.file import SecretInAFile
from buildbot.test.util.config import ConfigErrorsMixin


class TestSecretInFile(ConfigErrorsMixin, unittest.TestCase):

    def createTempDir(self, dirname):
        tempdir = FilePath(self.mktemp())
        tempdir.createDirectory()
        return tempdir.path

    def createFileTemp(self, tempdir, filename, text=None):
        if text is None:
            text = ""
        file_path = os.path.join(tempdir, filename)
        filetmp = open(file_path, 'w')
        with open(file_path, 'w') as filetmp:
            filetmp.write(text)
        return filetmp, file_path

    @defer.inlineCallbacks
    def setUp(self):
        self.tmp_dir = self.createTempDir("temp")
        filetmp, self.filepath = self.createFileTemp(self.tmp_dir,
                                                     "tempfile.txt",
                                                     text="key value")
        os.chmod(self.filepath, stat.S_IRWXU)
        self.srvfile = SecretInAFile(self.tmp_dir)
        yield self.srvfile.startService()

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.srvfile.stopService()

    def testCheckConfigSecretInAFileService(self):
        self.assertEqual(self.srvfile.name, "SecretInAFile")
        self.assertEqual(self.srvfile._dirname, self.tmp_dir)

    def testCheckConfigErrorSecretInAFileService(self):
        file_path_not_readable, filepath = self.createFileTemp(self.tmp_dir,
                                                               "tempfile2.txt")
        os.chmod(filepath, stat.S_IRGRP)
        expctd_msg_error = "Permissions 040 on file tempfile2.txt are too " \
                           "open. It is required that your secret files are" \
                           " NOT accessible by others!"
        self.assertRaisesConfigError(expctd_msg_error,
                                     lambda: self.srvfile.checkConfig(self.tmp_dir))
        os.remove(filepath)

    @defer.inlineCallbacks
    def testCheckConfigfileExtension(self):
        file_suffix, filepath = self.createFileTemp(self.tmp_dir,
                                                    "tempfile2.ini",
                                                    text="test suffix")
        file_not_suffix, filepath2 = self.createFileTemp(self.tmp_dir,
                                                         "tempfile2.txt",
                                                         text="some text")
        os.chmod(filepath, stat.S_IRWXU)
        os.chmod(filepath2, stat.S_IRWXU)
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
