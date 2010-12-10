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
        self.migrate_schedulers()
        self.set_version()

    def migrate_schedulers(self):
        cursor = self.conn.cursor()
        # If this fails, there's no cleaning up to do
        cursor.execute("""
            ALTER TABLE schedulers
                RENAME TO schedulers_old
        """)

        try:
            cursor.execute("""
                CREATE TABLE schedulers (
                    `schedulerid` INTEGER PRIMARY KEY, -- joins to other tables
                    `name` VARCHAR(127) NOT NULL, -- the scheduler's name according to master.cfg
                    `class_name` VARCHAR(127) NOT NULL, -- the scheduler's class
                    `state` VARCHAR(1024) NOT NULL -- JSON-encoded state dictionary
                );
            """)
        except:
            # Restore the original table
            cursor.execute("""
                ALTER TABLE schedulers_old
                    RENAME TO schedulers
            """)
            raise

        try:
            cursor.execute("""
                CREATE UNIQUE INDEX `name_and_class` ON
                    schedulers (`name`, `class_name`)
            """)

            cursor.execute("""
                INSERT INTO schedulers (`schedulerid`, `name`, `state`, `class_name`)
                    SELECT `schedulerid`, `name`, `state`, '' FROM schedulers_old
            """)
            cursor.execute("""
                DROP TABLE schedulers_old
            """)
        except:
            # Clean up the new table, and restore the original
            cursor.execute("""
                DROP TABLE schedulers
            """)
            cursor.execute("""
                ALTER TABLE schedulers_old
                    RENAME TO schedulers
            """)
            raise

    def set_version(self):
        c = self.conn.cursor()
        c.execute("""UPDATE version set version = 3 where version = 2""")
