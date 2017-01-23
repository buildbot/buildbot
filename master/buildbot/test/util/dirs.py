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

from twisted.internet import defer


class DirsMixin(object):

    _dirs = None

    def setUpDirs(self, *dirs):
        """Make sure C{dirs} exist and are empty, and set them up to be deleted
        in tearDown."""
        self._dirs = map(os.path.abspath, dirs)
        for dir in self._dirs:
            if os.path.exists(dir):
                shutil.rmtree(dir)
            os.makedirs(dir)
        # return a deferred to make chaining easier
        return defer.succeed(None)

    def tearDownDirs(self):
        for dir in self._dirs:
            if os.path.exists(dir):
                shutil.rmtree(dir)
        # return a deferred to make chaining easier
        return defer.succeed(None)
