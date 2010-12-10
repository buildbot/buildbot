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
        self.add_columns()
        self.set_version()

    def add_columns(self):
        if self.dbapiName == 'MySQLdb':
            default_text = ""
        else:
            default_text = "default ''"

        cursor = self.conn.cursor()
        cursor.execute("""
        ALTER TABLE changes
            add column `repository` text not null %s
        """ % default_text)
        cursor.execute("""
        ALTER TABLE changes
            add column `project` text not null %s
        """ % default_text)
        cursor.execute("""
        ALTER TABLE sourcestamps
            add column `repository` text not null %s
        """ % default_text)
        cursor.execute("""
        ALTER TABLE sourcestamps
            add column `project` text not null %s
        """ % default_text)

    def set_version(self):
        c = self.conn.cursor()
        c.execute("""UPDATE version set version = 2 where version = 1""")
