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
import subprocess
from pathlib import Path
from unittest.mock import Mock, PropertyMock
from unittest.mock import patch

from twisted.internet import defer
from twisted.python.filepath import FilePath
from twisted.trial import unittest

from buildbot.secrets.providers.passwordstore import SecretInPass
from buildbot.test.util.config import ConfigErrorsMixin


class TestSecretInPass(ConfigErrorsMixin, unittest.TestCase):

    def createTempDir(self, dirname):
        tempdir = FilePath(self.mktemp())
        tempdir.createDirectory()
        return tempdir.path

    @defer.inlineCallbacks
    def setUp(self):
        with patch.object(Path, "is_file", return_value=True):
            self.tmp_dir = self.createTempDir("temp")
            self.srvpass = SecretInPass("password", self.tmp_dir)
            yield self.srvpass.startService()

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.srvpass.stopService()

    def testCheckConfigSecretInPassService(self):
        self.assertEqual(self.srvpass.name, "SecretInPass")
        env = self.srvpass._env
        self.assertEquals(env["PASSWORD_STORE_GPG_OPTS"], "--passphrase password")
        self.assertEquals(env["PASSWORD_STORE_DIR"], self.tmp_dir)

    def testCheckConfigBinaryErrorSecretInPassService(self):
        expected_error_msg = "pass does not exist in PATH"
        with patch.object(Path, "is_file", return_value=False):
            with self.assertRaisesConfigError(expected_error_msg):
                self.srvpass.checkConfig("password", "temp")

    def testCheckConfigDirectoryErrorSecretInPassService(self):
        expected_error_msg = "directory temp2 does not exist"
        with self.assertRaisesConfigError(expected_error_msg):
            self.srvpass.checkConfig("password", "temp2")

    @defer.inlineCallbacks
    def testReconfigSecretInAFileService(self):
        with patch.object(Path, "is_file", return_value=True):
            otherdir = self.createTempDir("temp2")
            yield self.srvpass.reconfigService("password2", otherdir)
        self.assertEqual(self.srvpass.name, "SecretInPass")
        env = self.srvpass._env
        self.assertEquals(env["PASSWORD_STORE_GPG_OPTS"], "--passphrase password2")
        self.assertEquals(env["PASSWORD_STORE_DIR"], otherdir)


    def testGetSecretInPass(self):
        with patch("subprocess.run") as mock:
            type(mock.return_value).stdout = PropertyMock(return_value="value")
            value = self.srvpass.get("secret")
        self.assertEqual(value, "value")

    def testGetSecretInPassMultipleLinesUnix(self):
        with patch("subprocess.run") as mock:
            type(mock.return_value).stdout = PropertyMock(return_value="value1\nvalue2\nvalue3")
            value = self.srvpass.get("secret")
        self.assertEqual(value, "value1")

    def testGetSecretInPassMultipleLinesDarwin(self):
        with patch("subprocess.run") as mock:
            type(mock.return_value).stdout = PropertyMock(return_value="value1\rvalue2\rvalue3")
            value = self.srvpass.get("secret")
        self.assertEqual(value, "value1")

    def testGetSecretInPassMultipleLinesWindows(self):
        with patch("subprocess.run") as mock:
            type(mock.return_value).stdout = PropertyMock(return_value="value1\r\nvalue2\r\nvalue3")
            value = self.srvpass.get("secret")
        self.assertEqual(value, "value1")

    def testGetSecretInPassNotFound(self):
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "cmd")):
            value = self.srvpass.get("secret")
        self.assertEqual(value, None)
