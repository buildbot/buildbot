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
            config.error("vaultServer must be a string while it is %s" % (type(vaultServer,)))
        if not isinstance(vaultToken, str):
            config.error("vaultToken must be a string while it is %s" % (type(vaultToken,)))
        if apiVersion not in [1, 2]:
            config.error("apiVersion %s is not supported" % apiVersion)

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
        if self.apiVersion == 1:
            path = self.secretsmount + '/' + entry
        else:
            path = self.secretsmount + '/data/' + entry

        # note that the HTTP path contains v1 for both versions of the key-value
        # secret engine. Different versions of the key-value engine are
        # effectively separate secret engines in vault, with the same base HTTP
        # API, but with different paths within it.
        proj = yield self._http.get('/v1/{0}'.format(path))
        code = yield proj.code
        if code != 200:
            raise KeyError("The key %s does not exist in Vault provider: request"
                           " return code:%d." % (entry, code))
        json = yield proj.json()
        if self.apiVersion == 1:
            ret = json.get('data', {}).get('value')
        else:
            ret = json.get('data', {}).get('data', {}).get('value')
        return ret
