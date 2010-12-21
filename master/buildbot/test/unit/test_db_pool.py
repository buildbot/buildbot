import sqlalchemy
from twisted.trial import unittest
from buildbot.db import pool

class DBThreadPool(unittest.TestCase):
    def setUp(self):
        self.engine = sqlalchemy.create_engine('sqlite://')
        self.pool = pool.DBThreadPool(self.engine)

    def test_simple(self):
        def add(conn, addend1, addend2):
            rp = conn.execute("SELECT %d + %d" % (addend1, addend2))
            return rp.scalar()
        d = self.pool.do(add, 10, 11)
        def check(res):
            self.assertEqual(res, 21)
        d.addCallback(check)
        return d

    def test_error(self):
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

    def test_exception(self):
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
