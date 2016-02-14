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

    sautils.Table('masters', metadata,
                  sa.Column('id', sa.Integer, primary_key=True),
                  # ..
                  )

    changesources = sautils.Table(
        'changesources', metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column('name', sa.Text, nullable=False),
        sa.Column('name_hash', sa.String(40), nullable=False),
    )

    changesource_masters = sautils.Table(
        'changesource_masters', metadata,
        sa.Column('changesourceid', sa.Integer,
                  sa.ForeignKey('changesources.id'), nullable=False,
                  primary_key=True),
        sa.Column('masterid', sa.Integer, sa.ForeignKey('masters.id'),
                  nullable=False),
    )

    # create the new tables
    changesources.create()
    changesource_masters.create()

    # and the indices
    idx = sa.Index('changesource_name_hash', changesources.c.name_hash, unique=True)
    idx.create()
