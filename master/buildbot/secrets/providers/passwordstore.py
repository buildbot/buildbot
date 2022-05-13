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

import os
from pathlib import Path

from twisted.internet import defer

from buildbot import config
from buildbot.secrets.providers.base import SecretProviderBase
from buildbot.util import runprocess


class SecretInPass(SecretProviderBase):
    """
    secret is stored in a password store
    """

    name = "SecretInPass"

    def checkPassIsInPath(self):
        if not any((Path(p) / "pass").is_file() for p in os.environ["PATH"].split(":")):
            config.error("pass does not exist in PATH")

    def checkPassDirectoryIsAvailableAndReadable(self, dirname):
        if not os.access(dirname, os.F_OK):
            config.error(f"directory {dirname} does not exist")

    def checkConfig(self, gpgPassphrase=None, dirname=None):
        self.checkPassIsInPath()
        if dirname:
            self.checkPassDirectoryIsAvailableAndReadable(dirname)

    def reconfigService(self, gpgPassphrase=None, dirname=None):
        self._env = {**os.environ}
        if gpgPassphrase:
            self._env["PASSWORD_STORE_GPG_OPTS"] = f"--passphrase {gpgPassphrase}"
        if dirname:
            self._env["PASSWORD_STORE_DIR"] = dirname

    @defer.inlineCallbacks
    def get(self, entry):
        """
        get the value from pass identified by 'entry'
        """
        try:
            rc, output = yield runprocess.run_process(
                self.master.reactor,
                ["pass", entry],
                env=self._env,
                collect_stderr=False,
                stderr_is_error=True,
            )
            if rc != 0:
                return None
            return output.decode("utf-8", "ignore").splitlines()[0]
        except IOError:
            return None
