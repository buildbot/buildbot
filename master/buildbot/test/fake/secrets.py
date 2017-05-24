from __future__ import absolute_import
from __future__ import print_function

from buildbot.secrets.providers.base import SecretProviderBase


class FakeSecretStorage(SecretProviderBase):

    name = "SecretsInFake"

    def reconfigService(self, secretdict={}):
        self.allsecrets = secretdict

    def get(self, key):
        if key in self.allsecrets:
            return self.allsecrets[key]
        return None
