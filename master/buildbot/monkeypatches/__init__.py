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
from buildbot.util import sautils

# NOTE: all of these patches test for applicability *before* importing the
# patch module.  This will help cut down on unnecessary imports where the
# patches are not needed, and also avoid problems with patches importing
# private things in external libraries that no longer exist.

def patch_bug4881():
    # this patch doesn't apply (or even import!) on Windows
    import sys
    if sys.platform == 'win32':
        return

    # this bug was only present in Twisted-10.2.0
    if twisted.version == versions.Version('twisted', 10, 2, 0):
        from buildbot.monkeypatches import bug4881
        bug4881.patch()

def patch_bug5079():
    # this bug will hopefully be patched in Twisted-12.0.0; it was probably
    # present in Twisted-8.x.0, but the patch doesn't work
    if (twisted.version < versions.Version('twisted', 12, 0, 0) and
        twisted.version >= versions.Version('twisted', 9, 0, 0)):
        from buildbot.monkeypatches import bug5079
        bug5079.patch()

def patch_sqlalchemy2364():
    # fix for SQLAlchemy bug 2364 
    if sautils.sa_version() < (0,7,5):
        from buildbot.monkeypatches import sqlalchemy2364
        sqlalchemy2364.patch()

def patch_sqlalchemy2189():
    # fix for SQLAlchemy bug 2189
    if sautils.sa_version() <= (0,7,1):
        from buildbot.monkeypatches import sqlalchemy2189
        sqlalchemy2189.patch()

def patch_all():
    patch_bug4881()
    patch_bug5079()
    patch_sqlalchemy2364()
    patch_sqlalchemy2189()
