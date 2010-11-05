from sqlalchemy import engine
from twisted.internet import reactor, threads
from twisted.python import threadpool

class DBThreadPool(threadpool.ThreadPool):
    """
    A pool of threads ready and waiting to execute queries.
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

    def do(self, callable, *args, **kwargs):
        """
        Call CALLABLE in a thread, with a Connection as first argument.
        Returns a deferred that will indicate the results of the callable.

        Note: do not return any SQLAlchemy objects via this deferred!
        """
        def thd():
            conn = self.engine.contextual_connect()
            rv = callable(conn, *args, **kwargs)
            assert not isinstance(rv, engine.ResultProxy), \
                    "do not return ResultProxy objects!"
            return rv
        return threads.deferToThreadPool(reactor, self, thd)
