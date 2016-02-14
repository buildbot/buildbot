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

    builders = sautils.Table(
        'builders', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.Text, nullable=False),
        sa.Column('name_hash', sa.String(40), nullable=False),
    )
    builders.create()

    builder_masters = sautils.Table(
        'builder_masters', metadata,
        sa.Column('id', sa.Integer, primary_key=True, nullable=False),
        sa.Column('builderid', sa.Integer, sa.ForeignKey('builders.id'),
                  nullable=False),
        sa.Column('masterid', sa.Integer, sa.ForeignKey('masters.id'),
                  nullable=False),
    )
    builder_masters.create()

    idx = sa.Index('builder_name_hash', builders.c.name_hash, unique=True)
    idx.create()
    idx = sa.Index('builder_masters_builderid', builder_masters.c.builderid)
    idx.create()
    idx = sa.Index('builder_masters_masterid', builder_masters.c.masterid)
    idx.create()
    idx = sa.Index('builder_masters_identity',
                   builder_masters.c.builderid, builder_masters.c.masterid,
                   unique=True)
    idx.create()
