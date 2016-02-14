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

    # autoload the tables that are only referenced here
    sautils.Table('changes', metadata, autoload=True)
    sautils.Table('buildsets', metadata, autoload=True)
    sautils.Table("objects", metadata, autoload=True)

    # drop all tables.  Schedulers will re-populate on startup

    scheduler_changes_tbl = sautils.Table('scheduler_changes', metadata,
                                          sa.Column('schedulerid', sa.Integer),
                                          # ...
                                          )
    scheduler_changes_tbl.drop()
    metadata.remove(scheduler_changes_tbl)

    scheduler_upstream_buildsets_tbl = sautils.Table('scheduler_upstream_buildsets',
                                                     metadata,
                                                     sa.Column('buildsetid', sa.Integer),
                                                     # ...
                                                     )
    scheduler_upstream_buildsets_tbl.drop()
    metadata.remove(scheduler_upstream_buildsets_tbl)

    schedulers_tbl = sautils.Table("schedulers", metadata,
                                   sa.Column('schedulerid', sa.Integer),
                                   # ...
                                   )
    schedulers_tbl.drop()
    metadata.remove(schedulers_tbl)

    # schedulers and scheduler_upstream_buildsets aren't coming back, but
    # scheduler_changes is -- along with its indexes

    scheduler_changes_tbl = sautils.Table(
        'scheduler_changes', metadata,
        sa.Column('objectid', sa.Integer, sa.ForeignKey('objects.id')),
        sa.Column('changeid', sa.Integer, sa.ForeignKey('changes.changeid')),
        sa.Column('important', sa.Integer),
    )
    scheduler_changes_tbl.create()

    idx = sa.Index('scheduler_changes_objectid',
                   scheduler_changes_tbl.c.objectid)
    idx.create()

    idx = sa.Index('scheduler_changes_changeid',
                   scheduler_changes_tbl.c.changeid)
    idx.create()

    idx = sa.Index('scheduler_changes_unique',
                   scheduler_changes_tbl.c.objectid,
                   scheduler_changes_tbl.c.changeid, unique=True)
    idx.create()
