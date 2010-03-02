import os
import threading

from zope.interface import implements
from twisted.trial import unittest

from buildbot.db import dbspec, exceptions, connector

class DBConnector_Basic(unittest.TestCase):
    """
    Basic tests of the DBConnector class - all start with an empty DB
    """

    def setUp(self):
        # use an in-memory sqlite database to test
        self.dbc = connector.DBConnector(dbspec.DBSpec.from_url("sqlite://"))
        self.dbc.start()
        self.start_thdcount = len(threading.enumerate())

    def tearDown(self):
        self.dbc.stop()
        # double-check we haven't left a ThreadPool open
        assert len(threading.enumerate()) - self.start_thdcount < 1

    def test_quoteq_format(self):
        self.dbc.paramstyle = "format" # override default
        self.assertEqual(
                self.dbc.quoteq("SELECT * from developers where name='?'"),
                "SELECT * from developers where name='%s'")

    def test_quoteq_qmark(self):
        assert self.dbc.paramstyle == "qmark" # default for sqlite
        self.assertEqual(
                self.dbc.quoteq("SELECT * from developers where name='?'"),
                "SELECT * from developers where name='?'")

    def test_paramlist_single(self):
        self.dbc.paramstyle = "format" # override default
        self.assertEqual(self.dbc.parmlist(1), "(%s)")

    def test_paramlist_multiple(self):
        self.dbc.paramstyle = "format" # override default
        self.assertEqual(self.dbc.parmlist(3), "(%s,%s,%s)")

    def test_runQueryNow_simple(self):
        self.assertEqual(self.dbc.runQueryNow("SELECT 1"),
                         [(1,)])

    def test_runQueryNow_exception(self):
        self.assertRaises(Exception, lambda :
            self.dbc.runQueryNow("EAT * FROM cookies"))

    def test_runInterationNow_simple(self):
        def inter(cursor, *args, **kwargs):
            self.assertEqual(cursor.execute("SELECT 1").fetchall(),
                             [(1,)])
        self.dbc.runInteractionNow(inter)

    def test_runInterationNow_args(self):
        def inter(cursor, *args, **kwargs):
            self.assertEqual((args, kwargs), ((1, 2), dict(three=4)))
            cursor.execute("SELECT 1")
        self.dbc.runInteractionNow(inter, 1, 2, three=4)

    def test_runInterationNow_exception(self):
        def inter(cursor):
            cursor.execute("GET * WHERE golden")
        self.assertRaises(Exception, lambda : 
            self.dbc.runInteractionNow(inter))

    def test_runQuery_simple(self):
        d = self.dbc.runQuery("SELECT 1")
        def cb(res):
            self.assertEqual(res, [(1,)])
        d.addCallback(cb)
        return d
