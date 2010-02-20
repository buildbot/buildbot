import os

from zope.interface import implements
from twisted.trial import unittest

from buildbot import db

class DB(unittest.TestCase):
    # a dburl of "sqlite:///.." can use either the third-party sqlite3
    # module, or the stdlib pysqlite2.dbapi2 module, depending upon the
    # version of python in use
    SQLITE_NAMES = ["sqlite3", "pysqlite2.dbapi2"]

    def failUnlessConnection(self, db, dbapiName, connargs=None, connkw=None):
        errs = []
        if dbapiName is self.SQLITE_NAMES:
            if db.dbapiName not in self.SQLITE_NAMES:
                errs.append("unexpected dbapiName %s" % db.dbapiName)
        else:
            if db.dbapiName != dbapiName:
                errs.append("unexpected dbapiName %s" % db.dbapiName)
        if connargs is not None:
            if db.connargs != connargs:
                errs.append("unexpected connargs: %s, expected %s" % (db.connargs, connargs))
        if connkw is not None:
            if db.connkw != connkw:
                errs.append("unexpected connkw: %s, expected %s" % (db.connkw, connkw))
        if errs:
            raise unittest.FailTest("; ".join(errs))

    def test_fromURL_sqliteRelative(self):
        basedir = "/foo/bar"
        d = db.DB.from_url("sqlite:///state.sqlite", basedir=basedir)
        self.failUnlessConnection(d, self.SQLITE_NAMES, 
                connargs=(os.path.join(basedir, "state.sqlite"),))

    def test_fromURL_sqlitePercentSub(self):
        basedir = "/foo/bar"
        d = db.DB.from_url("sqlite:///%(basedir)s/x/state.sqlite", basedir=basedir)
        self.failUnlessConnection(d, self.SQLITE_NAMES, 
                connargs=(os.path.join(basedir, "x/state.sqlite"),))

    def test_fromURL_sqliteAbsolutePath(self):
        basedir = "/foo/bar"
        d = db.DB.from_url("sqlite:////tmp/state.sqlite", basedir=basedir)
        self.failUnlessConnection(d, self.SQLITE_NAMES, 
                connargs=("/tmp/state.sqlite",))

    def test_fromURL_sqliteAbsolutePathNoBasedir(self):
        d = db.DB.from_url("sqlite:////tmp/state.sqlite")
        self.failUnlessConnection(d, self.SQLITE_NAMES, 
                connargs=("/tmp/state.sqlite",))

    def test_fromURL_sqliteMemory(self):
        d = db.DB.from_url("sqlite://")
        self.failUnlessConnection(d, self.SQLITE_NAMES, 
                connargs=(":memory:",))

    def test_fromURL_sqliteArgs(self):
        d = db.DB.from_url("sqlite:////tmp/state.sqlite?foo=bar")
        self.failUnlessConnection(d, self.SQLITE_NAMES, 
                connargs=("/tmp/state.sqlite",),
                connkw={'foo' : 'bar'})

    def test_fromURL_noDriver(self):
        self.failUnlessRaises(ValueError, db.DB.from_url, "state.sqlite")

    def test_fromURL_noColon(self):
        self.failUnlessRaises(ValueError, db.DB.from_url, "sqlite/state.sqlite")

    def test_fromURL_noSlash(self):
        self.failUnlessRaises(ValueError, db.DB.from_url, "sqlite:state.sqlite")

    def test_fromURL_singleSlash(self):
        self.failUnlessRaises(ValueError, db.DB.from_url, "sqlite:/state.sqlite")

    def test_fromURL_unknownDriver(self):
        self.failUnlessRaises(ValueError, db.DB.from_url, "unknowndb://foo/bar")

    def test_fromURL_mysqlLocal2Slashes(self):
        self.failUnlessRaises(ValueError, db.DB.from_url, "mysql://foo")

    def test_fromURL_mysqlAlphaPort(self):
        self.failUnlessRaises(ValueError, db.DB.from_url, "mysql://somehost.com:badport/db")

    def test_fromURL_mysql(self):
        basedir = "/foo/bar"
        d = db.DB.from_url("mysql://somehost.com/dbname", basedir=basedir)
        self.failUnlessConnection(d, 'MySQLdb',
                connkw=dict(host='somehost.com', db='dbname'))

    def test_fromURL_mysqlNoBasedir(self):
        d = db.DB.from_url("mysql://somehost.com/dbname")
        self.failUnlessConnection(d, 'MySQLdb',
                connkw=dict(host='somehost.com', db='dbname'))

    def test_fromURL_mysqlPort(self):
        d = db.DB.from_url("mysql://somehost.com:9000/dbname")
        self.failUnlessConnection(d, 'MySQLdb',
                connkw=dict(host='somehost.com', db='dbname', port=9000))

    def test_fromURL_mysqlLocal(self):
        d = db.DB.from_url("mysql:///database_name")
        self.failUnlessConnection(d, 'MySQLdb',
                connkw=dict(host=None, db='database_name'))

    def test_fromURL_mysqlAuth(self):
        d = db.DB.from_url("mysql://user:pass@somehost.com/dbname")
        self.failUnlessConnection(d, 'MySQLdb',
                connkw=dict(host='somehost.com', db='dbname', user="user", passwd="pass"))

    def test_fromURL_mysqlAuthNoPass(self):
        d = db.DB.from_url("mysql://user@somehost.com/dbname")
        self.failUnlessConnection(d, 'MySQLdb',
                connkw=dict(host='somehost.com', db='dbname', user="user"))

    def test_fromURL_mysqlAuthNoPassPort(self):
        d = db.DB.from_url("mysql://user@somehost.com:8000/dbname")
        self.failUnlessConnection(d, 'MySQLdb',
                connkw=dict(host='somehost.com', db='dbname', user="user", port=8000))

    def test_fromURL_mysqlAuthNoPassPortArgs(self):
        d = db.DB.from_url("mysql://user@somehost.com:8000/dbname?foo=moo")
        self.failUnlessConnection(d, 'MySQLdb',
                connkw=dict(host='somehost.com', db='dbname', user="user",
                            port=8000, foo="moo"))
