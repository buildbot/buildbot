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

    # note that all of the tables defined here omit the ForeignKey constraints;
    # this just lets this code specify the tables in any order; the tables are
    # not re-created here, so this omission causes no problems - the key
    # constraints are still defined in the table

    def add_index(table_name, col_name):
        idx_name = "%s_%s" % (table_name, col_name)
        idx = sa.Index(idx_name, metadata.tables[table_name].c[col_name])
        idx.create(migrate_engine)

    sautils.Table('buildrequests', metadata,
                  sa.Column('id', sa.Integer, primary_key=True),
                  sa.Column('buildsetid', sa.Integer, nullable=False),
                  sa.Column('buildername', sa.String(length=None), nullable=False),
                  sa.Column('priority', sa.Integer, nullable=False),
                  sa.Column('claimed_at', sa.Integer, server_default=sa.DefaultClause("0")),
                  sa.Column('claimed_by_name', sa.String(length=None)),
                  sa.Column('claimed_by_incarnation', sa.String(length=None)),
                  sa.Column('complete', sa.Integer, server_default=sa.DefaultClause("0")),
                  sa.Column('results', sa.SmallInteger),
                  sa.Column('submitted_at', sa.Integer, nullable=False),
                  sa.Column('complete_at', sa.Integer),
                  )
    add_index("buildrequests", "buildsetid")
    add_index("buildrequests", "buildername")
    add_index("buildrequests", "complete")
    add_index("buildrequests", "claimed_at")
    add_index("buildrequests", "claimed_by_name")

    sautils.Table('builds', metadata,
                  sa.Column('id', sa.Integer, primary_key=True),
                  sa.Column('number', sa.Integer, nullable=False),
                  sa.Column('brid', sa.Integer, nullable=False),
                  sa.Column('start_time', sa.Integer, nullable=False),
                  sa.Column('finish_time', sa.Integer),
                  )
    add_index("builds", "number")
    add_index("builds", "brid")

    sautils.Table('buildsets', metadata,
                  sa.Column('id', sa.Integer, primary_key=True),
                  sa.Column('external_idstring', sa.String(256)),
                  sa.Column('reason', sa.String(256)),
                  sa.Column('sourcestampid', sa.Integer, nullable=False),
                  sa.Column('submitted_at', sa.Integer, nullable=False),
                  sa.Column('complete', sa.SmallInteger, nullable=False, server_default=sa.DefaultClause("0")),
                  sa.Column('complete_at', sa.Integer),
                  sa.Column('results', sa.SmallInteger),
                  )
    add_index("buildsets", "complete")
    add_index("buildsets", "submitted_at")

    sautils.Table('buildset_properties', metadata,
                  sa.Column('buildsetid', sa.Integer, nullable=False),
                  sa.Column('property_name', sa.String(256), nullable=False),
                  sa.Column('property_value', sa.String(1024), nullable=False),
                  )
    add_index("buildset_properties", "buildsetid")

    sautils.Table('changes', metadata,
                  sa.Column('changeid', sa.Integer, primary_key=True),
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
    add_index("changes", "branch")
    add_index("changes", "revision")
    add_index("changes", "author")
    add_index("changes", "category")
    add_index("changes", "when_timestamp")

    sautils.Table('change_files', metadata,
                  sa.Column('changeid', sa.Integer, nullable=False),
                  sa.Column('filename', sa.String(1024), nullable=False),
                  )
    add_index("change_files", "changeid")

    sautils.Table('change_links', metadata,
                  sa.Column('changeid', sa.Integer, nullable=False),
                  sa.Column('link', sa.String(1024), nullable=False),
                  )
    add_index("change_links", "changeid")

    sautils.Table('change_properties', metadata,
                  sa.Column('changeid', sa.Integer, nullable=False),
                  sa.Column('property_name', sa.String(256), nullable=False),
                  sa.Column('property_value', sa.String(1024), nullable=False),
                  )
    add_index("change_properties", "changeid")

    # schedulers already has an index

    sautils.Table('scheduler_changes', metadata,
                  sa.Column('schedulerid', sa.Integer),
                  sa.Column('changeid', sa.Integer),
                  sa.Column('important', sa.SmallInteger),
                  )
    add_index("scheduler_changes", "schedulerid")
    add_index("scheduler_changes", "changeid")

    sautils.Table('scheduler_upstream_buildsets', metadata,
                  sa.Column('buildsetid', sa.Integer),
                  sa.Column('schedulerid', sa.Integer),
                  sa.Column('active', sa.SmallInteger),
                  )
    add_index("scheduler_upstream_buildsets", "buildsetid")
    add_index("scheduler_upstream_buildsets", "schedulerid")
    add_index("scheduler_upstream_buildsets", "active")

    # sourcestamps are only queried by id, no need for additional indexes

    sautils.Table('sourcestamp_changes', metadata,
                  sa.Column('sourcestampid', sa.Integer, nullable=False),
                  sa.Column('changeid', sa.Integer, nullable=False),
                  )
    add_index("sourcestamp_changes", "sourcestampid")
