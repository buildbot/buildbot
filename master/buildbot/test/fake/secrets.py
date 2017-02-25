from __future__ import absolute_import
from __future__ import print_function

from buildbot.secrets.providers.base import SecretProviderBase


class FakeSecretStorage(SecretProviderBase):

    def __init__(self, allsecretsInADict):
        self.allsecrets = allsecretsInADict

    def get(self, key):
        if key in self.allsecrets:
            return self.allsecrets[key]
        else:
            return None
