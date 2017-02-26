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


import twisted

from twisted.python import versions


def patch_bug4881():
    # this patch doesn't apply (or even import!) on Windows
    import sys
    if sys.platform == 'win32':
        return

    # this bug was only present in Twisted-10.2.0
    if twisted.version == versions.Version(twisted.version.package, 10, 2, 0):
        from buildbot_worker.monkeypatches import bug4881
        bug4881.patch()


def patch_bug5079():
    # this bug will hopefully be patched in Twisted-12.0.0
    if twisted.version < versions.Version(twisted.version.package, 12, 0, 0):
        from buildbot_worker.monkeypatches import bug5079
        bug5079.patch()


def patch_all(for_tests=False):
    if for_tests:
        from buildbot_worker.monkeypatches import testcase_assert
        testcase_assert.patch()

    patch_bug4881()
    patch_bug5079()
