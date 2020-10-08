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
"""
vault based providers
"""


from twisted.internet import defer

from buildbot import config
from buildbot.secrets.providers.base import SecretProviderBase
from buildbot.util import httpclientservice


class HashiCorpVaultSecretProvider(SecretProviderBase):
    """
    basic provider where each secret is stored in Vault KV secret engine
    """

    name = 'SecretInVault'

    def checkConfig(self, vaultServer=None, vaultToken=None, secretsmount=None,
                    apiVersion=1):
        if not isinstance(vaultServer, str):
            config.error("vaultServer must be a string while it is {}".format(type(vaultServer)))
        if not isinstance(vaultToken, str):
            config.error("vaultToken must be a string while it is {}".format(type(vaultToken)))
        if apiVersion not in [1, 2]:
            config.error("apiVersion {} is not supported".format(apiVersion))

    @defer.inlineCallbacks
    def reconfigService(self, vaultServer=None, vaultToken=None, secretsmount=None,
                        apiVersion=1):
        if secretsmount is None:
            self.secretsmount = "secret"
        else:
            self.secretsmount = secretsmount
        self.vaultServer = vaultServer
        self.vaultToken = vaultToken
        self.apiVersion = apiVersion
        if vaultServer.endswith('/'):
            vaultServer = vaultServer[:-1]
        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, self.vaultServer, headers={'X-Vault-Token': self.vaultToken})

    @defer.inlineCallbacks
    def get(self, entry):
        """
        get the value from vault secret backend
        """
        parts = entry.split('/', maxsplit=1)
        name = parts[0]
        if len(parts) > 1:
            key = parts[1]
        else:
            key = 'value'

        if self.apiVersion == 1:
            path = self.secretsmount + '/' + name
        else:
            path = self.secretsmount + '/data/' + name

        # note that the HTTP path contains v1 for both versions of the key-value
        # secret engine. Different versions of the key-value engine are
        # effectively separate secret engines in vault, with the same base HTTP
        # API, but with different paths within it.
        proj = yield self._http.get('/v1/{0}'.format(path))
        code = yield proj.code
        if code != 200:
            raise KeyError(("The secret {} does not exist in Vault provider: request"
                           " return code: {}.").format(entry, code))
        json = yield proj.json()
        if self.apiVersion == 1:
            secrets = json.get('data', {})
        else:
            secrets = json.get('data', {}).get('data', {})
        try:
            return secrets[key]
        except KeyError as e:
            raise KeyError(
                "The secret {} does not exist in Vault provider: {}".format(entry, e)) from e
