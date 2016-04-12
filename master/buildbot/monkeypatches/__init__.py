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

from buildbot.util import sautils


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


@onlyOnce
def patch_mock_asserts():
    from buildbot.monkeypatches import mock_asserts
    mock_asserts.patch()


def patch_all(for_tests=False):
    if for_tests:
        patch_servicechecks()
        patch_testcase_assert_raises_regexp()
        patch_decorators()
        patch_mock_asserts()

    patch_sqlalchemy2364()
    patch_sqlalchemy2189()
    patch_python14653()
