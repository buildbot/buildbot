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


class FakePrivateTemporaryDirectory:
    def __init__(self, suffix=None, prefix=None, dir=None, mode=0o700):
        dir = dir or '/'
        prefix = prefix or ''
        suffix = suffix or ''

        self.name = os.path.join(dir, prefix + '@@@' + suffix)
        self.mode = mode

    def __enter__(self):
        return self.name

    def __exit__(self, exc, value, tb):
        pass

    def cleanup(self):
        pass


class MockPrivateTemporaryDirectory:
    def __init__(self):
        self.dirs = []

    def __call__(self, *args, **kwargs):
        ret = FakePrivateTemporaryDirectory(*args, **kwargs)
        self.dirs.append((ret.name, ret.mode))
        return ret
