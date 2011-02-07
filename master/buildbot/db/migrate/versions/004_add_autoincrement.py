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

    # re-include some of the relevant tables, as they were in version 3, since
    # sqlalchemy's reflection doesn't work very well for defaults

    sa.Table("schedulers", metadata,
        sa.Column('schedulerid', sa.Integer, autoincrement=False, primary_key=True),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('state', sa.String(1024), nullable=False),
        sa.Column('class_name', sa.Text, nullable=False, server_default=sa.DefaultClause(''))
    )

    sa.Table('changes', metadata,
        sa.Column('changeid', sa.Integer, autoincrement=False, primary_key=True),
        sa.Column('author', sa.String(1024), nullable=False),
        sa.Column('comments', sa.String(1024), nullable=False),
        sa.Column('is_dir', sa.SmallInteger, nullable=False),
        sa.Column('branch', sa.String(1024)),
        sa.Column('revision', sa.String(256)),
        sa.Column('revlink', sa.String(256)),
        sa.Column('when_timestamp', sa.Integer, nullable=False),
        sa.Column('category', sa.String(256)),
        sa.Column('repository', sa.Text, nullable=False, server_default=sa.DefaultClause('')),
        sa.Column('project', sa.Text, nullable=False, server_default=sa.DefaultClause('')),
    )

    sa.Table('sourcestamps', metadata,
        sa.Column('id', sa.Integer, autoincrement=False, primary_key=True),
        sa.Column('branch', sa.String(256)),
        sa.Column('revision', sa.String(256)),
        sa.Column('patchid', sa.Integer, sa.ForeignKey('patches.id')),
        sa.Column('repository', sa.Text, nullable=False, server_default=''),
        sa.Column('project', sa.Text, nullable=False, server_default=''),
    )

    to_autoinc = [ s.split(".") for s in
        "schedulers.schedulerid",
        "builds.id",
        "changes.changeid",
        "buildrequests.id",
        "buildsets.id",
        "patches.id",
        "sourcestamps.id",
    ]

    # It seems that SQLAlchemy's ALTER TABLE doesn't work when migrating from
    # INTEGER to PostgreSQL's SERIAL data type (which is just pseudo data type
    # for INTEGER with SEQUENCE), so we have to work-around this with raw SQL.
    if str(migrate_engine.dialect).startswith("<sqlalchemy.dialects.postgresql"):
        for table_name, col_name in to_autoinc:
            migrate_engine.execute("CREATE SEQUENCE %s_%s_seq"
                                   % (table_name, col_name))
            migrate_engine.execute("ALTER TABLE %s ALTER COLUMN %s SET DEFAULT nextval('%s_%s_seq'::regclass)"
                                   % (table_name, col_name, table_name, col_name))
            migrate_engine.execute("ALTER SEQUENCE %s_%s_seq OWNED BY %s.%s"
                                   % (table_name, col_name, table_name, col_name))
    else:
        for table_name, col_name in to_autoinc:
            table = sa.Table(table_name, metadata, autoload=True)
            col = table.c[col_name]
            col.alter(autoincrement=True)


    # also drop the changes_nextid table here (which really should have been a
    # sequence..)
    table = sa.Table('changes_nextid', metadata, autoload=True)
    table.drop()
