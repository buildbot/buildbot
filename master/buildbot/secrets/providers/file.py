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
file based provider
"""

from __future__ import annotations

import os
import stat

from buildbot import config
from buildbot.secrets.providers.base import SecretProviderBase


class SecretInAFile(SecretProviderBase):
    """
    secret is stored in a separate file under the given directory name
    """

    name: str | None = "SecretInAFile"  # type: ignore[assignment]

    def checkFileIsReadOnly(self, dirname: str, secretfile: str) -> None:
        filepath = os.path.join(dirname, secretfile)
        obs_stat = stat.S_IMODE(os.stat(filepath).st_mode)
        if (obs_stat & 0o7) != 0 and os.name == "posix":
            config.error(
                f"Permissions {oct(obs_stat)} on file {secretfile} are too open."
                " It is required that your secret files are NOT"
                " accessible by others!"
            )

    def checkSecretDirectoryIsAvailableAndReadable(self, dirname: str, suffixes: list[str]) -> None:
        if not os.access(dirname, os.F_OK):
            config.error(f"directory {dirname} does not exists")
        for secretfile in os.listdir(dirname):
            for suffix in suffixes:
                if secretfile.endswith(suffix):
                    self.checkFileIsReadOnly(dirname, secretfile)

    def loadSecrets(self, dirname: str, suffixes: list[str], strip: bool) -> dict[str, str]:
        secrets: dict[str, str] = {}
        for secretfile in os.listdir(dirname):
            secretvalue = None
            for suffix in suffixes:
                if secretfile.endswith(suffix):
                    with open(os.path.join(dirname, secretfile), encoding='utf-8') as source:
                        secretvalue = source.read()
                    if suffix:
                        secretfile = secretfile[: -len(suffix)]
                    if strip:
                        secretvalue = secretvalue.rstrip("\r\n")
                    secrets[secretfile] = secretvalue
        return secrets

    def checkConfig(
        self, dirname: str, suffixes: list[str] | None = None, strip: bool = True
    ) -> None:
        self._dirname = dirname
        if suffixes is None:
            suffixes = [""]
        self.checkSecretDirectoryIsAvailableAndReadable(dirname, suffixes=suffixes)

    def reconfigService(  # type: ignore[override]
        self, dirname: str, suffixes: list[str] | None = None, strip: bool = True
    ) -> None:
        self._dirname = dirname
        self.secrets: dict[str, str] = {}
        if suffixes is None:
            suffixes = [""]
        self.secrets = self.loadSecrets(self._dirname, suffixes=suffixes, strip=strip)

    def get(self, entry: str) -> str | None:
        """
        get the value from the file identified by 'entry'
        """
        return self.secrets.get(entry)
