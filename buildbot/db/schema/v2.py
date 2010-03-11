import os

from buildbot.db import util
from buildbot.db.schema import base

class Upgrader(base.Upgrader):
    def upgrade(self):
        self.add_columns()
        self.set_version()

    def add_columns(self):
        cursor = self.conn.cursor()
        cursor.execute("""
        ALTER TABLE changes
            add column `repository` text not null default ''
        """)
        cursor.execute("""
        ALTER TABLE changes
            add column `project` text not null default ''
        """)
        cursor.execute("""
        ALTER TABLE sourcestamps
            add column `repository` text not null default ''
        """)
        cursor.execute("""
        ALTER TABLE sourcestamps
            add column `project` text not null default ''
        """)

    def set_version(self):
        c = self.conn.cursor()
        c.execute("""UPDATE version set version = 2 where version = 1""")
