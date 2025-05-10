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

from parameterized import parameterized
from twisted.trial import unittest

from buildbot_worker import util


class remove_userpassword(unittest.TestCase):
    def assertUrl(self, real_url: str, expected_url: str) -> None:
        new_url = util.remove_userpassword(real_url)
        self.assertEqual(expected_url, new_url)

    def test_url_with_no_user_and_password(self) -> None:
        self.assertUrl('http://myurl.com/myrepo', 'http://myurl.com/myrepo')

    def test_url_with_user_and_password(self) -> None:
        self.assertUrl('http://myuser:mypass@myurl.com/myrepo', 'http://myurl.com/myrepo')

    def test_another_url_with_no_user_and_password(self) -> None:
        self.assertUrl('http://myurl2.com/myrepo2', 'http://myurl2.com/myrepo2')

    def test_another_url_with_user_and_password(self) -> None:
        self.assertUrl('http://myuser2:mypass2@myurl2.com/myrepo2', 'http://myurl2.com/myrepo2')

    def test_with_different_protocol_without_user_and_password(self) -> None:
        self.assertUrl('ssh://myurl3.com/myrepo3', 'ssh://myurl3.com/myrepo3')

    def test_with_different_protocol_with_user_and_password(self) -> None:
        self.assertUrl('ssh://myuser3:mypass3@myurl3.com/myrepo3', 'ssh://myurl3.com/myrepo3')

    def test_file_path(self) -> None:
        self.assertUrl('/home/me/repos/my-repo', '/home/me/repos/my-repo')

    def test_file_path_with_at_sign(self) -> None:
        self.assertUrl('/var/repos/speci@l', '/var/repos/speci@l')

    def test_win32file_path(self) -> None:
        self.assertUrl('c:\\repos\\my-repo', 'c:\\repos\\my-repo')


class TestObfuscated(unittest.TestCase):
    def testSimple(self) -> None:
        c = util.Obfuscated('real', '****')
        self.assertEqual(str(c), '****')
        self.assertEqual(repr(c), "'****'")

    def testObfuscatedCommand(self) -> None:
        cmd = ['echo', util.Obfuscated('password', '*******')]
        cmd_bytes = [b'echo', util.Obfuscated(b'password', b'*******')]
        cmd_unicode = ['echo', util.Obfuscated('password', 'привет')]

        self.assertEqual(['echo', 'password'], util.Obfuscated.get_real(cmd))
        self.assertEqual(['echo', '*******'], util.Obfuscated.get_fake(cmd))
        self.assertEqual([b'echo', b'password'], util.Obfuscated.get_real(cmd_bytes))
        self.assertEqual([b'echo', b'*******'], util.Obfuscated.get_fake(cmd_bytes))
        self.assertEqual(['echo', 'password'], util.Obfuscated.get_real(cmd_unicode))
        self.assertEqual(['echo', 'привет'], util.Obfuscated.get_fake(cmd_unicode))

    def testObfuscatedNonString(self) -> None:
        cmd = ['echo', 1]
        cmd_bytes = [b'echo', 2]
        cmd_unicode = ['привет', 3]
        self.assertEqual(['echo', '1'], util.Obfuscated.get_real(cmd))
        self.assertEqual([b'echo', '2'], util.Obfuscated.get_fake(cmd_bytes))
        self.assertEqual(['привет', '3'], util.Obfuscated.get_fake(cmd_unicode))

    def testObfuscatedNonList(self) -> None:
        cmd = 1
        self.assertEqual(1, util.Obfuscated.get_real(cmd))
        self.assertEqual(1, util.Obfuscated.get_fake(cmd))


class TestRewrap(unittest.TestCase):
    def test_main(self) -> None:
        tests = [
            ("", "", None),
            ("\n", "\n", None),
            ("\n  ", "\n", None),
            ("  \n", "\n", None),
            ("  \n  ", "\n", None),
            (
                """
                multiline
                with
                indent
                """,
                "\nmultiline with indent",
                None,
            ),
            (
                """\
                multiline
                with
                indent

                """,
                "multiline with indent\n",
                None,
            ),
            (
                """\
                 multiline
                 with
                 indent

                 """,
                "multiline with indent\n",
                None,
            ),
            (
                """\
                multiline
                with
                indent

                  and
                   formatting
                """,
                "multiline with indent\n  and\n   formatting\n",
                None,
            ),
            (
                """\
                multiline
                with
                indent
                and wrapping

                  and
                   formatting
                """,
                "multiline with\nindent and\nwrapping\n  and\n   formatting\n",
                15,
            ),
        ]

        for text, expected, width in tests:
            self.assertEqual(util.rewrap(text, width=width), expected)


class TestTwistedConnectionStringToWsUrl(unittest.TestCase):
    @parameterized.expand([
        ('empty', ''),
        ('tcp_no_host', 'tcp:'),
        ('tls_no_host', 'tls:'),
    ])
    def test_exception(self, name: str, description: str) -> None:
        with self.assertRaises(ValueError):
            util.twisted_connection_string_to_ws_url(description)

    @parameterized.expand([
        ('tcp_host', 'tcp:abc', 'ws://abc:80'),
        ('tcp_host_port', 'tcp:abc:123', 'ws://abc:123'),
        ('tcp_host_kw_port', 'tcp:host=abc:123', 'ws://abc:123'),
        ('tcp_host_port_kw', 'tcp:abc:port=123', 'ws://abc:123'),
        ('tcp_host_kw_port_kw', 'tcp:host=abc:port=123', 'ws://abc:123'),
        ('tls_host_port', 'tls:host=abc:port=123', 'ws://abc:123'),
    ])
    def test_converts(self, name: str, description: str, expected: str) -> None:
        ws_connection = util.twisted_connection_string_to_ws_url(description)
        self.assertEqual(ws_connection, expected)
