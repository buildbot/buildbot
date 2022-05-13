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

from parameterized import parameterized

from twisted.trial import unittest

from buildbot.test.util.decorators import skipUnlessPlatformIs
from buildbot.util import path_expand_user


class TestExpanduser(unittest.TestCase):
    @parameterized.expand(
        [
            ("no_tilde", "test_path", {}, "test_path"),
            ("no_env_tilde", "~test_path", {}, "~test_path"),
            (
                "homedrive_tilde",
                "~test_path",
                {"HOMEDRIVE": "C:\\", "HOMEPATH": "Users\\eric", "USERNAME": "eric"},
                "C:\\Users\\test_path",
            ),
            (
                "homedrive_tilde_only",
                "~",
                {"HOMEDRIVE": "C:\\", "HOMEPATH": "Users\\eric", "USERNAME": "eric"},
                "C:\\Users\\eric",
            ),
            (
                "no_homedrive_tilde",
                "~test_path",
                {"HOMEPATH": "Users\\eric", "USERNAME": "eric"},
                "Users\\test_path",
            ),
            (
                "no_homedrive_tilde_only",
                "~",
                {"HOMEPATH": "Users\\eric", "USERNAME": "eric"},
                "Users\\eric",
            ),
            (
                "userprofile_tilde",
                "~test_path",
                {"USERPROFILE": "C:\\Users\\eric", "USERNAME": "eric"},
                "C:\\Users\\test_path",
            ),
            (
                "userprofile_tilde_only",
                "~",
                {"USERPROFILE": "C:\\Users\\eric", "USERNAME": "eric"},
                "C:\\Users\\eric",
            ),
            (
                "userprofile_backslash",
                "~test_path\\foo\\bar",
                {"USERPROFILE": "C:\\Users\\eric", "USERNAME": "eric"},
                "C:\\Users\\test_path\\foo\\bar",
            ),
            (
                "userprofile_slash",
                "~test_path/foo/bar",
                {"USERPROFILE": "C:\\Users\\eric", "USERNAME": "eric"},
                "C:\\Users\\test_path/foo/bar",
            ),
            (
                "userprofile_not_separate_tilde_backslash",
                "~\\foo\\bar",
                {"USERPROFILE": "C:\\Users\\eric", "USERNAME": "eric"},
                "C:\\Users\\eric\\foo\\bar",
            ),
            (
                "userprofile_separate_tilde_slash",
                "~/foo/bar",
                {"USERPROFILE": "C:\\Users\\eric", "USERNAME": "eric"},
                "C:\\Users\\eric/foo/bar",
            ),
            # bpo-36264: ignore `HOME` when set on windows
            (
                "ignore_home_on_windows",
                "~test_path",
                {"HOME": "F:\\", "USERPROFILE": "C:\\Users\\eric", "USERNAME": "eric"},
                "C:\\Users\\test_path",
            ),
            (
                "ignore_home_on_windows_tilde_only",
                "~",
                {"HOME": "F:\\", "USERPROFILE": "C:\\Users\\eric", "USERNAME": "eric"},
                "C:\\Users\\eric",
            ),
            # bpo-39899: don't guess another user's home directory if
            # `%USERNAME% != basename(%USERPROFILE%)`
            (
                "dont_guess_home_dir",
                "~test_path",
                {"USERPROFILE": "C:\\Users\\eric", "USERNAME": "idle"},
                "~test_path",
            ),
            (
                "dont_guess_home_dir_tilde_only",
                "~",
                {"USERPROFILE": "C:\\Users\\eric", "USERNAME": "idle"},
                "C:\\Users\\eric",
            ),
        ]
    )
    def test_nt(self, name, path, env, result):
        self.assertEqual(path_expand_user.nt_expanduser(path, env), result)

    @parameterized.expand(
        [
            ("no_home", "test_path", {}, "test_path"),
            ("home_tilde_only", "~", {"HOME": "/home/victor"}, "/home/victor"),
            (
                "home_tilde_only_trailing_slash",
                "~",
                {"HOME": "/home/victor/"},
                "/home/victor",
            ),
            ("home_slash_tilde_only", "~", {"HOME": "/"}, "/"),
            ("home_slash_tilde_slash", "~/", {"HOME": "/"}, "/"),
            ("home_slash_tilde_slash_name", "~/test_path", {"HOME": "/"}, "/test_path"),
            ("home_empty_tilde_only", "~", {"HOME": ""}, "/"),
            ("home_empty_tilde_slash", "~/", {"HOME": ""}, "/"),
            ("home_empty_tilde_slash_name", "~/test_path", {"HOME": ""}, "/test_path"),
            ("home_double_slash_tilde_only", "~", {"HOME": "//"}, "/"),
            ("home_double_slash_tilde_slash", "~/", {"HOME": "//"}, "/"),
            (
                "home_double_slash_tilde_slash_name",
                "~/test_path",
                {"HOME": "//"},
                "/test_path",
            ),
            ("home_triple_slash_tilde_only", "~", {"HOME": "///"}, "/"),
            ("home_triple_slash_tilde_slash", "~/", {"HOME": "///"}, "/"),
            (
                "home_triple_slash_tilde_slash_name",
                "~/test_path",
                {"HOME": "///"},
                "/test_path",
            ),
        ]
    )
    def test_posix(self, name, path, env, result):
        self.assertEqual(path_expand_user.posix_expanduser(path, env), result)

    @skipUnlessPlatformIs("posix")
    def test_posix_no_home(self):
        import pwd

        home = pwd.getpwuid(os.getuid()).pw_dir
        # $HOME can end with a trailing /, so strip it (see cpython #17809)
        home = home.rstrip("/") or "/"
        self.assertEqual(path_expand_user.posix_expanduser("~", {}), home)
