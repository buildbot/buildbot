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

import sys

import twisted
from twisted.python import runtime
from twisted.python import versions


def usesFlushLoggedErrors(test):
    "Decorate a test method that uses flushLoggedErrors with this decorator"
    if (sys.version_info[:2] == (2, 7)
            and twisted.version <= versions.Version('twisted', 9, 0, 0)):
        test.skip = \
            "flushLoggedErrors is broken on Python==2.7 and Twisted<=9.0.0"
    return test


def skipUnlessPlatformIs(platform):
    def closure(test):
        if runtime.platformType != platform:
            test.skip = "not a %s platform" % platform
        return test
    return closure
