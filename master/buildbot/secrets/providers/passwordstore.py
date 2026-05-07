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
password store based provider
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from twisted.internet import defer

from buildbot import config
from buildbot.secrets.providers.base import SecretProviderBase
from buildbot.util import runprocess
from twisted.logger import Logger
log=Logger()

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class SecretInPass(SecretProviderBase):
    """
    secret is stored in a password store
    """

    name: str | None = "SecretInPass"  # type: ignore[assignment]

    def checkPassIsInPath(self) -> None:
        if not any((Path(p) / "pass").is_file() for p in os.environ["PATH"].split(":")):
            config.error("pass does not exist in PATH")

    def checkPassDirectoryIsAvailableAndReadable(self, dirname: str) -> None:
        if not os.access(dirname, os.F_OK):
            config.error(f"directory {dirname} does not exist")

    def checkConfig(self, gpgPassphrase: str | None = None, dirname: str | None = None) -> None:  # type: ignore[override]
        self.checkPassIsInPath()
        if dirname:
            self.checkPassDirectoryIsAvailableAndReadable(dirname)

    def reconfigService(self, gpgPassphrase: str | None = None, dirname: str | None = None) -> None:  # type: ignore[override]
        self._env = {**os.environ}
        if gpgPassphrase:
            self._env["PASSWORD_STORE_GPG_OPTS"] = f"--passphrase {gpgPassphrase}"
        if dirname:
            self._env["PASSWORD_STORE_DIR"] = dirname

    @defer.inlineCallbacks
    def get(self, entry: str) -> InlineCallbacksType[str | None]:
        """
        get the value from pass identified by 'entry'
        """
        try:
            rc, output, stderr = yield runprocess.run_process(
                self.master.reactor,
                ['pass', entry],
                env=self._env,
                collect_stderr=True,
                stderr_is_error=False, # usually this is true
            )
            if stderr:
                log.warn("Got stderr while accessing 'pass {entry}': {stderr}", entry=entry, stderr=stderr)
            if rc != 0:
                log.error("Got RC != 0 accessing 'pass {entry}' RC = {rc}", entry=entry, rc=rc)
                return None

            secret = "\n".join(output.decode("utf-8", "ignore").strip().splitlines())
            if not secret:
                return None
            else:
                return secret

        except OSError as exception:
            log.error("OSError accessing `pass {entry}`: {exception}", entry=entry, exception=exception)
            return None