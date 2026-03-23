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

import os
import time
from typing import TYPE_CHECKING
from typing import Any
from typing import NoReturn
from typing import cast

import sqlalchemy as sa
from twisted.internet import defer
from twisted.internet import reactor
from twisted.trial import unittest

from buildbot.db import enginestrategy
from buildbot.db import pool
from buildbot.test.util import db
from buildbot.test.util.db import thd_clean_database
from buildbot.util import sautils

if TYPE_CHECKING:
    from twisted.internet.defer import Deferred
    from twisted.internet.interfaces import IReactorTime

    from buildbot.util.twisted import InlineCallbacksType


class Basic(unittest.TestCase):
    # basic tests, just using an in-memory SQL db and one thread

    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        url = db.resolve_test_db_url(None, sqlite_memory=True)
        self.engine = enginestrategy.create_engine(url, basedir=os.getcwd())
        self.engine.should_retry = lambda _: False  # type: ignore[attr-defined]
        self.engine.optimal_thread_pool_size = 1  # type: ignore[attr-defined]
        self.pool = pool.DBThreadPool(self.engine, reactor=reactor)
        self.pool.start()
        yield self.pool.do(thd_clean_database)
        self.addCleanup(self.pool.stop)

    @defer.inlineCallbacks
    def test_do(self) -> InlineCallbacksType[None]:
        def add(conn: sa.Connection, addend1: int, addend2: int) -> Any | None:
            rp = conn.execute(sa.text(f"SELECT {addend1} + {addend2}"))
            return rp.scalar()

        res = yield self.pool.do(add, 10, 11)

        self.assertEqual(res, 21)

    @defer.inlineCallbacks
    def expect_failure(
        self,
        d: Deferred,
        expected_exceptions: tuple[type[Exception], ...],
        expect_logged_error: bool = False,
    ) -> InlineCallbacksType[None]:
        exception = None
        try:
            yield d
        except Exception as e:
            exception = e
        errors = []
        for expected_exception in expected_exceptions:
            errors += self.flushLoggedErrors(expected_exception)
        if expect_logged_error:
            self.assertEqual(len(errors), 1)
        self.assertTrue(isinstance(exception, expected_exceptions))

    def test_do_error(self) -> Deferred[None]:
        def fail(conn: sa.Connection) -> Any | None:
            rp = conn.execute(sa.text("EAT COOKIES"))
            return rp.scalar()

        return self.expect_failure(
            self.pool.do(fail),
            (sa.exc.ProgrammingError, sa.exc.OperationalError),
            expect_logged_error=True,
        )

    def test_do_exception(self) -> Deferred[None]:
        def raise_something(conn: sa.Connection) -> NoReturn:
            raise RuntimeError("oh noes")

        return self.expect_failure(
            self.pool.do(raise_something), (RuntimeError,), expect_logged_error=True
        )

    @defer.inlineCallbacks
    def test_do_with_engine(self) -> InlineCallbacksType[None]:
        def add(engine: sa.Engine, addend1: int, addend2: int) -> Any | None:
            with engine.connect() as conn:
                rp = conn.execute(sa.text(f"SELECT {addend1} + {addend2}"))
                return rp.scalar()

        res = yield self.pool.do_with_engine(add, 10, 11)

        self.assertEqual(res, 21)

    def test_do_with_engine_exception(self) -> Deferred[None]:
        def fail(engine: sa.Engine) -> Any | None:
            with engine.connect() as conn:
                rp = conn.execute(sa.text("EAT COOKIES"))
            return rp.scalar()

        return self.expect_failure(
            self.pool.do_with_engine(fail), (sa.exc.ProgrammingError, sa.exc.OperationalError)
        )

    @defer.inlineCallbacks
    def test_persistence_across_invocations(self) -> InlineCallbacksType[None]:
        # NOTE: this assumes that both methods are called with the same
        # connection; if they run in parallel threads then it is not valid to
        # assume that the database engine will have finalized the first
        # transaction (and thus created the table) by the time the second
        # transaction runs.  This is why we set optimal_thread_pool_size in
        # setUp.
        def create_table(engine: sa.Engine) -> None:
            with engine.connect() as conn:
                conn.execute(sa.text("CREATE TABLE tmp ( a integer )"))
                conn.commit()

        yield self.pool.do_with_engine(create_table)

        def insert_into_table(engine: sa.Engine) -> None:
            with engine.connect() as conn:
                conn.execute(sa.text("INSERT INTO tmp values ( 1 )"))
                conn.commit()

        yield self.pool.do_with_engine(insert_into_table)

    @defer.inlineCallbacks
    def test_ddl_and_queries(self) -> InlineCallbacksType[None]:
        meta = sa.MetaData()
        native_tests = sautils.Table("native_tests", meta, sa.Column('name', sa.String(length=200)))

        # perform a DDL operation and immediately try to access that table;
        # this has caused problems in the past, so this is basically a
        # regression test.
        def ddl(conn: sa.Connection) -> None:
            t = conn.begin()
            native_tests.create(bind=conn)
            t.commit()

        yield self.pool.do(ddl)

        def access(conn: sa.Connection) -> None:
            conn.execute(native_tests.insert().values({'name': 'foo'}))

        yield self.pool.do_with_transaction(access)


class Stress(unittest.TestCase):
    def setUp(self) -> None:
        setup_engine = sa.create_engine('sqlite:///test.sqlite', future=True)
        setup_engine.execute("pragma journal_mode = wal")  # type: ignore[attr-defined]
        setup_engine.execute("CREATE TABLE test (a integer, b integer)")  # type: ignore[attr-defined]

        self.engine = sa.create_engine('sqlite:///test.sqlite', future=True)
        self.engine.optimal_thread_pool_size = 2  # type: ignore[attr-defined]
        self.pool = pool.DBThreadPool(self.engine, reactor=reactor)
        self.pool.start()
        self.addCleanup(self.pool.stop)

    def tearDown(self) -> None:
        os.unlink("test.sqlite")

    @defer.inlineCallbacks
    def test_inserts(self) -> InlineCallbacksType[None]:
        def write(conn: sa.Connection) -> None:
            trans = conn.begin()
            conn.execute("INSERT INTO test VALUES (1, 1)")  # type: ignore[call-overload]
            time.sleep(31)
            trans.commit()

        d1 = self.pool.do(write)

        def write2(conn: sa.Connection) -> None:
            trans = conn.begin()
            conn.execute("INSERT INTO test VALUES (1, 1)")  # type: ignore[call-overload]
            trans.commit()

        d2: Deferred[None] = defer.Deferred()
        d2.addCallback(lambda _: self.pool.do(write2))
        cast("IReactorTime", reactor).callLater(0.1, d2.callback, None)

        yield defer.DeferredList([d1, d2], consumeErrors=True)

    # don't run this test, since it takes 30s
    del test_inserts


class BasicWithDebug(Basic):
    # same thing, but with debug=True

    def setUp(self) -> Deferred[None]:  # type: ignore[override]
        pool.debug = True
        return super().setUp()

    def tearDown(self) -> None:
        pool.debug = False
        return super().tearDown()
