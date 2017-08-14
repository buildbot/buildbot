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
from __future__ import absolute_import
from __future__ import print_function

import os
import stat

from buildbot import config
from buildbot.secrets.providers.base import SecretProviderBase


class SecretInAFile(SecretProviderBase):
    """
    secret is stored in a separate file under the given directory name
    """
    name = "SecretInAFile"

    def checkFileIsReadOnly(self, dirname, secretfile):
        filepath = os.path.join(dirname, secretfile)
        obs_stat = stat.S_IMODE(os.stat(filepath).st_mode)
        if (obs_stat & 0o77) != 0 and os.name == "posix":
            config.error("Permissions %s on file %s are too open."
                         " It is required that your secret files are NOT"
                         " accessible by others!" % (oct(obs_stat),
                                                     secretfile))

    def checkSecretDirectoryIsAvailableAndReadable(self, dirname, suffixes):
        if not os.access(dirname, os.F_OK):
            config.error("directory %s does not exists" % dirname)
        for secretfile in os.listdir(dirname):
            for suffix in suffixes:
                if secretfile.endswith(suffix):
                    self.checkFileIsReadOnly(dirname, secretfile)

    def loadSecrets(self, dirname, suffixes, strip):
        secrets = {}
        for secretfile in os.listdir(dirname):
            secretvalue = None
            for suffix in suffixes:
                if secretfile.endswith(suffix):
                    with open(os.path.join(dirname, secretfile)) as source:
                        secretvalue = source.read()
                    if suffix:
                        secretfile = secretfile[:-len(suffix)]
                    if strip:
                        secretvalue = secretvalue.rstrip("\r\n")
                    secrets[secretfile] = secretvalue
        return secrets

    def checkConfig(self, dirname, suffixes=None, strip=True):
        self._dirname = dirname
        if suffixes is None:
            suffixes = [""]
        self.checkSecretDirectoryIsAvailableAndReadable(dirname,
                                                        suffixes=suffixes)

    def reconfigService(self, dirname, suffixes=None, strip=True):
        self._dirname = dirname
        self.secrets = {}
        if suffixes is None:
            suffixes = [""]
        self.secrets = self.loadSecrets(self._dirname, suffixes=suffixes,
                                        strip=strip)

    def get(self, entry):
        """
        get the value from the file identified by 'entry'
        """
        return self.secrets.get(entry)
