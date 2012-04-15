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
import traceback
import inspect
import shutil
import os
import sqlalchemy as sa
import tempfile
from buildbot.process import metrics
from twisted.internet import reactor, threads
from twisted.python import threadpool, log

# set this to True for *very* verbose query debugging output; this can
# be monkey-patched from master.cfg, too:
#     from buildbot.db import pool
#     pool.debug = True
debug = False
_debug_id = 1

def timed_do_fn(f):
    """Decorate a do function to log before, after, and elapsed time,
    with the name of the calling function.  This is not speedy!"""
    def wrap(callable, *args, **kwargs):
        global _debug_id

        # get a description of the function that called us
        st = traceback.extract_stack(limit=2)
        file, line, name, _ = st[0]

        # and its locals
        frame = inspect.currentframe(1)
        locals = frame.f_locals

        # invent a unique ID for the description
        id, _debug_id = _debug_id, _debug_id+1

        descr = "%s-%08x" % (name, id)

        start_time = time.time()
        log.msg("%s - before ('%s' line %d)" % (descr, file, line))
        for name in locals:
            if name in ('self', 'thd'):
                continue
            log.msg("%s -   %s = %r" % (descr, name, locals[name]))

        # wrap the callable to log the begin and end of the actual thread
        # function
        def callable_wrap(*args, **kargs):
            log.msg("%s - thd start" % (descr,))
            try:
                return callable(*args, **kwargs)
            finally:
                log.msg("%s - thd end" % (descr,))
        d = f(callable_wrap, *args, **kwargs)

        def after(x):
            end_time = time.time()
            elapsed = (end_time - start_time) * 1000
            log.msg("%s - after (%0.2f ms elapsed)" % (descr, elapsed))
            return x
        d.addBoth(after)
        return d
    wrap.__name__ = f.__name__
    wrap.__doc__ = f.__doc__
    return wrap

class DBThreadPool(threadpool.ThreadPool):

    running = False

    # Some versions of SQLite incorrectly cache metadata about which tables are
    # and are not present on a per-connection basis.  This cache can be flushed
    # by querying the sqlite_master table.  We currently assume all versions of
    # SQLite have this bug, although it has only been observed in 3.4.2.  A
    # dynamic check for this bug would be more appropriate.  This is documented
    # in bug #1810.
    __broken_sqlite = False

    def __init__(self, engine, verbose=False):
        # verbose is used by upgrade scripts, and if it is set we should print
        # messages about versions and other warnings
        log_msg = log.msg
        if verbose:
            def log_msg(m):
                print m

        pool_size = 5

        # If the engine has an C{optimal_thread_pool_size} attribute, then the
        # maxthreads of the thread pool will be set to that value.  This is
        # most useful for SQLite in-memory connections, where exactly one
        # connection (and thus thread) should be used.
        if hasattr(engine, 'optimal_thread_pool_size'):
            pool_size = engine.optimal_thread_pool_size

        threadpool.ThreadPool.__init__(self,
                        minthreads=1,
                        maxthreads=pool_size,
                        name='DBThreadPool')
        self.engine = engine
        if engine.dialect.name == 'sqlite':
            vers = self.get_sqlite_version()
            if vers < (3,7):
                log_msg("Using SQLite Version %s" % (vers,))
                log_msg("NOTE: this old version of SQLite does not support "
                        "WAL journal mode; a busy master may encounter "
                        "'Database is locked' errors.  Consider upgrading.")
                if vers < (3,4):
                    log_msg("NOTE: this old version of SQLite is not "
                            "supported.")
                    raise RuntimeError("unsupported SQLite version")
            brkn = self.__broken_sqlite = self.detect_bug1810()
            if brkn:
                log_msg("Applying SQLite workaround from Buildbot bug #1810")
        self._start_evt = reactor.callWhenRunning(self._start)

        # patch the do methods to do verbose logging if necessary
        if debug:
            self.do = timed_do_fn(self.do)
            self.do_with_engine = timed_do_fn(self.do_with_engine)

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

    # Try about 170 times over the space of a day, with the last few tries
    # being about an hour apart.  This is designed to span a reasonable amount
    # of time for repairing a broken database server, while still failing
    # actual problematic queries eventually
    BACKOFF_START = 1.0
    BACKOFF_MULT = 1.05
    MAX_OPERATIONALERROR_TIME = 3600*24 # one day
    def __thd(self, with_engine, callable, args, kwargs):
        # try to call callable(arg, *args, **kwargs) repeatedly until no
        # OperationalErrors occur, where arg is either the engine (with_engine)
        # or a connection (not with_engine)
        backoff = self.BACKOFF_START
        start = time.time()
        while True:
            if with_engine:
                arg = self.engine
            else:
                arg = self.engine.contextual_connect()

            if self.__broken_sqlite: # see bug #1810
                arg.execute("select * from sqlite_master")
            try:
                try:
                    rv = callable(arg, *args, **kwargs)
                    assert not isinstance(rv, sa.engine.ResultProxy), \
                            "do not return ResultProxy objects!"
                except sa.exc.OperationalError, e:
                    text = e.orig.args[0]
                    if not isinstance(text, basestring):
                        raise
                    if "Lost connection" in text \
                        or "database is locked" in text:

                        # see if we've retried too much
                        elapsed = time.time() - start
                        if elapsed > self.MAX_OPERATIONALERROR_TIME:
                            raise

                        metrics.MetricCountEvent.log(
                                "DBThreadPool.retry-on-OperationalError")
                        log.msg("automatically retrying query after "
                                "OperationalError (%ss sleep)" % backoff)

                        # sleep (remember, we're in a thread..)
                        time.sleep(backoff)
                        backoff *= self.BACKOFF_MULT

                        # and re-try
                        continue
                    else:
                        raise
            finally:
                if not with_engine:
                    arg.close()
            break
        return rv

    def do(self, callable, *args, **kwargs):
        return threads.deferToThreadPool(reactor, self,
                self.__thd, False, callable, args, kwargs)

    def do_with_engine(self, callable, *args, **kwargs):
        return threads.deferToThreadPool(reactor, self,
                self.__thd, True, callable, args, kwargs)

    def detect_bug1810(self):
        # detect buggy SQLite implementations; call only for a known-sqlite
        # dialect
        try:
            import pysqlite2.dbapi2 as sqlite
            sqlite = sqlite
        except ImportError:
            import sqlite3 as sqlite

        tmpdir = tempfile.mkdtemp()
        dbfile = os.path.join(tmpdir, "detect_bug1810.db")
        def test(select_from_sqlite_master=False):
            conn1 = None
            conn2 = None
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
                if conn1:
                    conn1.close()
                if conn2:
                    conn2.close()
                os.unlink(dbfile)

        try:
            test()
        except sqlite.OperationalError:
            # this is the expected error indicating it's broken
            shutil.rmtree(tmpdir)
            return True

        # but this version should not fail..
        test(select_from_sqlite_master=True)
        shutil.rmtree(tmpdir)
        return False # not broken - no workaround required

    def get_sqlite_version(self):
        engine = sa.create_engine('sqlite://')
        conn = engine.contextual_connect()

        try:
            r = conn.execute("SELECT sqlite_version()")
            vers_row = r.fetchone()
            r.close()
        except:
            return (0,)

        if vers_row:
            try:
                return tuple(map(int, vers_row[0].split('.')))
            except (TypeError, ValueError):
                return (0,)
        else:
            return (0,)
