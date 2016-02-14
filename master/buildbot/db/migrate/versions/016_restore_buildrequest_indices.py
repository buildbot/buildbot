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

import sqlalchemy as sa

from buildbot.util import sautils


def upgrade(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    # the column drops in 011_add_buildrequest_claims.py unfortunately
    # also drop a great deal of other stuff on sqlite.  In particular, all
    # indexes and foreign keys.
    #
    # The foreign keys do not matter anyway - SQLite tracks them but ignores
    # them.  The indices, however, are important, so they are re-added here,
    # but only for the sqlite dialect.

    if migrate_engine.dialect.name != 'sqlite':
        return

    buildrequests = sautils.Table('buildrequests', metadata, autoload=True)
    sa.Index('buildrequests_buildsetid', buildrequests.c.buildsetid).create()
    sa.Index('buildrequests_buildername', buildrequests.c.buildername).create()
    sa.Index('buildrequests_complete', buildrequests.c.complete).create()
