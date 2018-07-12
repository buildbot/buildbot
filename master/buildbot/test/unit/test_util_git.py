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

from twisted.trial import unittest

from buildbot.util.git import GitMixin
from buildbot.util.git import getSshKnownHostsContents


class TestParseGitFeatures(GitMixin, unittest.TestCase):

    def test_no_output(self):
        self.setupGit()
        self.parseGitFeatures('')
        self.assertFalse(self.gitInstalled)
        self.assertFalse(self.supportsBranch)
        self.assertFalse(self.supportsSubmoduleForce)
        self.assertFalse(self.supportsSubmoduleCheckout)
        self.assertFalse(self.supportsSshPrivateKeyAsEnvOption)
        self.assertFalse(self.supportsSshPrivateKeyAsConfigOption)

    def test_git_noversion(self):
        self.setupGit()
        self.parseGitFeatures('git')
        self.assertFalse(self.gitInstalled)
        self.assertFalse(self.supportsBranch)
        self.assertFalse(self.supportsSubmoduleForce)
        self.assertFalse(self.supportsSubmoduleCheckout)
        self.assertFalse(self.supportsSshPrivateKeyAsEnvOption)
        self.assertFalse(self.supportsSshPrivateKeyAsConfigOption)

    def test_git_zero_version(self):
        self.setupGit()
        self.parseGitFeatures('git version 0.0.0')
        self.assertTrue(self.gitInstalled)
        self.assertFalse(self.supportsBranch)
        self.assertFalse(self.supportsSubmoduleForce)
        self.assertFalse(self.supportsSubmoduleCheckout)
        self.assertFalse(self.supportsSshPrivateKeyAsEnvOption)
        self.assertFalse(self.supportsSshPrivateKeyAsConfigOption)

    def test_git_2_10_0(self):
        self.setupGit()
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
