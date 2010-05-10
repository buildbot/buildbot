from buildbot.db.schema import base
from buildbot.db.exceptions import DatabaseNotReadyError

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
