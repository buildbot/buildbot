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

import sys
import twisted
from twisted.trial import unittest

def patch_testcase_patch():
    """
    Patch out TestCase.patch to skip the test on version combinations where it
    does not work.

    (used for debugging only)
    """
    # Twisted-9.0.0 and earlier did not have a UnitTest.patch that worked on
    # Python-2.7
    if twisted.version.major <= 9 and sys.version_info[:2] == (2,7):
        def nopatch(self, *args):
            raise unittest.SkipTest('unittest.TestCase.patch is not available')
        unittest.TestCase.patch = nopatch
