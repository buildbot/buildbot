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
from __future__ import absolute_import
from __future__ import print_function

from twisted.internet import defer

from buildbot.secrets.secret import SecretDetails
from buildbot.util import service


class SecretManager(service.BuildbotServiceManager):
    """
    Secret manager
    """
    name = 'secrets'
    config_attr = "secretsProviders"

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
                defer.returnValue(SecretDetails(source_name, secret, value))
