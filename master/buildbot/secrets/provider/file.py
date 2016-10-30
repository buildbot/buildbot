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
file based providers
"""
import os

from buildbot.secrets.provider.base import SecretProviderBase


class SecretInAFile(SecretProviderBase):
    """
    basic provider where each secret is stored in a separate file under the
    given directory
    """
    def __init__(self, name, dirname, ext=None):
        super(SecretInAFile, self).__init__(name=name)

        self._dirname = dirname
        self._ext = ext

    def get(self, entry):
        """
        get the value from the file identified by 'entry'
        """
        filename = os.path.join(self._dirname, entry)
        if self._ext:
            filename += self._ext

        assert os.path.isfile(filename), \
            'File {} does not exist'.format(filename)

        with open(filename) as source:
            secret = source.read().strip()

        return secret, None
