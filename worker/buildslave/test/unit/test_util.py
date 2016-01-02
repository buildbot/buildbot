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

from twisted.trial import unittest

from buildslave import util


class remove_userpassword(unittest.TestCase):

    def assertUrl(self, real_url, expected_url):
        new_url = util.remove_userpassword(real_url)
        self.assertEqual(expected_url, new_url)

    def test_url_with_no_user_and_password(self):
        self.assertUrl('http://myurl.com/myrepo', 'http://myurl.com/myrepo')

    def test_url_with_user_and_password(self):
        self.assertUrl('http://myuser:mypass@myurl.com/myrepo', 'http://myurl.com/myrepo')

    def test_another_url_with_no_user_and_password(self):
        self.assertUrl('http://myurl2.com/myrepo2', 'http://myurl2.com/myrepo2')

    def test_another_url_with_user_and_password(self):
        self.assertUrl('http://myuser2:mypass2@myurl2.com/myrepo2', 'http://myurl2.com/myrepo2')

    def test_with_different_protocol_without_user_and_password(self):
        self.assertUrl('ssh://myurl3.com/myrepo3', 'ssh://myurl3.com/myrepo3')

    def test_with_different_protocol_with_user_and_password(self):
        self.assertUrl('ssh://myuser3:mypass3@myurl3.com/myrepo3', 'ssh://myurl3.com/myrepo3')

    def test_file_path(self):
        self.assertUrl('/home/me/repos/my-repo', '/home/me/repos/my-repo')

    def test_file_path_with_at_sign(self):
        self.assertUrl('/var/repos/speci@l', '/var/repos/speci@l')

    def test_win32file_path(self):
        self.assertUrl('c:\\repos\\my-repo', 'c:\\repos\\my-repo')


class TestObfuscated(unittest.TestCase):

    def testSimple(self):
        c = util.Obfuscated('real', '****')
        self.failUnlessEqual(str(c), '****')
        self.failUnlessEqual(repr(c), "'****'")

    def testObfuscatedCommand(self):
        cmd = ['echo', util.Obfuscated('password', '*******')]

        self.failUnlessEqual(['echo', 'password'], util.Obfuscated.get_real(cmd))
        self.failUnlessEqual(['echo', '*******'], util.Obfuscated.get_fake(cmd))

    def testObfuscatedNonString(self):
        cmd = ['echo', 1]
        self.failUnlessEqual(['echo', '1'], util.Obfuscated.get_real(cmd))
        self.failUnlessEqual(['echo', '1'], util.Obfuscated.get_fake(cmd))

    def testObfuscatedNonList(self):
        cmd = 1
        self.failUnlessEqual(1, util.Obfuscated.get_real(cmd))
        self.failUnlessEqual(1, util.Obfuscated.get_fake(cmd))
