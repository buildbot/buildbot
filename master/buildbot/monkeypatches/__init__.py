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

from twisted.python import util
from builtins import int
from future.utils import PY3


def onlyOnce(fn):
    'Set up FN to only run once within an interpreter instance'
    def wrap(*args, **kwargs):
        if hasattr(fn, 'called'):
            return
        fn.called = 1
        return fn(*args, **kwargs)
    util.mergeFunctionMetadata(fn, wrap)
    return wrap

# NOTE: all of these patches test for applicability *before* importing the
# patch module.  This will help cut down on unnecessary imports where the
# patches are not needed, and also avoid problems with patches importing
# private things in external libraries that no longer exist.


@onlyOnce
def patch_python14653():
    # this bug was fixed in Python 2.7.4: http://bugs.python.org/issue14653
    if sys.version_info[:3] < (2, 7, 4):
        from buildbot.monkeypatches import python14653
        python14653.patch()


@onlyOnce
def patch_twisted9127():
    if PY3:
        from buildbot.monkeypatches import twisted9127
        twisted9127.patch()


@onlyOnce
def patch_testcase_timeout():
    import unittest
    import os
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
def patch_mysqlclient_warnings():
    try:
        from _mysql_exceptions import Warning
        # MySQLdb.compat is only present in mysqlclient
        import MySQLdb.compat  # noqa pylint: disable=unused-import
    except ImportError:
        return
    # workaround for https://twistedmatrix.com/trac/ticket/9005
    # mysqlclient is easier to patch than twisted
    # we swap _mysql_exceptions.Warning arguments so that the code is in second place

    def patched_init(self, *args):
        if isinstance(args[0], int):
            super(Warning, self).__init__("{} {}".format(args[0], args[1]))
        else:
            super(Warning, self).__init__(*args)
    Warning.__init__ = patched_init


@onlyOnce
def patch_decorators():
    from buildbot.monkeypatches import decorators
    decorators.patch()


@onlyOnce
def patch_config_for_unit_tests():
    from buildbot import config
    # by default, buildbot.config warns about not configured buildbotNetUsageData.
    # its important for users to not leak information, but unneeded and painful for tests
    config._in_unit_tests = True


@onlyOnce
def patch_unittest_testcase():
    from twisted.trial.unittest import TestCase

    # In Python 3.2,
    # - assertRaisesRegexp() was renamed to assertRaisesRegex(),
    #   and assertRaisesRegexp() was deprecated.
    # - assertRegexpMatches() was renamed to assertRegex()
    #   and assertRegexpMatches() was deprecated.
    if not getattr(TestCase, "assertRaisesRegex", None):
        TestCase.assertRaisesRegex = TestCase.assertRaisesRegexp
    if not getattr(TestCase, "assertRegex", None):
        TestCase.assertRegex = TestCase.assertRegexpMatches


def patch_all(for_tests=False):
    if for_tests:
        patch_servicechecks()
        patch_testcase_timeout()
        patch_decorators()
        patch_mysqlclient_warnings()
        patch_config_for_unit_tests()
        patch_unittest_testcase()

    patch_python14653()
    patch_twisted9127()
