import os
import threading

from zope.interface import implements
from twisted.trial import unittest

from buildbot.db import dbspec, exceptions, connector

class DBSpec(unittest.TestCase):
    # a dburl of "sqlite:///.." can use either the third-party sqlite3
    # module, or the stdlib pysqlite2.dbapi2 module, depending upon the
    # version of python in use
    SQLITE_NAMES = ["sqlite3", "pysqlite2.dbapi2"]

    def failUnlessConnection(self, spec, dbapiName, connargs=None, connkw=None):
        errs = []
        if dbapiName is self.SQLITE_NAMES:
            if spec.dbapiName not in self.SQLITE_NAMES:
                errs.append("unexpected dbapiName %s" % spec.dbapiName)
        else:
            if spec.dbapiName != dbapiName:
                errs.append("unexpected dbapiName %s" % spec.dbapiName)
        if connargs is not None:
            if spec.connargs != connargs:
                errs.append("unexpected connargs: %s, expected %s" % (spec.connargs, connargs))
        if connkw is not None:
            if spec.connkw != connkw:
                errs.append("unexpected connkw: %s, expected %s" % (spec.connkw, connkw))
        if errs:
            raise unittest.FailTest("; ".join(errs))

    def test_fromURL_sqliteRelative(self):
        basedir = "/foo/bar"
        d = dbspec.DBSpec.from_url("sqlite:///state.sqlite", basedir=basedir)
        self.failUnlessConnection(d, self.SQLITE_NAMES, 
                connargs=(os.path.join(basedir, "state.sqlite"),))

    def test_fromURL_sqlitePercentSub(self):
        basedir = "/foo/bar"
        d = dbspec.DBSpec.from_url("sqlite:///%(basedir)s/x/state.sqlite", basedir=basedir)
        self.failUnlessConnection(d, self.SQLITE_NAMES, 
                connargs=(os.path.join(basedir, "x/state.sqlite"),))

    def test_fromURL_sqliteAbsolutePath(self):
        basedir = "/foo/bar"
        d = dbspec.DBSpec.from_url("sqlite:////tmp/state.sqlite", basedir=basedir)
        self.failUnlessConnection(d, self.SQLITE_NAMES, 
                connargs=("/tmp/state.sqlite",))

    def test_fromURL_sqliteAbsolutePathNoBasedir(self):
        d = dbspec.DBSpec.from_url("sqlite:////tmp/state.sqlite")
        self.failUnlessConnection(d, self.SQLITE_NAMES, 
                connargs=("/tmp/state.sqlite",))

    def test_fromURL_sqliteMemory(self):
        d = dbspec.DBSpec.from_url("sqlite://")
        self.failUnlessConnection(d, self.SQLITE_NAMES, 
                connargs=(":memory:",))

    def test_fromURL_sqliteArgs(self):
        d = dbspec.DBSpec.from_url("sqlite:////tmp/state.sqlite?foo=bar")
        self.failUnlessConnection(d, self.SQLITE_NAMES, 
                connargs=("/tmp/state.sqlite",),
                connkw={'foo' : 'bar'})

    def test_fromURL_noDriver(self):
        self.failUnlessRaises(ValueError, dbspec.DBSpec.from_url, "state.sqlite")

    def test_fromURL_noColon(self):
        self.failUnlessRaises(ValueError, dbspec.DBSpec.from_url, "sqlite/state.sqlite")

    def test_fromURL_noSlash(self):
        self.failUnlessRaises(ValueError, dbspec.DBSpec.from_url, "sqlite:state.sqlite")

    def test_fromURL_singleSlash(self):
        self.failUnlessRaises(ValueError, dbspec.DBSpec.from_url, "sqlite:/state.sqlite")

    def test_fromURL_unknownDriver(self):
        self.failUnlessRaises(ValueError, dbspec.DBSpec.from_url, "unknowndb://foo/bar")

    def test_fromURL_mysqlLocal2Slashes(self):
        self.failUnlessRaises(ValueError, dbspec.DBSpec.from_url, "mysql://foo")

    def test_fromURL_mysqlAlphaPort(self):
        self.failUnlessRaises(ValueError, dbspec.DBSpec.from_url, "mysql://somehost.com:badport/db")

    def test_fromURL_mysql(self):
        basedir = "/foo/bar"
        d = dbspec.DBSpec.from_url("mysql://somehost.com/dbname", basedir=basedir)
        self.failUnlessConnection(d, 'MySQLdb',
                connkw=dict(host='somehost.com', db='dbname', use_unicode=True, charset='utf8'))

    def test_fromURL_mysqlNoBasedir(self):
        d = dbspec.DBSpec.from_url("mysql://somehost.com/dbname")
        self.failUnlessConnection(d, 'MySQLdb',
                connkw=dict(host='somehost.com', db='dbname', use_unicode=True, charset='utf8'))

    def test_fromURL_mysqlPort(self):
        d = dbspec.DBSpec.from_url("mysql://somehost.com:9000/dbname")
        self.failUnlessConnection(d, 'MySQLdb',
                connkw=dict(host='somehost.com', db='dbname', port=9000, use_unicode=True, charset='utf8'))

    def test_fromURL_mysqlLocal(self):
        d = dbspec.DBSpec.from_url("mysql:///database_name")
        self.failUnlessConnection(d, 'MySQLdb',
                connkw=dict(host=None, db='database_name', use_unicode=True, charset='utf8'))

    def test_fromURL_mysqlAuth(self):
        d = dbspec.DBSpec.from_url("mysql://user:pass@somehost.com/dbname")
        self.failUnlessConnection(d, 'MySQLdb',
                connkw=dict(host='somehost.com', db='dbname', user="user", passwd="pass", use_unicode=True, charset='utf8'))

    def test_fromURL_mysqlAuthNoPass(self):
        d = dbspec.DBSpec.from_url("mysql://user@somehost.com/dbname")
        self.failUnlessConnection(d, 'MySQLdb',
                connkw=dict(host='somehost.com', db='dbname', user="user", use_unicode=True, charset='utf8'))

    def test_fromURL_mysqlAuthNoPassPort(self):
        d = dbspec.DBSpec.from_url("mysql://user@somehost.com:8000/dbname")
        self.failUnlessConnection(d, 'MySQLdb',
                connkw=dict(host='somehost.com', db='dbname', user="user", port=8000, use_unicode=True, charset='utf8'))

    def test_fromURL_mysqlAuthNoPassPortArgs(self):
        d = dbspec.DBSpec.from_url("mysql://user@somehost.com:8000/dbname?foo=moo")
        self.failUnlessConnection(d, 'MySQLdb',
                connkw=dict(host='somehost.com', db='dbname', user="user",
                            port=8000, foo="moo", use_unicode=True, charset='utf8'))

class DBSpec_methods(unittest.TestCase):

    def setUp(self):
        self.spec = dbspec.DBSpec.from_url("sqlite://")
        self.pools = []
        self.start_thdcount = len(threading.enumerate())

    def tearDown(self):
        # be careful to stop all pools
        for pool in self.pools:
            pool.close()
        # double-check we haven't left a ThreadPool open
        assert len(threading.enumerate()) - self.start_thdcount < 1

    # track a pool that must be closed
    def trackPool(self, pool):
        self.pools.append(pool)
        return pool

    # note that sync connections need not be cleaned up

    ## tests

    def test_get_dbapi_has_connect(self):
        self.assertTrue(hasattr(self.spec.get_dbapi(), 'connect'))

    def test_get_sync_connection_has_cursor(self):
        self.assertTrue(hasattr(self.spec.get_sync_connection(), 'cursor'))

    def test_get_async_connection_pool_has_runInteraction(self):
        pool = self.spec.get_async_connection_pool()
        self.trackPool(pool)
        pool.start()
        self.assertTrue(hasattr(pool, 'runInteraction'))
