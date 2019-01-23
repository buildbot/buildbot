
from buildbot.secrets.providers.base import SecretProviderBase


class FakeSecretStorage(SecretProviderBase):

    name = "SecretsInFake"

    def reconfigService(self, secretdict=None):
        if secretdict is None:
            secretdict = {}
        self.allsecrets = secretdict

    def get(self, key):
        if key in self.allsecrets:
            return self.allsecrets[key]
        return None
