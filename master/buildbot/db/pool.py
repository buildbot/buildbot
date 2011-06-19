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

import os
import sqlalchemy as sa
import twisted
from twisted.internet import reactor, threads, defer, task
from twisted.python import threadpool, failure, versions, log

# Hack for bug #1992.  In as-yet-unknown circumstances, select() fails to
# notice that a selfpipe has been written to, thus causing callFromThread, as
# used in deferToThreadPool, to hang indefinitely.  The workaround is to wake
# up the select loop every second by ensuring that there is an event occuring
# every second, with this busy loop:
def bug1992hack(f):
    def w(*args, **kwargs):
        busyloop = task.LoopingCall(lambda : None)
        busyloop.start(1)
        d = f(*args, **kwargs)
        def stop_loop(r):
            busyloop.stop()
            return r
        d.addBoth(stop_loop)
        return d
    w.__name__ = f.__name__
    w.__doc__ = f.__doc__
    return w


class DBThreadPool(threadpool.ThreadPool):
    """
    A pool of threads ready and waiting to execute queries.

    If the engine has an C{optimal_thread_pool_size} attribute, then the
    maxthreads of the thread pool will be set to that value.  This is most
    useful for SQLite in-memory connections, where exactly one connection
    (and thus thread) should be used.
    """

    running = False

    # Some versions of SQLite incorrectly cache metadata about which tables are
    # and are not present on a per-connection basis.  This cache can be flushed
    # by querying the sqlite_master table.  We currently assume all versions of
    # SQLite have this bug, although it has only been observed in 3.4.2.  A
    # dynamic check for this bug would be more appropriate.  This is documented
    # in bug #1810.
    __broken_sqlite = False

    def __init__(self, engine):
        pool_size = 5
        if hasattr(engine, 'optimal_thread_pool_size'):
            pool_size = engine.optimal_thread_pool_size
        threadpool.ThreadPool.__init__(self,
                        minthreads=1,
                        maxthreads=pool_size,
                        name='DBThreadPool')
        self.engine = engine
        if engine.dialect.name == 'sqlite':
            log.msg("applying SQLite workaround from Buildbot bug #1810")
            self.__broken_sqlite = self.detect_bug1810()
        self._start_evt = reactor.callWhenRunning(self._start)

    def _start(self):
        self._start_evt = None
        if not self.running:
            self.start()
            self._stop_evt = reactor.addSystemEventTrigger(
                    'during', 'shutdown', self._stop)
            self.running = True

    def _stop(self):
        self._stop_evt = None
        self.stop()
        self.engine.dispose()
        self.running = False

    def shutdown(self):
        """Manually stop the pool.  This is only necessary from tests, as the
        pool will stop itself when the reactor stops under normal
        circumstances."""
        if not self._stop_evt:
            return # pool is already stopped
        reactor.removeSystemEventTrigger(self._stop_evt)
        self._stop()

    @bug1992hack
    def do(self, callable, *args, **kwargs):
        """
        Call C{callable} in a thread, with a Connection as first argument.
        Returns a deferred that will indicate the results of the callable.

        Note: do not return any SQLAlchemy objects via this deferred!
        """
        def thd():
            conn = self.engine.contextual_connect()
            if self.__broken_sqlite: # see bug #1810
                conn.execute("select * from sqlite_master")
            try:
                rv = callable(conn, *args, **kwargs)
                assert not isinstance(rv, sa.engine.ResultProxy), \
                        "do not return ResultProxy objects!"
            finally:
                conn.close()
            return rv
        return threads.deferToThreadPool(reactor, self, thd)

    @bug1992hack
    def do_with_engine(self, callable, *args, **kwargs):
        """
        Like L{do}, but with an SQLAlchemy Engine as the first argument.  This
        is only used for schema manipulation, and is not used at master
        runtime.
        """
        def thd():
            if self.__broken_sqlite: # see bug #1810
                self.engine.execute("select * from sqlite_master")
            rv = callable(self.engine, *args, **kwargs)
            assert not isinstance(rv, sa.engine.ResultProxy), \
                    "do not return ResultProxy objects!"
            return rv
        return threads.deferToThreadPool(reactor, self, thd)

    # older implementations for twisted < 0.8.2, which does not have
    # deferToThreadPool; this basically re-implements it, although it gets some
    # of the synchronization wrong - the thread may still be "in use" when the
    # deferred fires in the parent, which can lead to database accesses hopping
    # between threads.  In practice, this should not cause any difficulty.
    @bug1992hack
    def do_081(self, callable, *args, **kwargs): # pragma: no cover
        d = defer.Deferred()
        def thd():
            try:
                conn = self.engine.contextual_connect()
                if self.__broken_sqlite: # see bug #1810
                    conn.execute("select * from sqlite_master")
                try:
                    rv = callable(conn, *args, **kwargs)
                    assert not isinstance(rv, sa.engine.ResultProxy), \
                            "do not return ResultProxy objects!"
                finally:
                    conn.close()
                reactor.callFromThread(d.callback, rv)
            except:
                reactor.callFromThread(d.errback, failure.Failure())
        self.callInThread(thd)
        return d

    @bug1992hack
    def do_with_engine_081(self, callable, *args, **kwargs): # pragma: no cover
        d = defer.Deferred()
        def thd():
            try:
                conn = self.engine
                if self.__broken_sqlite: # see bug #1810
                    conn.execute("select * from sqlite_master")
                rv = callable(conn, *args, **kwargs)
                assert not isinstance(rv, sa.engine.ResultProxy), \
                        "do not return ResultProxy objects!"
                reactor.callFromThread(d.callback, rv)
            except:
                reactor.callFromThread(d.errback, failure.Failure())
        self.callInThread(thd)
        return d
    if twisted.version < versions.Version('twisted', 8, 2, 0):
        do = do_081
        do_with_engine = do_with_engine_081

    def detect_bug1810(self):
        # detect buggy SQLite implementations; call only for a known-sqlite
        # dialect
        try:
            import pysqlite2.dbapi2 as sqlite
            sqlite = sqlite
        except ImportError:
            import sqlite3 as sqlite

        dbfile = "detect_bug1810.db"
        def test(select_from_sqlite_master=False):
            try:
                conn1 = sqlite.connect(dbfile)
                curs1 = conn1.cursor()
                curs1.execute("PRAGMA table_info('foo')")

                conn2 = sqlite.connect(dbfile)
                curs2 = conn2.cursor()
                curs2.execute("CREATE TABLE foo ( a integer )")

                if select_from_sqlite_master:
                    curs1.execute("SELECT * from sqlite_master")
                curs1.execute("SELECT * from foo")
            finally:
                conn1.close()
                conn2.close()
                os.unlink(dbfile)

        try:
            test()
        except sqlite.OperationalError:
            # this is the expected error indicating it's broken
            return True

        # but this version should not fail..
        test(select_from_sqlite_master=True)
        return False # not broken - no workaround required
