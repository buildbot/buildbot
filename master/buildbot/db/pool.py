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

import twisted
from sqlalchemy import engine
from twisted.internet import reactor, threads, defer
from twisted.python import threadpool, failure, versions

class DBThreadPool(threadpool.ThreadPool):
    """
    A pool of threads ready and waiting to execute queries.

    If the engine has an @C{optimal_thread_pool_size} attribute, then the
    maxthreads of the thread pool will be set to that value.  This is most
    useful for SQLite in-memory connections, where exactly one connection
    (and thus thread) should be used.
    """

    running = False

    def __init__(self, engine):
        pool_size = 5
        if hasattr(engine, 'optimal_thread_pool_size'):
            pool_size = engine.optimal_thread_pool_size
        threadpool.ThreadPool.__init__(self,
                        minthreads=1,
                        maxthreads=pool_size,
                        name='DBThreadPool')
        self.engine = engine
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

    def do(self, callable, *args, **kwargs):
        """
        Call CALLABLE in a thread, with a Connection as first argument.
        Returns a deferred that will indicate the results of the callable.

        Note: do not return any SQLAlchemy objects via this deferred!
        """
        def thd():
            conn = self.engine.contextual_connect()
            try:
                rv = callable(conn, *args, **kwargs)
                assert not isinstance(rv, engine.ResultProxy), \
                        "do not return ResultProxy objects!"
            finally:
                conn.close()
            return rv
        return threads.deferToThreadPool(reactor, self, thd)

    def do_with_engine(self, callable, *args, **kwargs):
        """
        Like l{do}, but with an SQLAlchemy Engine as the first argument
        """
        def thd():
            rv = callable(self.engine, *args, **kwargs)
            assert not isinstance(rv, engine.ResultProxy), \
                    "do not return ResultProxy objects!"
            return rv
        return threads.deferToThreadPool(reactor, self, thd)

    # older implementations for twisted < 0.8.2, which does not have
    # deferToThreadPool; this basically re-implements it, although it gets some
    # of the synchronization wrong - the thread may still be "in use" when the
    # deferred fires in the parent, which can lead to database accesses hopping
    # between threads.  In practice, this should not cause any difficulty.
    def do_081(self, callable, *args, **kwargs):
        d = defer.Deferred()
        def thd():
            try:
                conn = self.engine.contextual_connect()
                try:
                    rv = callable(conn, *args, **kwargs)
                    assert not isinstance(rv, engine.ResultProxy), \
                            "do not return ResultProxy objects!"
                finally:
                    conn.close()
                reactor.callFromThread(d.callback, rv)
            except:
                reactor.callFromThread(d.errback, failure.Failure())
        self.callInThread(thd)
        return d
    def do_with_engine_081(self, callable, *args, **kwargs):
        d = defer.Deferred()
        def thd():
            try:
                conn = self.engine
                rv = callable(conn, *args, **kwargs)
                assert not isinstance(rv, engine.ResultProxy), \
                        "do not return ResultProxy objects!"
                reactor.callFromThread(d.callback, rv)
            except:
                reactor.callFromThread(d.errback, failure.Failure())
        self.callInThread(thd)
        return d
    if twisted.version < versions.Version('twisted', 8, 2, 0):
        do = do_081
        do_with_engine = do_with_engine_081
