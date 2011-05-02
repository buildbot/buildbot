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

import time

from twisted.python import threadable, log
from twisted.application import internet, service
from buildbot.db import enginestrategy

from buildbot import util
from buildbot.util import collections as bbcollections
from buildbot.db import pool, model, changes, schedulers, sourcestamps
from buildbot.db import state, buildsets, buildrequests, builds

def str_or_none(s):
    if s is None:
        return None
    return str(s)

class Token: # used for _start_operation/_end_operation
    pass

from twisted.enterprise import adbapi
class TempAdbapiPool(adbapi.ConnectionPool):
    def __init__(self, engine):
        # this wants a module name, so give it one..
        adbapi.ConnectionPool.__init__(self, "buildbot.db.connector")
        self._engine = engine

    def connect(self):
        return self._engine.raw_connection()

    def stop(self):
        pass

class DBConnector(service.MultiService):
    """
    The connection between Buildbot and its backend database.  This is
    generally accessible as master.db, but is also used during upgrades.

    Most of the interesting operations available via the connector are
    implemented in connector components, available as attributes of this
    object, and listed below.
    """

    synchronized = ["_end_operation"] # TODO: remove
    MAX_QUERY_TIMES = 1000

    # Period, in seconds, of the cleanup task.  This master will perform
    # periodic cleanup actions on this schedule.
    CLEANUP_PERIOD = 3600

    def __init__(self, master, db_url, basedir):
        service.MultiService.__init__(self)
        self.master = master
        self.basedir = basedir
        "basedir for this master - used for upgrades"

        self._engine = enginestrategy.create_engine(db_url, basedir=self.basedir)
        self.pool = pool.DBThreadPool(self._engine)
        "thread pool (L{buildbot.db.pool.DBThreadPool}) for this db"

        self._oldpool = TempAdbapiPool(self._engine)

        self._sourcestamp_cache = util.LRUCache() # TODO: remove
        self._active_operations = set() # protected by synchronized= TODO: remove
        self._subscribers = bbcollections.defaultdict(set)

        self._started = False

        # set up components
        self.model = model.Model(self)
        "L{buildbot.db.model.Model} instance"

        self.changes = changes.ChangesConnectorComponent(self)
        "L{buildbot.db.changes.ChangesConnectorComponent} instance"

        self.schedulers = schedulers.SchedulersConnectorComponent(self)
        "L{buildbot.db.schedulers.ChangesConnectorComponent} instance"

        self.sourcestamps = sourcestamps.SourceStampsConnectorComponent(self)
        "L{buildbot.db.sourcestamps.SourceStampsConnectorComponent} instance"

        self.buildsets = buildsets.BuildsetsConnectorComponent(self)
        "L{buildbot.db.sourcestamps.BuildsetsConnectorComponent} instance"

        self.buildrequests = buildrequests.BuildRequestsConnectorComponent(self)
        "L{buildbot.db.sourcestamps.BuildRequestsConnectorComponent} instance"

        self.state = state.StateConnectorComponent(self)
        "L{buildbot.db.state.StateConnectorComponent} instance"

        self.builds = builds.BuildsConnectorComponent(self)
        "L{buildbot.db.builds.BuildsConnectorComponent} instance"

        self.cleanup_timer = internet.TimerService(self.CLEANUP_PERIOD, self.doCleanup)
        self.cleanup_timer.setServiceParent(self)

        self.changeHorizon = None # default value; set by master

    def start(self): # TODO: remove
        # this only *needs* to be called in reactorless environments (which
        # should be eliminated anyway).  but it doesn't hurt anyway
        self._oldpool.start()
        self._started = True

    def stop(self): # TODO: remove
        """Call this when you're done with me"""

        if not self._started:
            return
        self._oldpool.stop()
        self._started = False
        del self._oldpool

    def quoteq(self, query, returning=None): # TODO: remove
        """
        Given a query that contains qmark-style placeholders, like::
         INSERT INTO foo (col1, col2) VALUES (?,?)
        replace the '?' with '%s' if the backend uses format-style
        placeholders, like::
         INSERT INTO foo (col1, col2) VALUES (%s,%s)

        While there, append "RETURNING x" for backends that don't provide
        last row id (PostgreSQL and probably Oracle).
        """
        # PostgreSQL:
        # * doesn't return last row id, so we must append "RETURNING x"
        #   to queries where we want it and we must fetch it later,
        # PostgreSQL and MySQL:
        # * don't accept "?" in queries.
        if self._engine.dialect.name in ('postgres', 'postgresql', 'mysql'):
            query = query.replace("?", "%s")
        if self._engine.dialect.name in ('postgres', 'postgresql'):
            if returning:
                query += " RETURNING %s" % returning
        return query

    def lastrowid(self, t): # TODO: remove
        # PostgreSQL:
        # * fetch last row id from previously issued "RETURNING x" query.
        if self._engine.dialect.name in ('postgres', 'postgresql'):
            row = t.fetchone()
            if row:
                 return row[0]
            return -1

        # default
        return t.lastrowid

    def parmlist(self, count): # TODO: remove
        """
        When passing long lists of values to e.g., an INSERT query, it is
        tedious to pass long strings of ? placeholders.  This function will
        create a parenthesis-enclosed list of COUNT placeholders.  Note that
        the placeholders have already had quoteq() applied.
        """
        p = self.quoteq("?")
        return "(" + ",".join([p]*count) + ")"

    def runQueryNow(self, *args, **kwargs): # TODO: remove
        # synchronous+blocking version of runQuery()
        assert self._started
        return self.runInteractionNow(self._runQuery, *args, **kwargs)

    def _runQuery(self, c, *args, **kwargs):
        c.execute(*args, **kwargs)
        return c.fetchall()

    # TODO: remove
    def _start_operation(self):
        t = Token()
        self._active_operations.add(t)
        return t
    def _end_operation(self, t):
        # this is always invoked from the main thread, but is wrapped by
        # synchronized= and threadable.synchronous() for no particular reason
        # now that notifications are removed
        self._active_operations.discard(t)
        if self._active_operations:
            return

    def runInteractionNow(self, interaction, *args, **kwargs): # TODO: remove
        # synchronous+blocking version of runInteraction()
        assert self._started
        t = self._start_operation()
        try:
            return self._runInteractionNow(interaction, *args, **kwargs)
        finally:
            self._end_operation(t)

    def _runInteractionNow(self, interaction, *args, **kwargs): # TODO: remove
        conn = self._engine.raw_connection()
        c = conn.cursor()
        result = interaction(c, *args, **kwargs)
        c.close()
        conn.commit()
        return result

    def runQuery(self, *args, **kwargs): # TODO: remove
        assert self._started
        d = self._oldpool.runQuery(*args, **kwargs)
        return d

    def _runQuery_done(self, res, start, t): # TODO: remove
        self._end_operation(t)
        return res

    def runInteraction(self, *args, **kwargs): # TODO: remove
        assert self._started
        start = time.time()
        t = self._start_operation()
        d = self._oldpool.runInteraction(*args, **kwargs)
        d.addBoth(self._runInteraction_done, start, t)
        return d
    def _runInteraction_done(self, res, start, t): # TODO: remove
        self._end_operation(t)
        return res

    def doCleanup(self):
        """
        Perform any periodic database cleanup tasks.

        @returns: Deferred
        """
        d = self.changes.pruneChanges(self.changeHorizon)
        d.addErrback(log.err, 'while pruning changes')
        return d

threadable.synchronize(DBConnector)
