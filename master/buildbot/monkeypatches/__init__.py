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

from buildbot.util import sautils
from twisted.python import util
from twisted.python import versions


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
def patch_bug4881():
    # this patch doesn't apply (or even import!) on Windows
    if sys.platform == 'win32':
        return

    # this bug was only present in Twisted-10.2.0
    if twisted.version == versions.Version('twisted', 10, 2, 0):
        from buildbot.monkeypatches import bug4881
        bug4881.patch()


@onlyOnce
def patch_bug4520():
    # this bug was patched in twisted-11.1.0, and only affects py26 and up
    py_26 = (sys.version_info[0] > 2 or
            (sys.version_info[0] == 2 and sys.version_info[1] >= 6))
    if twisted.version < versions.Version('twisted', 11, 1, 0) and py_26:
        from buildbot.monkeypatches import bug4520
        bug4520.patch()


@onlyOnce
def patch_bug5079():
    # this bug is patched in Twisted-12.0.0; it was probably
    # present in Twisted-8.x.0, but the patch doesn't work
    if (twisted.version < versions.Version('twisted', 12, 0, 0) and
            twisted.version >= versions.Version('twisted', 9, 0, 0)):
        from buildbot.monkeypatches import bug5079
        bug5079.patch()


@onlyOnce
def patch_sqlalchemy2364():
    # fix for SQLAlchemy bug 2364
    if sautils.sa_version() < (0, 7, 5):
        from buildbot.monkeypatches import sqlalchemy2364
        sqlalchemy2364.patch()


@onlyOnce
def patch_sqlalchemy2189():
    # fix for SQLAlchemy bug 2189
    if sautils.sa_version() <= (0, 7, 1):
        from buildbot.monkeypatches import sqlalchemy2189
        sqlalchemy2189.patch()


@onlyOnce
def patch_gatherResults():
    if twisted.version < versions.Version('twisted', 11, 1, 0):
        from buildbot.monkeypatches import gatherResults
        gatherResults.patch()


@onlyOnce
def patch_python14653():
    # this bug was fixed in Python 2.7.4: http://bugs.python.org/issue14653
    if sys.version_info[:3] < (2, 7, 4):
        from buildbot.monkeypatches import python14653
        python14653.patch()


@onlyOnce
def patch_servicechecks():
    from buildbot.monkeypatches import servicechecks
    servicechecks.patch()


@onlyOnce
def patch_testcase_patch():
    # Twisted-9.0.0 and earlier did not have a UnitTest.patch that worked on
    # Python-2.7
    if twisted.version.major <= 9 and sys.version_info[:2] == (2, 7):
        from buildbot.monkeypatches import testcase_patch
        testcase_patch.patch()


@onlyOnce
def patch_testcase_synctest():
    if twisted.version.major < 13 or (
            twisted.version.major == 13 and twisted.version.minor == 0):
        from buildbot.monkeypatches import testcase_synctest
        testcase_synctest.patch()


@onlyOnce
def patch_testcase_assert_raises_regexp():
    # pythons before 2.7 does not have TestCase.assertRaisesRegexp() method
    # add our local implementation if needed
    if sys.version_info[:2] < (2, 7):
        from buildbot.monkeypatches import testcase_assert
        testcase_assert.patch()


@onlyOnce
def patch_decorators():
    from buildbot.monkeypatches import decorators
    decorators.patch()


def patch_all(for_tests=False):
    if for_tests:
        patch_servicechecks()
        patch_testcase_patch()
        patch_testcase_synctest()
        patch_testcase_assert_raises_regexp()
        patch_decorators()

    patch_bug4881()
    patch_bug4520()
    patch_bug5079()
    patch_sqlalchemy2364()
    patch_sqlalchemy2189()
    patch_gatherResults()
    patch_python14653()
