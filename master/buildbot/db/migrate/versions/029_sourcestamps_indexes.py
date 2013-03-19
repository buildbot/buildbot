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

    sourcestamps = sa.Table('sourcestamps', metadata,
        sa.Column('id', sa.Integer,  primary_key=True),
        sa.Column('branch', sa.String(256)),
        sa.Column('revision', sa.String(256)),
        sa.Column('repository', sa.String(length=512), nullable=False,
            server_default=''),
        sa.Column('project', sa.String(length=512), nullable=False,
            server_default=''),
    )
    idx = sa.Index('sourcestamps_branch', sourcestamps.c.branch)
    idx.create()
    idx = sa.Index('sourcestamps_revision', sourcestamps.c.revision)
    idx.create()
    idx = sa.Index('sourcestamps_repository', sourcestamps.c.repository)
    idx.create()
    idx = sa.Index('sourcestamps_project', sourcestamps.c.project)
    idx.create()
