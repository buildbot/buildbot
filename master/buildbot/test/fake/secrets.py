from __future__ import annotations

from buildbot.secrets.providers.base import SecretProviderBase


class FakeSecretStorage(SecretProviderBase):
    name: str | None = "SecretsInFake"  # type: ignore[assignment]

    def __init__(self, *args, secretdict: dict | None = None, **kwargs):
        super().__init__(*args, **kwargs, secretdict=secretdict)
        self._setup_secrets(secretdict=secretdict)

    def reconfigService(self, secretdict=None):
        self._setup_secrets(secretdict=secretdict)

    def _setup_secrets(self, secretdict: dict | None = None):
        if secretdict is None:
            secretdict = {}
        self.allsecrets = secretdict

    def get(self, key):
        if key in self.allsecrets:
            return self.allsecrets[key]
        return None
