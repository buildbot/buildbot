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


def upgrade(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    sa.Table('sourcestamps', metadata,
             sa.Column('id', sa.Integer, primary_key=True),
             sa.Column('ss_hash', sa.String(40), nullable=False),
             sa.Column('branch', sa.String(256)),
             sa.Column('revision', sa.String(256)),
             sa.Column('patchid', sa.Integer, sa.ForeignKey('patches.id')),
             sa.Column('repository', sa.String(length=512), nullable=False,
                       server_default=''),
             sa.Column('codebase', sa.String(256), nullable=False,
                       server_default=sa.DefaultClause("")),
             sa.Column('project', sa.String(length=512), nullable=False,
                       server_default=''),
             sa.Column('created_at', sa.Integer, nullable=False))

    # Specify what the new table should look like
    changes = sa.Table('changes', metadata,
                       sa.Column('changeid', sa.Integer, primary_key=True),
                       sa.Column('author', sa.String(256), nullable=False),
                       sa.Column('comments', sa.String(1024), nullable=False),
                       sa.Column('branch', sa.String(256)),
                       sa.Column('revision', sa.String(256)),
                       sa.Column('revlink', sa.String(256)),
                       sa.Column('when_timestamp', sa.Integer, nullable=False),
                       sa.Column('category', sa.String(256)),
                       sa.Column('repository', sa.String(length=512), nullable=False,
                                 server_default=''),
                       sa.Column('codebase', sa.String(256), nullable=False,
                                 server_default=sa.DefaultClause("")),
                       sa.Column('project', sa.String(length=512), nullable=False,
                                 server_default=''),
                       sa.Column('sourcestampid', sa.Integer,
                                 sa.ForeignKey('sourcestamps.id'))
                       )

    # Now drop column
    changeset.drop_column(
        sa.Column('is_dir', sa.SmallInteger, nullable=False),
        table=changes,
        metadata=metadata,
        engine=migrate_engine)

    # re-create all indexes on the table - sqlite dropped them
    if migrate_engine.dialect.name == 'sqlite':
        idx = sa.Index('changes_branch', changes.c.branch)
        idx.create()
        idx = sa.Index('changes_revision', changes.c.revision)
        idx.create()
        idx = sa.Index('changes_author', changes.c.author)
        idx.create()
        idx = sa.Index('changes_category', changes.c.category)
        idx.create()
        idx = sa.Index('changes_when_timestamp', changes.c.when_timestamp)
        idx.create()
        idx = sa.Index('changes_sourcestampid', changes.c.sourcestampid)
        idx.create()
