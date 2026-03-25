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

from pathlib import Path
from typing import TYPE_CHECKING
from unittest import mock

from twisted.internet import defer
from twisted.python.filepath import FilePath
from twisted.trial import unittest

from buildbot.secrets.providers.passwordstore import SecretInPass
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.runprocess import ExpectMasterShell
from buildbot.test.runprocess import MasterRunProcessMixin
from buildbot.test.util.config import ConfigErrorsMixin

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class TestSecretInPass(
    MasterRunProcessMixin, TestReactorMixin, ConfigErrorsMixin, unittest.TestCase
):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.setup_master_run_process()
        self.master = yield fakemaster.make_master(self)
        with mock.patch.object(Path, "is_file", return_value=True):
            self.tmp_dir = self.create_temp_dir("temp")
            self.srvpass = SecretInPass("password", self.tmp_dir)
            yield self.srvpass.setServiceParent(self.master)
            yield self.master.startService()
            self.addCleanup(self.srvpass.stopService)

    def create_temp_dir(self, dirname: str) -> str:
        tempdir = FilePath(self.mktemp())
        tempdir.createDirectory()
        return tempdir.path

    def test_check_config_secret_in_pass_service(self) -> None:
        self.assertEqual(self.srvpass.name, "SecretInPass")
        env = self.srvpass._env
        self.assertEqual(env["PASSWORD_STORE_GPG_OPTS"], "--passphrase password")
        self.assertEqual(env["PASSWORD_STORE_DIR"], self.tmp_dir)

    def test_check_config_binary_error_secret_in_pass_service(self) -> None:
        expected_error_msg = "pass does not exist in PATH"
        with mock.patch.object(Path, "is_file", return_value=False):
            with self.assertRaisesConfigError(expected_error_msg):
                self.srvpass.checkConfig("password", "temp")

    def test_check_config_directory_error_secret_in_pass_service(self) -> None:
        expected_error_msg = "directory temp2 does not exist"
        with mock.patch.object(Path, "is_file", return_value=True):
            with self.assertRaisesConfigError(expected_error_msg):
                self.srvpass.checkConfig("password", "temp2")

    @defer.inlineCallbacks
    def test_reconfig_secret_in_a_file_service(self) -> InlineCallbacksType[None]:
        with mock.patch.object(Path, "is_file", return_value=True):
            otherdir = self.create_temp_dir("temp2")
            yield self.srvpass.reconfigService("password2", otherdir)  # type: ignore[func-returns-value]
        self.assertEqual(self.srvpass.name, "SecretInPass")
        env = self.srvpass._env
        self.assertEqual(env["PASSWORD_STORE_GPG_OPTS"], "--passphrase password2")
        self.assertEqual(env["PASSWORD_STORE_DIR"], otherdir)

    @defer.inlineCallbacks
    def test_get_secret_in_pass(self) -> InlineCallbacksType[None]:
        self.expect_commands(ExpectMasterShell(['pass', 'secret']).stdout(b'value'))

        value = yield self.srvpass.get("secret")
        self.assertEqual(value, "value")

        self.assert_all_commands_ran()

    @defer.inlineCallbacks
    def test_get_secret_in_pass_multiple_lines_unix(self) -> InlineCallbacksType[None]:
        self.expect_commands(
            ExpectMasterShell(['pass', 'secret']).stdout(b"value1\nvalue2\nvalue3")
        )

        value = yield self.srvpass.get("secret")
        self.assertEqual(value, "value1")

        self.assert_all_commands_ran()

    @defer.inlineCallbacks
    def test_get_secret_in_pass_multiple_lines_darwin(self) -> InlineCallbacksType[None]:
        self.expect_commands(
            ExpectMasterShell(['pass', 'secret']).stdout(b"value1\rvalue2\rvalue3")
        )

        value = yield self.srvpass.get("secret")
        self.assertEqual(value, "value1")

        self.assert_all_commands_ran()

    @defer.inlineCallbacks
    def test_get_secret_in_pass_multiple_lines_windows(self) -> InlineCallbacksType[None]:
        self.expect_commands(
            ExpectMasterShell(['pass', 'secret']).stdout(b"value1\r\nvalue2\r\nvalue3")
        )

        value = yield self.srvpass.get("secret")
        self.assertEqual(value, "value1")

        self.assert_all_commands_ran()

    @defer.inlineCallbacks
    def test_get_secret_in_pass_not_found(self) -> InlineCallbacksType[None]:
        self.expect_commands(ExpectMasterShell(['pass', 'secret']).stderr(b"Not found"))

        value = yield self.srvpass.get("secret")
        self.assertEqual(value, None)
