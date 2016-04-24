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


# The existing builds table doesn't contain much useful information, and it's
# horrendously denormalized.  So we kill it dead.


def drop_builds(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    builds = sautils.Table('builds', metadata,
                           sa.Column('id', sa.Integer, primary_key=True),
                           )
    builds.drop()


def add_new_builds(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    # foreign keys
    sautils.Table('buildrequests', metadata,
                  sa.Column('id', sa.Integer, primary_key=True),
                  )
    sautils.Table('builders', metadata,
                  sa.Column('id', sa.Integer, primary_key=True),
                  )
    sautils.Table("masters", metadata,
                  sa.Column('id', sa.Integer, primary_key=True),
                  )

    builds = sautils.Table(
        'builds', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('number', sa.Integer, nullable=False),
        sa.Column('builderid', sa.Integer, sa.ForeignKey('builders.id')),
        sa.Column('buildrequestid', sa.Integer,
                  sa.ForeignKey('buildrequests.id'), nullable=False),
        sa.Column('buildslaveid', sa.Integer),
        sa.Column('masterid', sa.Integer, sa.ForeignKey('masters.id'),
                  nullable=False),
        sa.Column('started_at', sa.Integer, nullable=False),
        sa.Column('complete_at', sa.Integer),
        sa.Column('state_strings_json', sa.Text, nullable=False),
        sa.Column('results', sa.Integer),
    )
    builds.create()
    idx = sa.Index('builds_number', builds.c.builderid, builds.c.number,
                   unique=True)
    idx.create()
    idx = sa.Index('builds_buildslaveid', builds.c.buildslaveid)
    idx.create()
    idx = sa.Index('builds_masterid', builds.c.masterid)
    idx.create()
    idx = sa.Index('builds_buildrequestid', builds.c.buildrequestid)
    idx.create()


def upgrade(migrate_engine):
    drop_builds(migrate_engine)
    add_new_builds(migrate_engine)
