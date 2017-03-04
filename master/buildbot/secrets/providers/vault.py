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

import hvac

from buildbot import config
from buildbot.secrets.providers.base import SecretProviderBase


class SecretInVault(SecretProviderBase):
    """
    basic provider where each secret is stored in Vault
    """
    name = 'SecretInVault'

    def checkConfig(self, vaultServer=None, vaultToken=None):
        if not isinstance(vaultServer, str):
            config.error("vaultServer must be a string while it is %s" % (type(vaultServer,)))
        if not isinstance(vaultToken, str):
            config.error("vaultToken must be a string while it is %s" % (type(vaultToken,)))
        self.vaultServer = vaultServer
        self.token = vaultToken
        self.client = hvac.Client(url=vaultServer, token=vaultToken)

    def reconfigService(self, vaultServer=None, vaultToken=None):
        self.vaultServer = vaultServer
        self.token = vaultToken
        self.client = hvac.Client(url=vaultServer, token=vaultToken)

    def get(self, entry):
        """
        get the value from vault secret backend
        """
        secret = self.client.read('secret/' + entry)
        if 'data' not in secret.keys():
            return None
        if "value" not in secret["data"].keys():
            return None
        return secret["data"]["value"]
