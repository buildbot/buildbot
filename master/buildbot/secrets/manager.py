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
from future.utils import itervalues
from future.utils import text_type

from buildbot.secrets.secret import ActualSecret
from buildbot.secrets.secret import Secret
from buildbot.util.service import BuildbotService


class SecretManager(BuildbotService):
    """
    Secret manager
    """
    name = 'secrets'

    config_attr = 'providers'

    def getConfigDict(self):
        return {
            'name': self.name,
            'providers': [
                p.getConfigDict() for p in itervalues(self.namedServices)
            ]
        }

    def get_provider(self, provider_name):
        """
        get provider by its name
        """
        provider = self.namedServices.get(provider_name, None)

        assert provider, 'unknown secret provider: {}'.format(provider_name)

    def get(self, secret, *args, **kwargs):
        """
        get a secret from the provider defined in the secret using args and
        kwargs
        """
        allowed_types = (text_type, Secret)
        assert isinstance(secret, allowed_types), \
            'secret must be an instance of {!r}'.format(allowed_types)

        if isinstance(secret, text_type):
            # backward compatibility, produce a warning?
            value, props = secret, None
            source_name = 'Plain text secret'
        else:
            provider = self.get_provider(secret.provider_name)
            value, props = provider.get(*args, **kwargs)
            source_name = repr(provider)

        return ActualSecret(
            '{}: args={!r}, kwargs={!r}'.format(source_name, args, kwargs),
            value, props=props)
