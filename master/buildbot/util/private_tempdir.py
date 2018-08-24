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

from __future__ import absolute_import
from __future__ import print_function

import os
import shutil


class PrivateTemporaryDirectory(object):
    """ Works similarly to python 3.2+ TemporaryDirectory except the
        permissions and the exact path are given to the class.

        TODO: Use TemporaryDirectory when python 2.x is dropped

        Note, that Windows ignores the permissions.
    """

    def __init__(self, name, mode=0o700):
        self.name = name
        self.mode = mode
        self._cleanup_needed = True

    def _create_dir(self, name, mode):
        os.makedirs(name, mode=mode)

    def __enter__(self):
        self._create_dir(self.name, self.mode)
        return self

    def __exit__(self, exc, value, tb):
        self.cleanup()

    def cleanup(self):
        if self._cleanup_needed:
            shutil.rmtree(self.name)
            self._cleanup_needed = False
