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
from migrate import changeset

from buildbot.util import sautils


def upgrade(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    # the old (non-sqlalchemy-migrate) migration scripts messed up the
    # lengths of these columns, so fix them here.
    changeset.alter_column(
        sa.Column('class_name', sa.String(128), nullable=False),
        table="schedulers",
        metadata=metadata,
        engine=migrate_engine)

    changeset.alter_column(
        sa.Column('name', sa.String(128), nullable=False),
        table="schedulers",
        metadata=metadata,
        engine=migrate_engine)

    # sqlalchemy's reflection gets the server_defaults wrong, so this
    # table has to be included here.
    changes = sautils.Table('changes', metadata,
                            sa.Column(
                                'changeid', sa.Integer, primary_key=True),
                            sa.Column(
                                'author', sa.String(256), nullable=False),
                            sa.Column(
                                'comments', sa.String(1024), nullable=False),
                            sa.Column(
                                'is_dir', sa.SmallInteger, nullable=False),
                            sa.Column('branch', sa.String(256)),
                            sa.Column('revision', sa.String(256)),
                            sa.Column('revlink', sa.String(256)),
                            sa.Column(
                                'when_timestamp', sa.Integer, nullable=False),
                            sa.Column('category', sa.String(256)),
                            sa.Column('repository', sa.String(length=512), nullable=False,
                                      server_default=''),
                            sa.Column('project', sa.String(length=512), nullable=False,
                                      server_default=''),
                            )
    changeset.alter_column(
        sa.Column('author', sa.String(256), nullable=False),
        table=changes,
        metadata=metadata,
        engine=migrate_engine)
    changeset.alter_column(
        sa.Column('branch', sa.String(256)),
        table=changes,
        metadata=metadata,
        engine=migrate_engine)
