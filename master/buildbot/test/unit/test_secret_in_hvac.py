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

from unittest.mock import patch

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.secrets.providers.vault_hvac import HashiCorpVaultKvSecretProvider
from buildbot.secrets.providers.vault_hvac import VaultAuthenticatorApprole
from buildbot.secrets.providers.vault_hvac import VaultAuthenticatorToken
from buildbot.test.util import interfaces

try:
    import hvac
    assert hvac
except ImportError:
    hvac = None


class FakeHvacApprole:
    def login(self, role_id, secret_id):
        self.role_id = role_id
        self.secret_id = secret_id


class FakeHvacAuth:
    approle = FakeHvacApprole()


class FakeHvacKvV1:
    token = None

    def read_secret(self, path, mount_point):
        if self.token is None:
            raise hvac.exceptions.Unauthorized
        if path == "wrong/path":
            raise hvac.exceptions.InvalidPath(message="Fake InvalidPath exception")
        return {'data': {'key': "value"}}


class FakeHvacKvV2:
    token = None

    def read_secret_version(self, path, mount_point):
        if self.token is None:
            raise hvac.exceptions.Unauthorized(message="Fake Unauthorized exception")
        if path == "wrong/path":
            raise hvac.exceptions.InvalidPath(message="Fake InvalidPath exception")
        return {'data': {'data': {'key': "value"}}}


class FakeHvacKv:
    default_kv_version = 2
    v1 = FakeHvacKvV1()
    v2 = FakeHvacKvV2()


class FakeHvacSecrets:
    kv = FakeHvacKv()


class FakeHvacClient:
    auth = FakeHvacAuth()
    secrets = FakeHvacSecrets()

    _token = None

    @property
    def token(self):
        return self._token

    @token.setter
    def token(self, new_token):
        self._token = new_token
        self.secrets.kv.v1.token = new_token
        self.secrets.kv.v2.token = new_token


def mock_vault(*args, **kwargs):
    client = FakeHvacClient()
    client.token = "mockToken"
    return client


class TestSecretInVaultAuthenticator(interfaces.InterfaceTests):

    def test_authenticate(self):
        raise NotImplementedError


class TestSecretInVaultAuthenticatorToken(unittest.TestCase, TestSecretInVaultAuthenticator):

    def setUp(self):
        if hvac is None:
            raise unittest.SkipTest(
                "Need to install hvac to test VaultAuthenticatorToken")

    def test_authenticate(self):
        token = "mockToken"
        authenticator = VaultAuthenticatorToken(token)
        client = hvac.Client()
        authenticator.authenticate(client)
        self.assertEqual(client.token, token)


class TestSecretInVaultAuthenticatorApprole(unittest.TestCase, TestSecretInVaultAuthenticator):

    def test_authenticate(self):
        authenticator = VaultAuthenticatorApprole("testRole", "testSecret")
        client = FakeHvacClient()
        authenticator.authenticate(client)
        self.assertEqual(client.auth.approle.secret_id, "testSecret")


class TestSecretInHashiCorpVaultKvSecretProvider(unittest.TestCase):

    def setUp(self):
        if hvac is None:
            raise unittest.SkipTest(
                "Need to install hvac to test HashiCorpVaultKvSecretProvider")
        param = dict(vault_server="", authenticator=VaultAuthenticatorToken("mockToken"),
                     path_delimiter='|', path_escape='\\', api_version=2)
        self.provider = HashiCorpVaultKvSecretProvider(**param)
        self.provider.reconfigService(**param)
        self.provider.client = FakeHvacClient()
        self.provider.client.secrets.kv.default_kv_version = param['api_version']
        self.provider.client.token = "mockToken"

    def test_escaped_split(self):
        parts = self.provider.escaped_split("a/b\\|c/d|e/f\\|g/h")
        self.assertEqual(parts, ["a/b|c/d", "e/f|g/h"])

    def test_thd_hvac_wrap_read_v1(self):
        self.provider.api_version = 1
        self.provider.client.token = "mockToken"
        value = self.provider.thd_hvac_wrap_read("some/path")
        self.assertEqual(value['data']['key'], "value")

    def test_thd_hvac_wrap_read_v2(self):
        self.provider.client.token = "mockToken"
        value = self.provider.thd_hvac_wrap_read("some/path")
        self.assertEqual(value['data']['data']['key'], "value")

    # for some reason, errors regarding generator function were thrown
    @patch("hvac.Client", side_effect=mock_vault)
    def test_thd_hvac_wrap_read_unauthorized(self, mock_vault):
        self.provider.client.token = None
        yield self.assertFailure(self.provider.thd_hvac_wrap_read("some/path"),
                                 hvac.exceptions.Unauthorized)

    def test_thd_hvac_get_reauthorize(self):
        """
        When token is None, provider gets unauthorized exception and is forced to re-authenticate
        """
        self.provider.client.token = None
        value = self.provider.thd_hvac_get("some/path")
        self.assertEqual(value['data']['data']['key'], "value")

    @defer.inlineCallbacks
    def test_get_v1(self):
        self.provider.api_version = 1
        self.provider.client.token = "mockToken"
        value = yield self.provider.get("some/path|key")
        self.assertEqual(value, "value")

    @defer.inlineCallbacks
    def test_get_v2(self):
        self.provider.client.token = "mockToken"
        value = yield self.provider.get("some/path|key")
        self.assertEqual(value, "value")

    @defer.inlineCallbacks
    def test_get_fail_no_key(self):
        self.provider.client.token = "mockToken"
        with self.assertRaises(KeyError):
            yield self.provider.get("some/path")

    @defer.inlineCallbacks
    def test_get_fail_wrong_key(self):
        self.provider.client.token = "mockToken"
        with self.assertRaises(KeyError):
            yield self.provider.get("some/path|wrong_key")

    @defer.inlineCallbacks
    def test_get_fail_multiple_separators(self):
        self.provider.client.token = "mockToken"
        with self.assertRaises(KeyError):
            yield self.provider.get("some/path|unescaped|key")
