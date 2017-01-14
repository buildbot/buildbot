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

# this is here for compatibility
from collections import defaultdict

assert defaultdict


class KeyedSets:

    def __init__(self):
        self.d = dict()

    def add(self, key, value):
        if key not in self.d:
            self.d[key] = set()
        self.d[key].add(value)

    def discard(self, key, value):
        if key in self.d:
            self.d[key].discard(value)
            if not self.d[key]:
                del self.d[key]

    def __contains__(self, key):
        return key in self.d

    def __getitem__(self, key):
        return self.d.get(key, set())

    def pop(self, key):
        if key in self.d:
            return self.d.pop(key)
        return set()
