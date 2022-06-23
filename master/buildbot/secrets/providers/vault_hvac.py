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
HVAC based providers
"""

from twisted.internet import defer
from twisted.internet import threads

from buildbot import config
from buildbot.secrets.providers.base import SecretProviderBase


class VaultAuthenticator:
    """
    base HVAC authenticator class
    """

    def authenticate(self, client):
        pass


class VaultAuthenticatorToken(VaultAuthenticator):
    """
    HVAC authenticator for static token
    """

    def __init__(self, token):
        self.token = token

    def authenticate(self, client):
        client.token = self.token


class VaultAuthenticatorApprole(VaultAuthenticator):
    """
    HVAC authenticator for Approle login method
    """

    def __init__(self, roleId, secretId):
        self.roleId = roleId
        self.secretId = secretId

    def authenticate(self, client):
        client.auth.approle.login(role_id=self.roleId, secret_id=self.secretId)


class HashiCorpVaultKvSecretProvider(SecretProviderBase):
    """
    Basic provider where each secret is stored in Vault KV secret engine.
    In case more secret engines are going to be supported, each engine should have it's own class.
    """

    name = 'SecretInVaultKv'

    def checkConfig(self, vault_server=None, authenticator=None, secrets_mount=None,
                    api_version=2, path_delimiter='|', path_escape='\\'):
        try:
            import hvac
            [hvac]
        except ImportError:  # pragma: no cover
            config.error(f"{self.__class__.__name__} needs the hvac package installed " +
                         "(pip install hvac)")

        if not isinstance(vault_server, str):
            config.error(f"vault_server must be a string while it is {type(vault_server)}")
        if not isinstance(path_delimiter, str) or len(path_delimiter) > 1:
            config.error("path_delimiter must be a single character")
        if not isinstance(path_escape, str) or len(path_escape) > 1:
            config.error("path_escape must be a single character")
        if not isinstance(authenticator, VaultAuthenticator):
            config.error("authenticator must be instance of VaultAuthenticator while it is "
                         f"{type(authenticator)}")

        if api_version not in [1, 2]:
            config.error(f"api_version {api_version} is not supported")

    def reconfigService(self, vault_server=None, authenticator=None, secrets_mount=None,
                        api_version=2, path_delimiter='|', path_escape='\\'):
        try:
            import hvac
        except ImportError:  # pragma: no cover
            config.error(f"{self.__class__.__name__} needs the hvac package installed " +
                         "(pip install hvac)")

        if secrets_mount is None:
            secrets_mount = "secret"
        self.secrets_mount = secrets_mount
        self.path_delimiter = path_delimiter
        self.path_escape = path_escape
        self.authenticator = authenticator
        self.api_version = api_version
        if vault_server.endswith('/'):  # pragma: no cover
            vault_server = vault_server[:-1]
        self.client = hvac.Client(vault_server)
        self.client.secrets.kv.default_kv_version = api_version
        return self

    def escaped_split(self, s):
        """
        parse and split string, respecting escape characters
        """
        ret = []
        current = []
        itr = iter(s)
        for ch in itr:
            if ch == self.path_escape:
                try:
                    # skip the next character; it has been escaped and remove
                    # escape character
                    current.append(next(itr))
                except StopIteration:
                    # escape character on end of the string is safest to ignore, as buildbot for
                    # each secret identifier tries all secret providers until value is found,
                    # meaning we may end up parsing identifiers for other secret providers, where
                    # our escape character may be valid on end of string
                    pass
            elif ch == self.path_delimiter:
                # split! (add current to the list and reset it)
                ret.append(''.join(current))
                current = []
            else:
                current.append(ch)
        ret.append(''.join(current))
        return ret

    def thd_hvac_wrap_read(self, path):
        if self.api_version == 1:
            return self.client.secrets.kv.v1.read_secret(path=path, mount_point=self.secrets_mount)
        else:
            return self.client.secrets.kv.v2.read_secret_version(path=path,
                                                                 mount_point=self.secrets_mount)

    def thd_hvac_get(self, path):
        """
        query secret from Vault and re-authenticate if not authenticated
        """

        if not self.client.is_authenticated():
            self.authenticator.authenticate(self.client)

        response = self.thd_hvac_wrap_read(path=path)

        return response

    @defer.inlineCallbacks
    def get(self, entry):
        """
        get the value from vault secret backend
        """

        parts = self.escaped_split(entry)
        if len(parts) == 1:
            raise KeyError("Vault secret specification must contain attribute name separated from "
                           f"path by '{self.path_delimiter}'")
        if len(parts) > 2:
            raise KeyError(f"Multiple separators ('{self.path_delimiter}') found in vault "
                           f"path '{entry}'. All occurences of '{self.path_delimiter}' in path or "
                           f"attribute name must be escaped using '{self.path_escape}'")

        name = parts[0]
        key = parts[1]

        response = yield threads.deferToThread(self.thd_hvac_get, path=name)

        # in KVv2 we have extra "data" dictionary, as vault provides metadata as well
        if self.api_version == 2:
            response = response['data']

        try:
            return response['data'][key]
        except KeyError as e:
            raise KeyError(
                f"The secret {entry} does not exist in Vault provider: {e}") from e
