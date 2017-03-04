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

import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.secrets.providers.vault import SecretInVault
from buildbot.test.util.config import ConfigErrorsMixin


class FakeVaultClient(object):

    def __init__(self, fakeValues=None, vaultServer=None, vaultToken=None):
        self.vaultServer = vaultServer
        self.vaultToken = vaultToken
        self.fakeValues = fakeValues

    def get(self, key):
        return self.fakeValues[key]


class TestSecretInVault(ConfigErrorsMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self.srvcVault = SecretInVault(vaultServer="serveraddr",
                                       vaultToken="someToken")
        yield self.srvcVault.startService()

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.srvcVault.stopService()

    def checkGetVaultValue(self, fakeVaultValues, key, expectedValue):
        self.srvcVault.client.read = mock.Mock(return_value=fakeVaultValues)
        value = self.srvcVault.get(key)
        self.assertEqual(value, expectedValue)

    def testGetFile(self):
        fakeReadValue = {"data": {"value": "value1"}}
        self.checkGetVaultValue(fakeReadValue, "value", "value1")

    def testGetFileDataNotFound(self):
        fakeReadValue = {"data2": {"value": "value1"}}
        self.checkGetVaultValue(fakeReadValue, "value", None)

    def testGetFileValueNotFound(self):
        fakeReadValue = {"data": {"no_value": "value1"}}
        self.checkGetVaultValue(fakeReadValue, "value", None)

    def testCheckConfigSecretInVaultService(self):
        self.assertEqual(self.srvcVault.name, "SecretInVault")
        self.assertEqual(self.srvcVault.vaultServer, "serveraddr")
        self.assertEqual(self.srvcVault.token, "someToken")

    def testCheckConfigErrorSecretInVaultService(self):
        self.assertRaisesConfigError("vaultServer must be a string while it is",
                                     lambda: self.srvcVault.checkConfig())

    def testCheckConfigErrorSecretInVaultServiceWrongServerAddress(self):
        self.assertRaisesConfigError("vaultToken must be a string while it is",
                                     lambda: self.srvcVault.checkConfig(vaultServer="serveraddr",))

    @defer.inlineCallbacks
    def testReconfigSecretInVaultService(self):
        yield self.srvcVault.reconfigService(vaultServer="serveraddr",
                                             vaultToken="someToken")
        self.assertEqual(self.srvcVault.vaultServer, "serveraddr")
        self.assertEqual(self.srvcVault.token, "someToken")
