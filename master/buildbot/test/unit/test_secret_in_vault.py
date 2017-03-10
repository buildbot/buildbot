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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.secrets.providers.vault import HashiCorpVaultSecretProvider
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.fake import fakemaster
from buildbot.test.util.config import ConfigErrorsMixin


class TestSecretInVaultHttpFake(ConfigErrorsMixin, unittest.TestCase):

    def setUp(self):
        self.srvcVault = HashiCorpVaultSecretProvider(vaultServer="http://vaultServer",
                                                      vaultToken="someToken")
        self.master = fakemaster.make_master(testcase=self, wantData=True)
        self._http = self.successResultOf(
            fakehttpclientservice.HTTPClientService.getFakeService(
                self.master, self, 'http://vaultServer', headers={'X-Vault-Token': "someToken"}))
        self.srvcVault.setServiceParent(self.master)
        self.successResultOf(self.master.startService())

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.srvcVault.stopService()

    @defer.inlineCallbacks
    def testGetValue(self):
        self._http.expect(method='get', ep='/v1/secret/value', params=None,
                          data=None, json=None, code=200,
                          content_json={"data": {"value": "value1"}})
        value = yield self.srvcVault.get("value")
        self.assertEqual(value, "value1")

    @defer.inlineCallbacks
    def testGetValueNotFound(self):
        self._http.expect(method='get', ep='/v1/secret/value', params=None,
                          data=None, json=None, code=200,
                          content_json={"data": {"valueNotFound": "value1"}})
        value = yield self.srvcVault.get("value")
        self.assertEqual(value, None)

    @defer.inlineCallbacks
    def testGetError(self):
        self._http.expect(method='get', ep='/v1/secret/valueNotFound', params=None,
                          data=None, json=None, code=404,
                          content_json={"data": {"valueNotFound": "value1"}})
        yield self.assertFailure(self.srvcVault.get("valueNotFound"), KeyError)

    def testCheckConfigSecretInVaultService(self):
        self.assertEqual(self.srvcVault.name, "SecretInVault")
        self.assertEqual(self.srvcVault.vaultServer, "http://vaultServer")
        self.assertEqual(self.srvcVault.vaultToken, "someToken")

    def testCheckConfigErrorSecretInVaultService(self):
        self.assertRaisesConfigError("vaultServer must be a string while it is",
                                     lambda: self.srvcVault.checkConfig())

    def testCheckConfigErrorSecretInVaultServiceWrongServerAddress(self):
        self.assertRaisesConfigError("vaultToken must be a string while it is",
                                     lambda: self.srvcVault.checkConfig(vaultServer="serveraddr",))

    @defer.inlineCallbacks
    def testReconfigSecretInVaultService(self):
        self._http = self.successResultOf(
            fakehttpclientservice.HTTPClientService.getFakeService(
                self.master, self, 'serveraddr', headers={'X-Vault-Token': "someToken"}))
        yield self.srvcVault.reconfigService(vaultServer="serveraddr",
                                             vaultToken="someToken")
        self.assertEqual(self.srvcVault.vaultServer, "serveraddr")
        self.assertEqual(self.srvcVault.vaultToken, "someToken")
