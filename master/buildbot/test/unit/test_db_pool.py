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

from __future__ import absolute_import
from __future__ import print_function

import os
import time

import sqlalchemy as sa

from twisted.internet import defer
from twisted.internet import reactor
from twisted.trial import unittest

from buildbot.db import pool
from buildbot.test.util import db
from buildbot.util import sautils


class Basic(unittest.TestCase):

    # basic tests, just using an in-memory SQL db and one thread

    def setUp(self):
        self.engine = sa.create_engine('sqlite://')
        self.engine.should_retry = lambda _: False
        self.engine.optimal_thread_pool_size = 1
        self.pool = pool.DBThreadPool(self.engine, reactor=reactor)

    def tearDown(self):
        self.pool.shutdown()

    def test_do(self):
        def add(conn, addend1, addend2):
            rp = conn.execute("SELECT %d + %d" % (addend1, addend2))
            return rp.scalar()
        d = self.pool.do(add, 10, 11)

        def check(res):
            self.assertEqual(res, 21)
        d.addCallback(check)
        return d

    @defer.inlineCallbacks
    def expect_failure(self, d, expected_exception, expect_logged_error=False):
        exception = None
        try:
            yield d
        except Exception as e:
            exception = e
        errors = self.flushLoggedErrors(expected_exception)
        if expect_logged_error:
            self.assertEqual(len(errors), 1)
        self.assertTrue(isinstance(exception, expected_exception))

    def test_do_error(self):
        def fail(conn):
            rp = conn.execute("EAT COOKIES")
            return rp.scalar()

        return self.expect_failure(self.pool.do(fail), sa.exc.OperationalError,
                                   expect_logged_error=True)

    def test_do_exception(self):
        def raise_something(conn):
            raise RuntimeError("oh noes")
        return self.expect_failure(self.pool.do(raise_something), RuntimeError,
                                   expect_logged_error=True)

    def test_do_with_engine(self):
        def add(engine, addend1, addend2):
            rp = engine.execute("SELECT %d + %d" % (addend1, addend2))
            return rp.scalar()
        d = self.pool.do_with_engine(add, 10, 11)

        def check(res):
            self.assertEqual(res, 21)
        d.addCallback(check)
        return d

    def test_do_with_engine_exception(self):
        def fail(engine):
            rp = engine.execute("EAT COOKIES")
            return rp.scalar()
        return self.expect_failure(self.pool.do_with_engine(fail), sa.exc.OperationalError)

    def test_persistence_across_invocations(self):
        # NOTE: this assumes that both methods are called with the same
        # connection; if they run in parallel threads then it is not valid to
        # assume that the database engine will have finalized the first
        # transaction (and thus created the table) by the time the second
        # transaction runs.  This is why we set optimal_thread_pool_size in
        # setUp.
        d = defer.succeed(None)

        def create_table(engine):
            engine.execute("CREATE TABLE tmp ( a integer )")
        d.addCallback(lambda r: self.pool.do_with_engine(create_table))

        def insert_into_table(engine):
            engine.execute("INSERT INTO tmp values ( 1 )")
        d.addCallback(lambda r: self.pool.do_with_engine(insert_into_table))
        return d


class Stress(unittest.TestCase):

    def setUp(self):
        setup_engine = sa.create_engine('sqlite:///test.sqlite')
        setup_engine.execute("pragma journal_mode = wal")
        setup_engine.execute("CREATE TABLE test (a integer, b integer)")

        self.engine = sa.create_engine('sqlite:///test.sqlite')
        self.engine.optimal_thread_pool_size = 2
        self.pool = pool.DBThreadPool(self.engine, reactor=reactor)

    def tearDown(self):
        self.pool.shutdown()
        os.unlink("test.sqlite")

    @defer.inlineCallbacks
    def test_inserts(self):
        def write(conn):
            trans = conn.begin()
            conn.execute("INSERT INTO test VALUES (1, 1)")
            time.sleep(31)
            trans.commit()
        d1 = self.pool.do(write)

        def write2(conn):
            trans = conn.begin()
            conn.execute("INSERT INTO test VALUES (1, 1)")
            trans.commit()
        d2 = defer.Deferred()
        d2.addCallback(lambda _:
                       self.pool.do(write2))
        reactor.callLater(0.1, d2.callback, None)

        yield defer.DeferredList([d1, d2])

    # don't run this test, since it takes 30s
    del test_inserts


class BasicWithDebug(Basic):

    # same thing, but with debug=True

    def setUp(self):
        pool.debug = True
        return Basic.setUp(self)

    def tearDown(self):
        pool.debug = False
        return Basic.tearDown(self)


class Native(unittest.TestCase, db.RealDatabaseMixin):

    # similar tests, but using the BUILDBOT_TEST_DB_URL

    def setUp(self):
        d = self.setUpRealDatabase(want_pool=False)

        def make_pool(_):
            self.pool = pool.DBThreadPool(self.db_engine, reactor=reactor)
        d.addCallback(make_pool)
        return d

    def tearDown(self):
        # try to delete the 'native_tests' table
        meta = sa.MetaData()
        native_tests = sautils.Table("native_tests", meta)

        def thd(conn):
            native_tests.drop(bind=self.db_engine, checkfirst=True)
        d = self.pool.do(thd)
        d.addCallback(lambda _: self.pool.shutdown())
        d.addCallback(lambda _: self.tearDownRealDatabase())
        return d

    def test_ddl_and_queries(self):
        meta = sa.MetaData()
        native_tests = sautils.Table("native_tests", meta,
                                     sa.Column('name', sa.String(length=200)))

        # perform a DDL operation and immediately try to access that table;
        # this has caused problems in the past, so this is basically a
        # regression test.
        def ddl(conn):
            t = conn.begin()
            native_tests.create(bind=conn)
            t.commit()
        d = self.pool.do(ddl)

        def access(conn):
            native_tests.insert(bind=conn).execute([{'name': 'foo'}])
        d.addCallback(lambda _:
                      self.pool.do(access))
        return d
