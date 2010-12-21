import sqlalchemy
from twisted.trial import unittest
from twisted.internet import defer
from buildbot.db import pool

class DBThreadPool(unittest.TestCase):
    def setUp(self):
        self.engine = sqlalchemy.create_engine('sqlite://')
        self.pool = pool.DBThreadPool(self.engine)

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
        d = defer.succeed(None)
        def create_table(engine):
            engine.execute("CREATE TABLE tmp ( a integer )")
        d.addCallback( lambda r : self.pool.do_with_engine(create_table))
        def insert_into_table(engine):
            engine.execute("INSERT INTO tmp values ( 1 )")
        d.addCallback( lambda r : self.pool.do_with_engine(insert_into_table))
        return d
