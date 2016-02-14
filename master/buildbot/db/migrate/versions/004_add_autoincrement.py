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

    # re-include some of the relevant tables, as they were in version 3, since
    # sqlalchemy's reflection doesn't work very well for defaults.  These must
    # be complete table specifications as for some dialects sqlalchemy will
    # create a brand new, temporary table, and copy data over

    sautils.Table("schedulers", metadata,
                  sa.Column('schedulerid', sa.Integer, autoincrement=False,
                            primary_key=True),
                  sa.Column('name', sa.String(128), nullable=False),
                  sa.Column('state', sa.String(1024), nullable=False),
                  sa.Column('class_name', sa.String(128), nullable=False),
                  )

    sautils.Table('changes', metadata,
                  sa.Column('changeid', sa.Integer, autoincrement=False,
                            primary_key=True),
                  sa.Column('author', sa.String(256), nullable=False),
                  sa.Column('comments', sa.String(1024), nullable=False),
                  sa.Column('is_dir', sa.SmallInteger, nullable=False),
                  sa.Column('branch', sa.String(256)),
                  sa.Column('revision', sa.String(256)),
                  sa.Column('revlink', sa.String(256)),
                  sa.Column('when_timestamp', sa.Integer, nullable=False),
                  sa.Column('category', sa.String(256)),
                  sa.Column('repository', sa.Text, nullable=False, server_default=''),
                  sa.Column('project', sa.Text, nullable=False, server_default=''),
                  )

    sautils.Table('patches', metadata,
                  sa.Column('id', sa.Integer, primary_key=True),
                  sa.Column('patchlevel', sa.Integer, nullable=False),
                  sa.Column('patch_base64', sa.Text, nullable=False),
                  sa.Column('subdir', sa.Text),
                  )

    sautils.Table('sourcestamps', metadata,
                  sa.Column('id', sa.Integer, autoincrement=True, primary_key=True),
                  sa.Column('branch', sa.String(256)),
                  sa.Column('revision', sa.String(256)),
                  sa.Column('patchid', sa.Integer, sa.ForeignKey('patches.id')),
                  sa.Column('repository', sa.Text(length=None), nullable=False,
                            server_default=''),
                  sa.Column('project', sa.Text(length=None), nullable=False,
                            server_default=''),
                  )

    sautils.Table('buildsets', metadata,
                  sa.Column('id', sa.Integer, primary_key=True),
                  sa.Column('external_idstring', sa.String(256)),
                  sa.Column('reason', sa.String(256)),
                  sa.Column('sourcestampid', sa.Integer,
                            sa.ForeignKey('sourcestamps.id'), nullable=False),
                  sa.Column('submitted_at', sa.Integer, nullable=False),
                  sa.Column('complete', sa.SmallInteger, nullable=False,
                            server_default=sa.DefaultClause("0")),
                  sa.Column('complete_at', sa.Integer),
                  sa.Column('results', sa.SmallInteger),
                  )

    sautils.Table('buildrequests', metadata,
                  sa.Column('id', sa.Integer, primary_key=True),
                  sa.Column('buildsetid', sa.Integer, sa.ForeignKey("buildsets.id"),
                            nullable=False),
                  sa.Column('buildername', sa.String(length=None), nullable=False),
                  sa.Column('priority', sa.Integer, nullable=False,
                            server_default=sa.DefaultClause("0")),
                  sa.Column('claimed_at', sa.Integer,
                            server_default=sa.DefaultClause("0")),
                  sa.Column('claimed_by_name', sa.String(length=None)),
                  sa.Column('claimed_by_incarnation', sa.String(length=None)),
                  sa.Column('complete', sa.Integer,
                            server_default=sa.DefaultClause("0")),
                  sa.Column('results', sa.SmallInteger),
                  sa.Column('submitted_at', sa.Integer, nullable=False),
                  sa.Column('complete_at', sa.Integer),
                  )

    sautils.Table('builds', metadata,
                  sa.Column('id', sa.Integer, primary_key=True),
                  sa.Column('number', sa.Integer, nullable=False),
                  sa.Column('brid', sa.Integer, sa.ForeignKey('buildrequests.id'),
                            nullable=False),
                  sa.Column('start_time', sa.Integer, nullable=False),
                  sa.Column('finish_time', sa.Integer),
                  )

    to_autoinc = [s.split(".") for s in
                  ("schedulers.schedulerid",
                   "builds.id",
                   "changes.changeid",
                   "buildrequests.id",
                   "buildsets.id",
                   "patches.id",
                   "sourcestamps.id",)
                  ]

    # It seems that SQLAlchemy's ALTER TABLE doesn't work when migrating from
    # INTEGER to PostgreSQL's SERIAL data type (which is just pseudo data type
    # for INTEGER with SEQUENCE), so we have to work-around this with raw SQL.
    if migrate_engine.dialect.name in ('postgres', 'postgresql'):
        for table_name, col_name in to_autoinc:
            migrate_engine.execute("CREATE SEQUENCE %s_%s_seq"
                                   % (table_name, col_name))
            migrate_engine.execute("ALTER TABLE %s ALTER COLUMN %s SET DEFAULT nextval('%s_%s_seq'::regclass)"
                                   % (table_name, col_name, table_name, col_name))
            migrate_engine.execute("ALTER SEQUENCE %s_%s_seq OWNED BY %s.%s"
                                   % (table_name, col_name, table_name, col_name))
    else:
        for table_name, col_name in to_autoinc:
            table = metadata.tables[table_name]
            col = table.c[col_name]
            col.alter(autoincrement=True)

    # also drop the changes_nextid table here (which really should have been a
    # sequence..)
    table = sautils.Table('changes_nextid', metadata, autoload=True)
    table.drop()
