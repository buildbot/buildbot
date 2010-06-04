import sys

try:
    from pysqlite2 import dbapi2 as sqlite3
except ImportError:
    # don't use built-in sqlite3 on 2.5 -- it has *bad* bugs
    if sys.version_info >= (2,6):
        import sqlite3
    else:
        raise

def get_sqlite_memory_connection():
    return sqlite3.connect(":memory:")

class FakeDBSpec(object):
    def __init__(self, conn=None, pool=None):
        self.conn = conn
        self.pool = pool

    def get_dbapi(self):
        return sqlite3

    def get_sync_connection(self):
        return self.conn

    def get_async_connection_pool(self):
        assert self.pool, "fake DBSpec will only return a pool once"
        pool = self.pool
        self.pool = None
        return pool
