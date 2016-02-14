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

    # drop the old scheduler_changes table (that references objects).  This
    # loses a small, transient bit of information (processed but un-built
    # changes), during a cluster-wide downtime.

    metadata = sa.MetaData()
    metadata.bind = migrate_engine
    scheduler_changes = sautils.Table('scheduler_changes', metadata,
                                      sa.Column('objectid', sa.Integer),
                                      sa.Column('changeid', sa.Integer),
                                      # ..
                                      )

    idx = sa.Index('scheduler_changes_objectid', scheduler_changes.c.objectid)
    idx.drop()
    idx = sa.Index('scheduler_changes_changeid', scheduler_changes.c.changeid)
    idx.drop()
    idx = sa.Index('scheduler_changes_unique', scheduler_changes.c.objectid,
                   scheduler_changes.c.changeid, unique=True)
    idx.drop()
    scheduler_changes.drop()

    # now create the new tables (with new metadata since we're using the same
    # table name)

    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    sautils.Table('masters', metadata,
                  sa.Column('id', sa.Integer, primary_key=True),
                  # ..
                  )

    sautils.Table('changes', metadata,
                  sa.Column('changeid', sa.Integer, primary_key=True),
                  # ..
                  )

    schedulers = sautils.Table(
        'schedulers', metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column('name', sa.Text, nullable=False),
        sa.Column('name_hash', sa.String(40), nullable=False),
    )

    scheduler_masters = sautils.Table(
        'scheduler_masters', metadata,
        sa.Column('schedulerid', sa.Integer, sa.ForeignKey('schedulers.id'),
                  nullable=False, primary_key=True),
        sa.Column('masterid', sa.Integer, sa.ForeignKey('masters.id'),
                  nullable=False),
    )

    scheduler_changes = sautils.Table(
        'scheduler_changes', metadata,
        sa.Column('schedulerid', sa.Integer, sa.ForeignKey('schedulers.id')),
        sa.Column('changeid', sa.Integer, sa.ForeignKey('changes.changeid')),
        # true (nonzero) if this change is important to this scheduler
        sa.Column('important', sa.Integer),
    )

    # create the new tables
    schedulers.create()
    scheduler_masters.create()
    scheduler_changes.create()

    # and the indices
    idx = sa.Index('scheduler_name_hash', schedulers.c.name_hash, unique=True)
    idx.create()
    idx = sa.Index('scheduler_changes_schedulerid',
                   scheduler_changes.c.schedulerid)
    idx.create()
    idx = sa.Index('scheduler_changes_changeid',
                   scheduler_changes.c.changeid)
    idx.create()
    idx = sa.Index('scheduler_changes_unique',
                   scheduler_changes.c.schedulerid, scheduler_changes.c.changeid,
                   unique=True)
    idx.create()
