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

from parameterized import parameterized

from twisted.trial import unittest

from buildbot.test.util import config
from buildbot.util.git import GitMixin
from buildbot.util.git import escapeShellArgIfNeeded
from buildbot.util.git import getSshKnownHostsContents


class TestEscapeShellArgIfNeeded(unittest.TestCase):

    def assert_escapes(self, arg):
        escaped = '"{}"'.format(arg)
        self.assertEqual(escapeShellArgIfNeeded(arg), escaped)

    def assert_does_not_escape(self, arg):
        self.assertEqual(escapeShellArgIfNeeded(arg), arg)

    def test_empty(self):
        self.assert_escapes('')

    def test_spaces(self):
        self.assert_escapes(' ')
        self.assert_escapes('a ')
        self.assert_escapes(' a')
        self.assert_escapes('a b')

    def test_special(self):
        self.assert_escapes('a=b')
        self.assert_escapes('a%b')
        self.assert_escapes('a(b')
        self.assert_escapes('a[b')

    def test_no_escape(self):
        self.assert_does_not_escape('abc')
        self.assert_does_not_escape('a_b')
        self.assert_does_not_escape('-opt')
        self.assert_does_not_escape('--opt')


class TestSetUpGit(GitMixin, unittest.TestCase, config.ConfigErrorsMixin):

    @parameterized.expand([
        ('no_keys', None, None, None, None),
        ('only_private_key', 'key', None, None, None),
        ('private_key_host_key', 'key', 'host', None, None),
        ('private_key_known_hosts', 'key', None, 'hosts', None),
        ('no_private_key_host_key', None, 'host', None,
         'sshPrivateKey must be provided in order use sshHostKey'),
        ('no_private_key_known_hosts', None, None, 'hosts',
         'sshPrivateKey must be provided in order use sshKnownHosts'),
        ('both_host_key_known_hosts', 'key', 'host', 'hosts',
         'only one of sshPrivateKey and sshHostKey can be provided'),
    ])
    def test_config(self, name, private_key, host_key, known_hosts, config_error):
        self.sshPrivateKey = private_key
        self.sshHostKey = host_key
        self.sshKnownHosts = known_hosts
        if config_error is None:
            self.setupGit()
        else:
            with self.assertRaisesConfigError(config_error):
                self.setupGit()


class TestParseGitFeatures(GitMixin, unittest.TestCase):

    def setUp(self):
        self.sshPrivateKey = None
        self.sshHostKey = None
        self.sshKnownHosts = None
        self.setupGit()

    def test_no_output(self):
        self.parseGitFeatures('')
        self.assertFalse(self.gitInstalled)
        self.assertFalse(self.supportsBranch)
        self.assertFalse(self.supportsSubmoduleForce)
        self.assertFalse(self.supportsSubmoduleCheckout)
        self.assertFalse(self.supportsSshPrivateKeyAsEnvOption)
        self.assertFalse(self.supportsSshPrivateKeyAsConfigOption)

    def test_git_noversion(self):
        self.parseGitFeatures('git')
        self.assertFalse(self.gitInstalled)
        self.assertFalse(self.supportsBranch)
        self.assertFalse(self.supportsSubmoduleForce)
        self.assertFalse(self.supportsSubmoduleCheckout)
        self.assertFalse(self.supportsSshPrivateKeyAsEnvOption)
        self.assertFalse(self.supportsSshPrivateKeyAsConfigOption)

    def test_git_zero_version(self):
        self.parseGitFeatures('git version 0.0.0')
        self.assertTrue(self.gitInstalled)
        self.assertFalse(self.supportsBranch)
        self.assertFalse(self.supportsSubmoduleForce)
        self.assertFalse(self.supportsSubmoduleCheckout)
        self.assertFalse(self.supportsSshPrivateKeyAsEnvOption)
        self.assertFalse(self.supportsSshPrivateKeyAsConfigOption)

    def test_git_2_10_0(self):
        self.parseGitFeatures('git version 2.10.0')
        self.assertTrue(self.gitInstalled)
        self.assertTrue(self.supportsBranch)
        self.assertTrue(self.supportsSubmoduleForce)
        self.assertTrue(self.supportsSubmoduleCheckout)
        self.assertTrue(self.supportsSshPrivateKeyAsEnvOption)
        self.assertTrue(self.supportsSshPrivateKeyAsConfigOption)


class TestAdjustCommandParamsForSshPrivateKey(GitMixin, unittest.TestCase):
    def test_throws_when_wrapper_not_given(self):
        self.gitInstalled = True

        command = []
        env = {}
        with self.assertRaises(Exception):
            self.adjustCommandParamsForSshPrivateKey(command, env,
                                                     'path/to/key')


class TestGetSshKnownHostsContents(unittest.TestCase):
    def test(self):
        key = 'ssh-rsa AAAA<...>WsHQ=='

        expected = '* ssh-rsa AAAA<...>WsHQ=='
        self.assertEqual(expected, getSshKnownHostsContents(key))
