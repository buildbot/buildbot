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

    def checkConfig(self, name, dirname):
        if dirname is None:
            config.error("directory name could not be empty")

    def reconfigService(self, name, dirname):
        self._dirname = dirname

    def get(self, entry):
        """
        get the value from the file identified by 'entry'
        """
        filename = os.path.join(self._dirname, entry)
        assert os.path.isfile(filename), \
            'File {} does not exist'.format(filename)
        with open(filename) as source:
            secret = source.read().strip()
        return secret
