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

from buildbot.db.schema import base

class Upgrader(base.Upgrader):
    def upgrade(self):
        self.add_index("buildrequests", "buildsetid")
        self.add_index("buildrequests", "buildername", 255)
        self.add_index("buildrequests", "complete")
        self.add_index("buildrequests", "claimed_at")
        self.add_index("buildrequests", "claimed_by_name", 255)

        self.add_index("builds", "number")
        self.add_index("builds", "brid")

        self.add_index("buildsets", "complete")
        self.add_index("buildsets", "submitted_at")

        self.add_index("buildset_properties", "buildsetid")

        self.add_index("changes", "branch", 255)
        self.add_index("changes", "revision", 255)
        self.add_index("changes", "author", 255)
        self.add_index("changes", "category", 255)
        self.add_index("changes", "when_timestamp")

        self.add_index("change_files", "changeid")
        self.add_index("change_links", "changeid")
        self.add_index("change_properties", "changeid")

        # schedulers already has an index

        self.add_index("scheduler_changes", "schedulerid")
        self.add_index("scheduler_changes", "changeid")

        self.add_index("scheduler_upstream_buildsets", "buildsetid")
        self.add_index("scheduler_upstream_buildsets", "schedulerid")
        self.add_index("scheduler_upstream_buildsets", "active")

        # sourcestamps are only queried by id, no need for additional indexes

        self.add_index("sourcestamp_changes", "sourcestampid")

        self.set_version()

    def add_index(self, table, column, length=None):
        lengthstr=""
        if length is not None and self.dbapiName == 'MySQLdb':
            lengthstr = " (%i)" % length
        q = "CREATE INDEX `%(table)s_%(column)s` ON `%(table)s` (`%(column)s`%(lengthstr)s)"
        cursor = self.conn.cursor()
        cursor.execute(q % {'table': table, 'column': column, 'lengthstr': lengthstr})

    def set_version(self):
        c = self.conn.cursor()
        c.execute("""UPDATE version set version = 5 where version = 4""")
