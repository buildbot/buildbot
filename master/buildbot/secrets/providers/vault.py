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

from __future__ import absolute_import
from __future__ import print_function

from twisted.internet import defer

from buildbot import config
from buildbot.secrets.providers.base import SecretProviderBase
from buildbot.util import httpclientservice


class HashiCorpVaultSecretProvider(SecretProviderBase):
    """
    basic provider where each secret is stored in Vault
    """

    name = 'SecretInVault'

    def checkConfig(self, vaultServer=None, vaultToken=None, secretsmount=None):
        if not isinstance(vaultServer, str):
            config.error("vaultServer must be a string while it is %s" % (type(vaultServer,)))
        if not isinstance(vaultToken, str):
            config.error("vaultToken must be a string while it is %s" % (type(vaultToken,)))

    @defer.inlineCallbacks
    def reconfigService(self, vaultServer=None, vaultToken=None, secretsmount=None):
        if secretsmount is None:
            self.secretsmount = "secret"
        else:
            self.secretsmount = secretsmount
        self.vaultServer = vaultServer
        self.vaultToken = vaultToken
        if vaultServer.endswith('/'):
            vaultServer = vaultServer[:-1]
        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, self.vaultServer, headers={'X-Vault-Token': self.vaultToken})

    @defer.inlineCallbacks
    def get(self, entry):
        """
        get the value from vault secret backend
        """
        path = self.secretsmount + '/' + entry
        proj = yield self._http.get('/v1/{0}'.format(path))
        code = yield proj.code
        if code != 200:
            raise KeyError("The key %s does not exist in Vault provider: request"
                           " return code:%d." % (entry, code))
        json = yield proj.json()
        defer.returnValue(json.get(u'data', {}).get('value'))
