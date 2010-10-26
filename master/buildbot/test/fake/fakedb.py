import sys, time

from twisted.internet import defer

try:
    from pysqlite2 import dbapi2 as sqlite3
    assert sqlite3
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

###
# Note, this isn't fully equivalent to a real db connection object
# transactions aren't emulated, scheduler state is hacked, and some methods
# are missing or are just stubbed out.
###
class FakeDBConn:
    def __init__(self):
        self.schedulers = []
        self.changes = []
        self.sourcestamps = []
        self.scheduler_states = {}
        self.classified_changes = {}

    def addSchedulers(self, schedulers):
        i = len(self.schedulers)
        for s in schedulers:
            self.schedulers.append(s)
            s.schedulerid = i
            i += 1
        return defer.succeed(True)

    def addChangeToDatabase(self, change):
        i = len(self.changes)
        self.changes.append(change)
        change.number = i

    def get_sourcestampid(self, ss, t):
        i = len(self.sourcestamps)
        self.sourcestamps.append(ss)
        ss.ssid = ss
        return i

    def runInteraction(self, f, *args):
        return f(None, *args)

    def scheduler_get_state(self, schedulerid, t):
        return self.scheduler_states.get(schedulerid, {"last_processed": 0, "last_build": time.time()+100})

    def scheduler_set_state(self, schedulerid, t, state):
        self.scheduler_states[schedulerid] = state

    def getLatestChangeNumberNow(self, t):
        return len(self.changes)-1

    def getChangesGreaterThan(self, last_changeid, t):
        return self.changes[last_changeid:]

    def scheduler_get_classified_changes(self, schedulerid, t):
        return self.classified_changes.get(schedulerid, ([], []))

    def scheduler_classify_change(self, schedulerid, changeid, important, t):
        if schedulerid not in self.classified_changes:
            self.classified_changes[schedulerid] = ([], [])

        if important:
            self.classified_changes[schedulerid][0].append(self.changes[changeid])
        else:
            self.classified_changes[schedulerid][1].append(self.changes[changeid])

    def scheduler_retire_changes(self, schedulerid, changeids, t):
        if schedulerid not in self.classified_changes:
            return
        for c in self.classified_changes[schedulerid][0][:]:
            if c.number in changeids:
                self.classified_changes[schedulerid][0].remove(c)
        for c in self.classified_changes[schedulerid][1][:]:
            if c.number in changeids:
                self.classified_changes[schedulerid][1].remove(c)

    def create_buildset(self, *args):
        pass

