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
    metadata.reflect()

    def add_index(table_name, col_name):
        idx_name = "%s_%s" % (table_name, col_name)
        idx = sa.Index(idx_name, metadata.tables[table_name].c[col_name])
        idx.create(migrate_engine)
    add_index("buildrequests", "buildsetid")
    add_index("buildrequests", "buildername")
    add_index("buildrequests", "complete")
    add_index("buildrequests", "claimed_at")
    add_index("buildrequests", "claimed_by_name")

    add_index("builds", "number")
    add_index("builds", "brid")

    add_index("buildsets", "complete")
    add_index("buildsets", "submitted_at")

    add_index("buildset_properties", "buildsetid")

    add_index("changes", "branch")
    add_index("changes", "revision")
    add_index("changes", "author")
    add_index("changes", "category")
    add_index("changes", "when_timestamp")

    add_index("change_files", "changeid")
    add_index("change_links", "changeid")
    add_index("change_properties", "changeid")

    # schedulers already has an index

    add_index("scheduler_changes", "schedulerid")
    add_index("scheduler_changes", "changeid")

    add_index("scheduler_upstream_buildsets", "buildsetid")
    add_index("scheduler_upstream_buildsets", "schedulerid")
    add_index("scheduler_upstream_buildsets", "active")

    # sourcestamps are only queried by id, no need for additional indexes

    add_index("sourcestamp_changes", "sourcestampid")
