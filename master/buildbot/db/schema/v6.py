from buildbot.db.schema import base

class Upgrader(base.Upgrader):
    def upgrade(self):
        cursor = self.conn.cursor()
        cursor.execute("DROP table last_access")
        cursor.execute("""UPDATE version set version = 6 where version = 5""")

