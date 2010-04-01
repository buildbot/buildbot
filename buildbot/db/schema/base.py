class Upgrader(object):

    def __init__(self, dbapi, conn, basedir, quiet=False):
        self.dbapi = dbapi
        self.conn = conn
        self.basedir = basedir
        self.quiet = quiet

        self.dbapiName = dbapi.__name__

    def upgrade(self):
        raise NotImplementedError
