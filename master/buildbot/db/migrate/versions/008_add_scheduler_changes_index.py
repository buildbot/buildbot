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


def upgrade(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    scheduler_changes = sa.Table('scheduler_changes', metadata,
                                 sa.Column('schedulerid', sa.Integer),
                                 sa.Column('changeid', sa.Integer),
                                 sa.Column('important', sa.SmallInteger),
                                 )

    idx = sa.Index('scheduler_changes_unique',
                   scheduler_changes.c.schedulerid,
                   scheduler_changes.c.changeid, unique=True)
    idx.create(migrate_engine)
