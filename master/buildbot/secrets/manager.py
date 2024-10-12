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
manage providers and handle secrets
"""

from __future__ import annotations

from twisted.internet import defer

from buildbot.secrets.providers.base import SecretProviderBase
from buildbot.secrets.secret import SecretDetails
from buildbot.util import service


class SecretManager(service.BuildbotServiceManager):
    """
    Secret manager
    """

    name: str | None = 'secrets'  # type: ignore[assignment]
    config_attr = "secretsProviders"

    @defer.inlineCallbacks
    def setup(self):
        configuredProviders = self.get_service_config(self.master.config)

        for child in configuredProviders.values():
            assert isinstance(child, SecretProviderBase)
            yield child.setServiceParent(self)
            yield child.configureService()

    @defer.inlineCallbacks
    def get(self, secret, *args, **kwargs):
        """
        get secrets from the provider defined in the secret using args and
        kwargs
        @secrets: secrets keys
        @type: string
        @return type: SecretDetails
        """
        for provider in self.services:
            value = yield provider.get(secret)
            source_name = provider.__class__.__name__
            if value is not None:
                return SecretDetails(source_name, secret, value)
        return None
