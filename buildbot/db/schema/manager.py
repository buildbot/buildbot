from twisted.python import reflect

# note that schema modules are not loaded unless an upgrade is taking place

CURRENT_VERSION = 4

class DBSchemaManager(object):
    """
    This class is responsible for managing the database schema and upgrading it
    as necessary.  This includes both the *actual* database and the old pickle
    database, as migrations move data between the two.

    Note that this class is *entirely synchronous*!  Performing any other operations
    while changing the schema is just asking for trouble.
    """
    def __init__(self, spec, basedir):
        self.spec = spec
        self.basedir = basedir
        self.dbapi = self.spec.get_dbapi()
        self.conn = self.spec.get_sync_connection()

    def get_db_version(self):
        """
        Get the current schema version for this database
        """
        c = self.conn.cursor()
        try:
            c.execute("SELECT version FROM version")
            rows = c.fetchall()
            assert len(rows) == 1, "%i rows in version table! (should only be 1)" % len(rows)
            return rows[0][0]
        except (self.dbapi.OperationalError, self.dbapi.ProgrammingError):
            # no version table = version 0
            return 0

    def get_current_version(self):
        """
        Get the current db version for this release of buildbot
        """
        return CURRENT_VERSION

    def is_current(self):
        """
        Is this database current?
        """
        return self.get_db_version() == self.get_current_version()

    def upgrade(self, quiet=False):
        """
        Upgrade this database to the current version
        """
        while self.get_db_version() < self.get_current_version():
            next_version = self.get_db_version() + 1
            next_version_module = reflect.namedModule("buildbot.db.schema.v%d" % next_version)
            upg = next_version_module.Upgrader(self.dbapi, self.conn, self.basedir, quiet)
            upg.upgrade()
            self.conn.commit()
            assert self.get_db_version() == next_version
