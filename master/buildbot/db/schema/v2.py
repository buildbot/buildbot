
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
