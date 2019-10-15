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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.secrets.providers.vault import HashiCorpVaultSecretProvider
from buildbot.test.fake import fakemaster
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.test.util.misc import TestReactorMixin


class TestSecretInVaultHttpFakeBase(ConfigErrorsMixin, TestReactorMixin,
                                    unittest.TestCase):

    def setUp(self, version):
        self.setUpTestReactor()
        self.srvcVault = HashiCorpVaultSecretProvider(vaultServer="http://vaultServer",
                                                      vaultToken="someToken",
                                                      apiVersion=version)
        self.master = fakemaster.make_master(self, wantData=True)
        self._http = self.successResultOf(
            fakehttpclientservice.HTTPClientService.getFakeService(
                self.master, self, 'http://vaultServer', headers={'X-Vault-Token': "someToken"}))
        self.srvcVault.setServiceParent(self.master)
        self.successResultOf(self.master.startService())

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.srvcVault.stopService()


class TestSecretInVaultV1(TestSecretInVaultHttpFakeBase):

    def setUp(self):
        super().setUp(version=1)

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
        with self.assertRaisesConfigError(
                "vaultServer must be a string while it is"):
            self.srvcVault.checkConfig()

    def testCheckConfigErrorSecretInVaultServiceWrongServerAddress(self):
        with self.assertRaisesConfigError(
                "vaultToken must be a string while it is"):
            self.srvcVault.checkConfig(vaultServer="serveraddr")

    def test_check_config_error_apiVersion_unsupported(self):
        with self.assertRaisesConfigError(
                "apiVersion 0 is not supported"):
            self.srvcVault.checkConfig(vaultServer="serveraddr",
                                       vaultToken="vaultToken",
                                       apiVersion=0)

    @defer.inlineCallbacks
    def testReconfigSecretInVaultService(self):
        self._http = self.successResultOf(
            fakehttpclientservice.HTTPClientService.getFakeService(
                self.master, self, 'serveraddr', headers={'X-Vault-Token': "someToken"}))
        yield self.srvcVault.reconfigService(vaultServer="serveraddr",
                                             vaultToken="someToken")
        self.assertEqual(self.srvcVault.vaultServer, "serveraddr")
        self.assertEqual(self.srvcVault.vaultToken, "someToken")


class TestSecretInVaultV2(TestSecretInVaultHttpFakeBase):

    def setUp(self):
        super().setUp(version=2)

    @defer.inlineCallbacks
    def testGetValue(self):
        self._http.expect(method='get', ep='/v1/secret/data/value', params=None,
                          data=None, json=None, code=200,
                          content_json={"data": {"data": {"value": "value1"}}})
        value = yield self.srvcVault.get("value")
        self.assertEqual(value, "value1")

    @defer.inlineCallbacks
    def testGetValueNotFound(self):
        self._http.expect(method='get', ep='/v1/secret/data/value', params=None,
                          data=None, json=None, code=200,
                          content_json={"data": {"data": {"valueNotFound": "value1"}}})
        value = yield self.srvcVault.get("value")
        self.assertEqual(value, None)

    @defer.inlineCallbacks
    def testGetError(self):
        self._http.expect(method='get', ep='/v1/secret/data/valueNotFound', params=None,
                          data=None, json=None, code=404,
                          content_json={"data": {"data": {"valueNotFound": "value1"}}})
        yield self.assertFailure(self.srvcVault.get("valueNotFound"), KeyError)
