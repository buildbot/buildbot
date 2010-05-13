from buildbot.db.schema import base
from buildbot.db.exceptions import DatabaseNotReadyError

class Upgrader(base.Upgrader):
    def upgrade(self):
        self.migrate_buildrequests()
        self.migrate_builds()
        self.migrate_buildsets()
        self.migrate_changes()
        self.migrate_patches()
        self.migrate_sourcestamps()
        self.migrate_schedulers()
        self.set_version()

    def makeAutoincColumn(self, name):
        if self.dbapiName == 'MySQLdb':
            return "`%s` INTEGER PRIMARY KEY AUTO_INCREMENT" % name
        elif self.dbapiName in ('sqlite3', 'pysqlite2.dbapi2'):
            return "`%s` INTEGER PRIMARY KEY AUTOINCREMENT" % name
        raise ValueError("Unsupported dbapi: %s" % self.dbapiName)

    def migrate_table(self, table_name, schema):
        old_name = "%s_old" % table_name
        cursor = self.conn.cursor()
        # If this fails, there's no cleaning up to do
        cursor.execute("""
            ALTER TABLE %(table_name)s
                RENAME TO %(old_name)s
        """ % locals())

        try:
            cursor.execute(schema)
        except:
            # Restore the original table
            cursor.execute("""
                ALTER TABLE %(old_name)s
                    RENAME TO %(table_name)s
            """ % locals())
            raise

        try:
            cursor.execute("""
                INSERT INTO %(table_name)s
                    SELECT * FROM %(old_name)s
            """ % locals())
            cursor.execute("""
                DROP TABLE %(old_name)s
            """ % locals())
        except:
            # Clean up the new table, and restore the original
            cursor.execute("""
                DROP TABLE %(table_name)s
            """ % locals())
            cursor.execute("""
                ALTER TABLE %(old_name)s
                    RENAME TO %(table_name)s
            """ % locals())
            raise

    def set_version(self):
        c = self.conn.cursor()
        c.execute("""UPDATE version set version = 4 where version = 3""")

    def migrate_schedulers(self):
        schedulerid_col = self.makeAutoincColumn('schedulerid')
        schema = """
            CREATE TABLE schedulers (
                %(schedulerid_col)s, -- joins to other tables
                `name` VARCHAR(100) NOT NULL, -- the scheduler's name according to master.cfg
                `class_name` VARCHAR(100) NOT NULL, -- the scheduler's class
                `state` VARCHAR(1024) NOT NULL -- JSON-encoded state dictionary
            );
        """ % locals()
        self.migrate_table('schedulers', schema)

        # Fix up indices
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE UNIQUE INDEX `name_and_class` ON
                schedulers (`name`, `class_name`)
        """)

    def migrate_builds(self):
        buildid_col = self.makeAutoincColumn('id')
        schema = """
            CREATE TABLE builds (
                %(buildid_col)s,
                `number` INTEGER NOT NULL, -- BuilderStatus.getBuild(number)
                -- 'number' is scoped to both the local buildmaster and the buildername
                `brid` INTEGER NOT NULL, -- matches buildrequests.id
                `start_time` INTEGER NOT NULL,
                `finish_time` INTEGER
            );
        """ % locals()
        self.migrate_table('builds', schema)

    def migrate_changes(self):
        changeid_col = self.makeAutoincColumn('changeid')
        schema = """
            CREATE TABLE changes (
                %(changeid_col)s, -- also serves as 'change number'
                `author` VARCHAR(1024) NOT NULL,
                `comments` VARCHAR(1024) NOT NULL, -- too short?
                `is_dir` SMALLINT NOT NULL, -- old, for CVS
                `branch` VARCHAR(1024) NULL,
                `revision` VARCHAR(256), -- CVS uses NULL. too short for darcs?
                `revlink` VARCHAR(256) NULL,
                `when_timestamp` INTEGER NOT NULL, -- copied from incoming Change
                `category` VARCHAR(256) NULL,

                -- repository specifies, along with revision and branch, the
                -- source tree in which this change was detected.
                `repository` TEXT NOT NULL default '',

                -- project names the project this source code represents.  It is used
                -- later to filter changes
                `project` TEXT NOT NULL default ''
            );
        """ % locals()
        self.migrate_table('changes', schema)

        # Drop changes_nextid columnt
        cursor = self.conn.cursor()
        cursor.execute("DROP TABLE changes_nextid")

    def migrate_buildrequests(self):
        buildrequestid_col = self.makeAutoincColumn('id')
        schema = """
            CREATE TABLE buildrequests (
                %(buildrequestid_col)s,

                -- every BuildRequest has a BuildSet
                -- the sourcestampid and reason live in the BuildSet
                `buildsetid` INTEGER NOT NULL,

                `buildername` VARCHAR(256) NOT NULL,

                `priority` INTEGER NOT NULL default 0,

                -- claimed_at is the time at which a master most recently asserted that
                -- it is responsible for running the build: this will be updated
                -- periodically to maintain the claim
                `claimed_at` INTEGER default 0,

                -- claimed_by indicates which buildmaster has claimed this request. The
                -- 'name' contains hostname/basedir, and will be the same for subsequent
                -- runs of any given buildmaster. The 'incarnation' contains bootime/pid,
                -- and will be different for subsequent runs. This allows each buildmaster
                -- to distinguish their current claims, their old claims, and the claims
                -- of other buildmasters, to treat them each appropriately.
                `claimed_by_name` VARCHAR(256) default NULL,
                `claimed_by_incarnation` VARCHAR(256) default NULL,

                `complete` INTEGER default 0, -- complete=0 means 'pending'

                 -- results is only valid when complete==1
                `results` SMALLINT, -- 0=SUCCESS,1=WARNINGS,etc, from status/builder.py

                `submitted_at` INTEGER NOT NULL,

                `complete_at` INTEGER
            );
        """ % locals()
        self.migrate_table('buildrequests', schema)

    def migrate_buildsets(self):
        buildsetsid_col = self.makeAutoincColumn('id')
        schema = """
            CREATE TABLE buildsets (
                %(buildsetsid_col)s,
                `external_idstring` VARCHAR(256),
                `reason` VARCHAR(256),
                `sourcestampid` INTEGER NOT NULL,
                `submitted_at` INTEGER NOT NULL,
                `complete` SMALLINT NOT NULL default 0,
                `complete_at` INTEGER,
                `results` SMALLINT -- 0=SUCCESS,2=FAILURE, from status/builder.py
                 -- results is NULL until complete==1
            );
        """ % locals()
        self.migrate_table("buildsets", schema)

    def migrate_patches(self):
        patchesid_col = self.makeAutoincColumn('id')
        schema = """
            CREATE TABLE patches (
                %(patchesid_col)s,
                `patchlevel` INTEGER NOT NULL,
                `patch_base64` TEXT NOT NULL, -- encoded bytestring
                `subdir` TEXT -- usually NULL
            );
        """ % locals()
        self.migrate_table("patches", schema)

    def migrate_sourcestamps(self):
        sourcestampsid_col = self.makeAutoincColumn('id')
        schema = """
            CREATE TABLE sourcestamps (
                %(sourcestampsid_col)s,
                `branch` VARCHAR(256) default NULL,
                `revision` VARCHAR(256) default NULL,
                `patchid` INTEGER default NULL,
                `repository` TEXT not null default '',
                `project` TEXT not null default ''
            );
        """ % locals()
        self.migrate_table("sourcestamps", schema)
