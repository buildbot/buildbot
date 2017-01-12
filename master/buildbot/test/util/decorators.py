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
Various decorators for test cases
"""

from __future__ import absolute_import
from __future__ import print_function

import os
import sys

from twisted.python import runtime

_FLAKY_ENV_VAR = 'RUN_FLAKY_TESTS'


def todo(message):
    """
    decorator to mark a todo test
    """
    def wrap(func):
        """
        just mark the test
        """
        func.todo = message
        return func
    return wrap


def flaky(bugNumber):
    def wrap(fn):
        if not os.environ.get(_FLAKY_ENV_VAR):
            fn.skip = ("Flaky test (http://trac.buildbot.net/ticket/%d) "
                       "- set $%s to run anyway" % (bugNumber, _FLAKY_ENV_VAR))
        return fn
    return wrap


def skipUnlessPlatformIs(platform):
    def closure(test):
        if runtime.platformType != platform:
            test.skip = "not a %s platform" % platform
        return test
    return closure


def skipIfPythonVersionIsLess(min_version_info):
    assert isinstance(min_version_info, tuple)

    def closure(test):
        if sys.version_info < min_version_info:
            test.skip = "requires Python >= {0}".format(min_version_info)
        return test
    return closure
