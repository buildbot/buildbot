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

from __future__ import annotations

import inspect
import time
import traceback
from typing import TYPE_CHECKING

import sqlalchemy as sa
from twisted.internet import defer
from twisted.internet import threads
from twisted.python import log

from buildbot import util
from buildbot.db.buildrequests import AlreadyClaimedError
from buildbot.db.buildsets import AlreadyCompleteError
from buildbot.db.changesources import ChangeSourceAlreadyClaimedError
from buildbot.db.logs import LogSlugExistsError
from buildbot.db.schedulers import SchedulerAlreadyClaimedError
from buildbot.process import metrics
from buildbot.util.sautils import get_sqlite_version

if TYPE_CHECKING:
    from typing import Callable
    from typing import TypeVar

    from typing_extensions import Concatenate
    from typing_extensions import ParamSpec

    _T = TypeVar('_T')
    _P = ParamSpec('_P')

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
        frame = inspect.currentframe()
        locals = frame.f_locals

        # invent a unique ID for the description
        id = _debug_id
        _debug_id = _debug_id + 1

        descr = f"{name}-{id:08x}"

        start_time = time.time()
        log.msg(f"{descr} - before ('{file}' line {line})")
        for name in locals:
            if name in ('self', 'thd'):
                continue
            log.msg(f"{descr} - {name} = {locals[name]!r}")

        # wrap the callable to log the begin and end of the actual thread
        # function
        def callable_wrap(*args, **kargs):
            log.msg(f"{descr} - thd start")
            try:
                return callable(*args, **kwargs)
            finally:
                log.msg(f"{descr} - thd end")

        d = f(callable_wrap, *args, **kwargs)

        @d.addBoth
        def after(x):
            end_time = time.time()
            elapsed = (end_time - start_time) * 1000
            log.msg(f"{descr} - after ({elapsed:0.2f} ms elapsed)")
            return x

        return d

    wrap.__name__ = f.__name__
    wrap.__doc__ = f.__doc__
    return wrap


class DBThreadPool:
    running = False

    def __init__(self, engine, reactor, verbose=False):
        # verbose is used by upgrade scripts, and if it is set we should print
        # messages about versions and other warnings
        log_msg = log.msg
        if verbose:

            def _log_msg(m):
                print(m)

            log_msg = _log_msg

        self.reactor = reactor

        pool_size = 5

        # If the engine has an C{optimal_thread_pool_size} attribute, then the
        # maxthreads of the thread pool will be set to that value.  This is
        # most useful for SQLite in-memory connections, where exactly one
        # connection (and thus thread) should be used.
        if hasattr(engine, 'optimal_thread_pool_size'):
            pool_size = engine.optimal_thread_pool_size

        self._pool = util.twisted.ThreadPool(
            minthreads=1, maxthreads=pool_size, name='DBThreadPool'
        )

        self.engine = engine
        if engine.dialect.name == 'sqlite':
            vers = get_sqlite_version()
            if vers < (3, 7):
                log_msg(f"Using SQLite Version {vers}")
                log_msg(
                    "NOTE: this old version of SQLite does not support "
                    "WAL journal mode; a busy master may encounter "
                    "'Database is locked' errors.  Consider upgrading."
                )
                if vers < (3, 6, 19):
                    log_msg("NOTE: this old version of SQLite is not supported.")
                    raise RuntimeError("unsupported SQLite version")

        # patch the do methods to do verbose logging if necessary
        if debug:
            self.do = timed_do_fn(self.do)
            self.do_with_engine = timed_do_fn(self.do_with_engine)

        self.forbidded_callable_return_type = self.get_sqlalchemy_result_type()

    def get_sqlalchemy_result_type(self):
        try:
            from sqlalchemy.engine import ResultProxy  # sqlalchemy 1.x - 1.3

            return ResultProxy
        except ImportError:
            pass

        try:
            from sqlalchemy.engine import Result  # sqlalchemy 1.4 and newer

            return Result
        except ImportError:
            pass

        raise ImportError("Could not import SQLAlchemy result type")

    def start(self):
        if not self.running:
            self._pool.start()
            self.running = True

    @defer.inlineCallbacks
    def stop(self):
        if self.running:
            yield threads.deferToThreadPool(self.reactor, self._pool, self.engine.dispose)
            self._pool.stop()
            self.running = False

    # Try about 170 times over the space of a day, with the last few tries
    # being about an hour apart.  This is designed to span a reasonable amount
    # of time for repairing a broken database server, while still failing
    # actual problematic queries eventually
    BACKOFF_START = 1.0
    BACKOFF_MULT = 1.05
    MAX_OPERATIONALERROR_TIME = 3600 * 24  # one day

    def __thd(
        self,
        with_engine: bool,
        callable: Callable[Concatenate[sa.engine.Engine | sa.engine.Connection, _P], _T],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> _T:
        # try to call callable(arg, *args, **kwargs) repeatedly until no
        # OperationalErrors occur, where arg is either the engine (with_engine)
        # or a connection (not with_engine)
        backoff = self.BACKOFF_START
        start = time.time()
        while True:
            if with_engine:
                arg = self.engine
            else:
                arg = self.engine.connect()
            try:
                try:
                    rv = callable(arg, *args, **kwargs)
                    assert not isinstance(rv, self.forbidded_callable_return_type), (
                        "do not return ResultProxy objects!"
                    )
                except sa.exc.OperationalError as e:
                    if not self.engine.should_retry(e):
                        log.err(e, 'Got fatal OperationalError on DB')
                        raise
                    elapsed = time.time() - start
                    if elapsed > self.MAX_OPERATIONALERROR_TIME:
                        log.err(
                            e,
                            f'Raising due to {self.MAX_OPERATIONALERROR_TIME} '
                            'seconds delay on DB query retries',
                        )
                        raise

                    metrics.MetricCountEvent.log("DBThreadPool.retry-on-OperationalError")
                    # sleep (remember, we're in a thread..)
                    time.sleep(backoff)
                    backoff *= self.BACKOFF_MULT
                    # and re-try
                    log.err(e, f'retrying {callable} after sql error {e}')
                    continue
                except Exception as e:
                    # AlreadyClaimedError are normal especially in a multimaster
                    # configuration
                    if not isinstance(
                        e,
                        (
                            AlreadyClaimedError,
                            ChangeSourceAlreadyClaimedError,
                            SchedulerAlreadyClaimedError,
                            AlreadyCompleteError,
                            LogSlugExistsError,
                        ),
                    ):
                        log.err(e, 'Got fatal Exception on DB')
                    raise
            finally:
                if not with_engine:
                    arg.close()
            break
        return rv

    def do_with_transaction(
        self,
        callable: Callable[Concatenate[sa.engine.Connection, _P], _T],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> defer.Deferred[_T]:
        """Same as `do`, but will wrap callable with `with conn.begin():`"""

        def _transaction(
            conn: sa.engine.Connection,
            callable: Callable[Concatenate[sa.engine.Connection, _P], _T],
            *args: _P.args,
            **kwargs: _P.kwargs,
        ) -> _T:
            with conn.begin():
                return callable(conn, *args, **kwargs)

        return self.do(_transaction, callable, *args, **kwargs)

    def do(
        self,
        callable: Callable[Concatenate[sa.engine.Connection, _P], _T],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> defer.Deferred[_T]:
        return threads.deferToThreadPool(
            self.reactor,
            self._pool,
            self.__thd,  # type: ignore[arg-type]
            False,
            callable,
            *args,
            **kwargs,
        )

    def do_with_engine(
        self,
        callable: Callable[Concatenate[sa.engine.Engine, _P], _T],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> defer.Deferred[_T]:
        return threads.deferToThreadPool(
            self.reactor,
            self._pool,
            self.__thd,  # type: ignore[arg-type]
            True,
            callable,
            *args,
            **kwargs,
        )
