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


def upgrade(migrate_engine):

    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    sa.Table('builder_masters', metadata,
             sa.Column('id', sa.Integer, primary_key=True),
             # ..
             )

    sa.Table('masters', metadata,
             sa.Column('id', sa.Integer, primary_key=True),
             # ..
             )

    buildworkers = sa.Table("buildworkers", metadata,
                           sa.Column("id", sa.Integer, primary_key=True),
                           sa.Column("name", sa.String(256), nullable=False),
                           sa.Column("info", JsonObject, nullable=False),
                            )

    configured_buildworkers = sa.Table('configured_buildworkers', metadata,
                                      sa.Column('id', sa.Integer, primary_key=True, nullable=False),
                                      sa.Column('buildermasterid', sa.Integer,
                                                sa.ForeignKey('builder_masters.id'), nullable=False),
                                      sa.Column('buildworkerid', sa.Integer, sa.ForeignKey('buildworkers.id'),
                                                nullable=False),
                                       )

    connected_buildworkers = sa.Table('connected_buildworkers', metadata,
                                     sa.Column('id', sa.Integer, primary_key=True, nullable=False),
                                     sa.Column('masterid', sa.Integer,
                                               sa.ForeignKey('masters.id'), nullable=False),
                                     sa.Column('buildworkerid', sa.Integer, sa.ForeignKey('buildworkers.id'),
                                               nullable=False),
                                      )

    # update the column length in bulidworkers
    buildworkers.c.name.alter(sa.String(50), nullable=False)

    # and recreate the index that got unceremoniously dumped by sqlite
    if migrate_engine.dialect.name == 'sqlite':
        sa.Index('buildworkers_name', buildworkers.c.name, unique=True).create()

    # create the new tables
    configured_buildworkers.create()
    connected_buildworkers.create()

    # and the indices
    idx = sa.Index('configured_workers_buildmasterid',
                   configured_buildworkers.c.buildermasterid)
    idx.create()

    idx = sa.Index('configured_workers_workers',
                   configured_buildworkers.c.buildworkerid)
    idx.create()

    idx = sa.Index('configured_workers_identity',
                   configured_buildworkers.c.buildermasterid,
                   configured_buildworkers.c.buildworkerid, unique=True)
    idx.create()

    idx = sa.Index('connected_workers_masterid',
                   connected_buildworkers.c.masterid)
    idx.create()

    idx = sa.Index('connected_workers_workers',
                   connected_buildworkers.c.buildworkerid)
    idx.create()

    idx = sa.Index('connected_workers_identity',
                   connected_buildworkers.c.masterid,
                   connected_buildworkers.c.buildworkerid, unique=True)
    idx.create()
