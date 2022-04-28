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

import os
import unittest

from twisted.python import util


def onlyOnce(fn):
    'Set up FN to only run once within an interpreter instance'
    def wrap(*args, **kwargs):
        if hasattr(fn, 'called'):
            return None
        fn.called = 1
        return fn(*args, **kwargs)
    util.mergeFunctionMetadata(fn, wrap)
    return wrap

# NOTE: all of these patches test for applicability *before* importing the
# patch module.  This will help cut down on unnecessary imports where the
# patches are not needed, and also avoid problems with patches importing
# private things in external libraries that no longer exist.


@onlyOnce
def patch_testcase_timeout():
    # any test that should take more than 5 second should be annotated so.
    unittest.TestCase.timeout = 5

    # but we know that the DB tests are very slow, so we increase a bit that value for
    # real database tests
    if os.environ.get("BUILDBOT_TEST_DB_URL", None) is not None:
        unittest.TestCase.timeout = 120


@onlyOnce
def patch_servicechecks():
    from buildbot.monkeypatches import servicechecks
    servicechecks.patch()


@onlyOnce
def patch_decorators():
    from buildbot.monkeypatches import decorators
    decorators.patch()


@onlyOnce
def patch_config_for_unit_tests():
    from buildbot.config.master import set_is_in_unit_tests
    # by default, buildbot.config warns about not configured buildbotNetUsageData.
    # its important for users to not leak information, but unneeded and painful for tests
    set_is_in_unit_tests(True)


def patch_all(for_tests=False):
    if for_tests:
        patch_servicechecks()
        patch_testcase_timeout()
        patch_decorators()
        patch_config_for_unit_tests()
