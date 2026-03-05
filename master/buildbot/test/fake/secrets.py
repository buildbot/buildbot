from __future__ import annotations

from typing import Any

from buildbot.secrets.providers.base import SecretProviderBase


class FakeSecretStorage(SecretProviderBase):
    name: str | None = "SecretsInFake"  # type: ignore[assignment]

    def __init__(self, *args: Any, secretdict: dict | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs, secretdict=secretdict)
        self._setup_secrets(secretdict=secretdict)

    def reconfigService(self, secretdict: dict | None = None) -> None:
        self._setup_secrets(secretdict=secretdict)

    def _setup_secrets(self, secretdict: dict | None = None) -> None:
        if secretdict is None:
            secretdict = {}
        self.allsecrets = secretdict

    def get(self, key: str) -> str | None:
        if key in self.allsecrets:
            return self.allsecrets[key]
        return None
