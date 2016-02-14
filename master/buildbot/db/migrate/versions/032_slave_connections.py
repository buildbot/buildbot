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

from buildbot.db.types.json import JsonObject
from buildbot.util import sautils


def upgrade(migrate_engine):

    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    sautils.Table('builder_masters', metadata,
                  sa.Column('id', sa.Integer, primary_key=True),
                  # ..
                  )

    sautils.Table('masters', metadata,
                  sa.Column('id', sa.Integer, primary_key=True),
                  # ..
                  )

    buildslaves = sautils.Table("buildslaves", metadata,
                                sa.Column("id", sa.Integer, primary_key=True),
                                sa.Column("name", sa.String(256), nullable=False),
                                sa.Column("info", JsonObject, nullable=False),
                                )

    configured_buildslaves = sautils.Table(
        'configured_buildslaves', metadata,
        sa.Column('id', sa.Integer, primary_key=True, nullable=False),
        sa.Column('buildermasterid', sa.Integer,
                  sa.ForeignKey('builder_masters.id'), nullable=False),
        sa.Column('buildslaveid', sa.Integer,
                  sa.ForeignKey('buildslaves.id'), nullable=False),
    )

    connected_buildslaves = sautils.Table(
        'connected_buildslaves', metadata,
        sa.Column('id', sa.Integer, primary_key=True, nullable=False),
        sa.Column('masterid', sa.Integer,
                  sa.ForeignKey('masters.id'), nullable=False),
        sa.Column('buildslaveid', sa.Integer,
                  sa.ForeignKey('buildslaves.id'), nullable=False),
    )

    # update the column length in bulidslaves
    buildslaves.c.name.alter(sa.String(50), nullable=False)

    # and recreate the index that got unceremoniously dumped by sqlite
    if migrate_engine.dialect.name == 'sqlite':
        sa.Index('buildslaves_name', buildslaves.c.name, unique=True).create()

    # create the new tables
    configured_buildslaves.create()
    connected_buildslaves.create()

    # and the indices
    idx = sa.Index('configured_slaves_buildmasterid',
                   configured_buildslaves.c.buildermasterid)
    idx.create()

    idx = sa.Index('configured_slaves_slaves',
                   configured_buildslaves.c.buildslaveid)
    idx.create()

    idx = sa.Index('configured_slaves_identity',
                   configured_buildslaves.c.buildermasterid,
                   configured_buildslaves.c.buildslaveid, unique=True)
    idx.create()

    idx = sa.Index('connected_slaves_masterid',
                   connected_buildslaves.c.masterid)
    idx.create()

    idx = sa.Index('connected_slaves_slaves',
                   connected_buildslaves.c.buildslaveid)
    idx.create()

    idx = sa.Index('connected_slaves_identity',
                   connected_buildslaves.c.masterid,
                   connected_buildslaves.c.buildslaveid, unique=True)
    idx.create()
