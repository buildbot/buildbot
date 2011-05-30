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

import sqlalchemy as sa
from twisted.trial import unittest
from twisted.internet import defer
from buildbot.db import pool
from buildbot.test.util import db

class Basic(unittest.TestCase):

    # basic tests, just using an in-memory SQL db and one thread

    def setUp(self):
        self.engine = sa.create_engine('sqlite://')
        self.engine.optimal_thread_pool_size = 1
        self.pool = pool.DBThreadPool(self.engine)

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

    def test_do_error(self):
        def fail(conn):
            rp = conn.execute("EAT COOKIES")
            return rp.scalar()
        d = self.pool.do(fail)
        def eb(f):
            pass
        def cb(r):
            self.fail("no exception propagated")
        d.addCallbacks(cb, eb)
        return d

    def test_do_exception(self):
        def raise_something(conn):
            raise RuntimeError("oh noes")
        d = self.pool.do(raise_something)
        def eb(f):
            f.trap(RuntimeError) # make sure it gets the *right* exception
            pass
        def cb(r):
            self.fail("no exception propagated")
        d.addCallbacks(cb, eb)
        return d

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
        d = self.pool.do_with_engine(fail)
        def eb(f):
            pass
        def cb(r):
            self.fail("no exception propagated")
        d.addCallbacks(cb, eb)
        return d

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
        d.addCallback( lambda r : self.pool.do_with_engine(create_table))
        def insert_into_table(engine):
            engine.execute("INSERT INTO tmp values ( 1 )")
        d.addCallback( lambda r : self.pool.do_with_engine(insert_into_table))
        return d

class Native(unittest.TestCase, db.RealDatabaseMixin):

    # similar tests, but using the BUILDBOT_TEST_DB_URL

    def setUp(self):
        d = self.setUpRealDatabase(want_pool=False)
        def make_pool(_):
            self.pool = pool.DBThreadPool(self.db_engine)
        d.addCallback(make_pool)
        return d

    def tearDown(self):
        # try to delete the 'native_tests' table
        meta = sa.MetaData()
        native_tests = sa.Table("native_tests", meta)
        def thd(conn):
            native_tests.drop(bind=self.db_engine, checkfirst=True)
        d = self.pool.do(thd)
        d.addCallback(lambda _ : self.pool.shutdown())
        d.addCallback(lambda _ : self.tearDownRealDatabase())
        return d

    def test_ddl_and_queries(self):
        meta = sa.MetaData()
        native_tests = sa.Table("native_tests", meta,
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
            native_tests.insert(bind=conn).execute([ {'name':'foo'} ])
        d.addCallback(lambda _ :
            self.pool.do(access))
        return d

