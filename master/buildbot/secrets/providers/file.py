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

from buildbot import config
from buildbot.secrets.providers.base import SecretProviderBase


class SecretInAFile(SecretProviderBase):
    """
    secret is stored in a separate file under the given directory name
    """
    name = "SecretInAFile"

    def checkFileIsReadOnly(self, dirname, secretfile):
        filepath = os.path.join(dirname, secretfile)
        if not os.access(filepath, os.R_OK) or os.access(filepath, os.W_OK):
            config.error("the file %s is not read-only for user" %
                         (secretfile))

    def checkSecretDirectoryIsAvailableAndReadable(self, dirname, suffix=None):
        if not os.access(dirname, os.F_OK):
            config.error("directory %s does not exists" % dirname)
        for secretfile in os.listdir(dirname):
            if suffix and secretfile.endswith(suffix):
                self.checkFileIsReadOnly(dirname, secretfile)
            elif not suffix:
                self.checkFileIsReadOnly(dirname, secretfile)

    def loadSecrets(self, dirname, suffix=None):
        secrets = {}
        for secretfile in os.listdir(dirname):
            secretvalue = None
            if suffix and secretfile.endswith(suffix):
                with open(os.path.join(dirname, secretfile)) as source:
                    secretvalue = source.read()
            elif not suffix:
                with open(os.path.join(dirname, secretfile)) as source:
                    secretvalue = source.read()
            secrets.update({secretfile: secretvalue})
        return secrets

    def checkConfig(self, dirname, suffix=None):
        self._dirname = dirname
        self.checkSecretDirectoryIsAvailableAndReadable(dirname, suffix=suffix)
        self.secrets = self.loadSecrets(self._dirname, suffix=suffix)

    def reconfigService(self, dirname, suffix=None):
        self._dirname = dirname
        self.secrets = {}
        self.checkSecretDirectoryIsAvailableAndReadable(dirname, suffix=suffix)
        self.secrets = self.loadSecrets(self._dirname, suffix=suffix)

    def get(self, entry):
        """
        get the value from the file identified by 'entry'
        """
        if entry in self.secrets.keys():
            return self.secrets[entry]
        else:
            return None
