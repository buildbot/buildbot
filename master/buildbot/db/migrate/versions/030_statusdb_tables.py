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

    # foreign keys
    sautils.Table('builds', metadata,
                  sa.Column('id', sa.Integer, primary_key=True),
                  )

    steps = sautils.Table(
        'steps', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('number', sa.Integer, nullable=False),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('buildid', sa.Integer, sa.ForeignKey('builds.id')),
        sa.Column('started_at', sa.Integer),
        sa.Column('complete_at', sa.Integer),
        sa.Column('state_strings_json', sa.Text, nullable=False),
        sa.Column('results', sa.Integer),
        sa.Column('urls_json', sa.Text, nullable=False),
    )

    logs = sautils.Table(
        'logs', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('stepid', sa.Integer, sa.ForeignKey('steps.id')),
        sa.Column('complete', sa.SmallInteger, nullable=False),
        sa.Column('num_lines', sa.Integer, nullable=False),
        sa.Column('type', sa.String(1), nullable=False),
    )

    logchunks = sautils.Table(
        'logchunks', metadata,
        sa.Column('logid', sa.Integer, sa.ForeignKey('logs.id')),
        sa.Column('first_line', sa.Integer, nullable=False),
        sa.Column('last_line', sa.Integer, nullable=False),
        sa.Column('content', sa.LargeBinary(65536)),
        sa.Column('compressed', sa.SmallInteger, nullable=False),
    )

    steps.create()
    logs.create()
    logchunks.create()

    idx = sa.Index('steps_number', steps.c.buildid, steps.c.number,
                   unique=True)
    idx.create()

    idx = sa.Index('steps_name', steps.c.buildid, steps.c.name,
                   unique=True)
    idx.create()

    idx = sa.Index('logs_name', logs.c.stepid, logs.c.name,
                   unique=True)
    idx.create()

    idx = sa.Index('logchunks_firstline',
                   logchunks.c.logid, logchunks.c.first_line)
    idx.create()

    idx = sa.Index('logchunks_lastline',
                   logchunks.c.logid, logchunks.c.last_line)
    idx.create()
