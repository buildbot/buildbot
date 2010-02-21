import os
import threading

from zope.interface import implements
from twisted.trial import unittest

from buildbot import db

class DBSpec(unittest.TestCase):
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
        d = db.DBSpec.from_url("sqlite:///state.sqlite", basedir=basedir)
        self.failUnlessConnection(d, self.SQLITE_NAMES, 
                connargs=(os.path.join(basedir, "state.sqlite"),))

    def test_fromURL_sqlitePercentSub(self):
        basedir = "/foo/bar"
        d = db.DBSpec.from_url("sqlite:///%(basedir)s/x/state.sqlite", basedir=basedir)
        self.failUnlessConnection(d, self.SQLITE_NAMES, 
                connargs=(os.path.join(basedir, "x/state.sqlite"),))

    def test_fromURL_sqliteAbsolutePath(self):
        basedir = "/foo/bar"
        d = db.DBSpec.from_url("sqlite:////tmp/state.sqlite", basedir=basedir)
        self.failUnlessConnection(d, self.SQLITE_NAMES, 
                connargs=("/tmp/state.sqlite",))

    def test_fromURL_sqliteAbsolutePathNoBasedir(self):
        d = db.DBSpec.from_url("sqlite:////tmp/state.sqlite")
        self.failUnlessConnection(d, self.SQLITE_NAMES, 
                connargs=("/tmp/state.sqlite",))

    def test_fromURL_sqliteMemory(self):
        d = db.DBSpec.from_url("sqlite://")
        self.failUnlessConnection(d, self.SQLITE_NAMES, 
                connargs=(":memory:",))

    def test_fromURL_sqliteArgs(self):
        d = db.DBSpec.from_url("sqlite:////tmp/state.sqlite?foo=bar")
        self.failUnlessConnection(d, self.SQLITE_NAMES, 
                connargs=("/tmp/state.sqlite",),
                connkw={'foo' : 'bar'})

    def test_fromURL_noDriver(self):
        self.failUnlessRaises(ValueError, db.DBSpec.from_url, "state.sqlite")

    def test_fromURL_noColon(self):
        self.failUnlessRaises(ValueError, db.DBSpec.from_url, "sqlite/state.sqlite")

    def test_fromURL_noSlash(self):
        self.failUnlessRaises(ValueError, db.DBSpec.from_url, "sqlite:state.sqlite")

    def test_fromURL_singleSlash(self):
        self.failUnlessRaises(ValueError, db.DBSpec.from_url, "sqlite:/state.sqlite")

    def test_fromURL_unknownDriver(self):
        self.failUnlessRaises(ValueError, db.DBSpec.from_url, "unknowndb://foo/bar")

    def test_fromURL_mysqlLocal2Slashes(self):
        self.failUnlessRaises(ValueError, db.DBSpec.from_url, "mysql://foo")

    def test_fromURL_mysqlAlphaPort(self):
        self.failUnlessRaises(ValueError, db.DBSpec.from_url, "mysql://somehost.com:badport/db")

    def test_fromURL_mysql(self):
        basedir = "/foo/bar"
        d = db.DBSpec.from_url("mysql://somehost.com/dbname", basedir=basedir)
        self.failUnlessConnection(d, 'MySQLdb',
                connkw=dict(host='somehost.com', db='dbname'))

    def test_fromURL_mysqlNoBasedir(self):
        d = db.DBSpec.from_url("mysql://somehost.com/dbname")
        self.failUnlessConnection(d, 'MySQLdb',
                connkw=dict(host='somehost.com', db='dbname'))

    def test_fromURL_mysqlPort(self):
        d = db.DBSpec.from_url("mysql://somehost.com:9000/dbname")
        self.failUnlessConnection(d, 'MySQLdb',
                connkw=dict(host='somehost.com', db='dbname', port=9000))

    def test_fromURL_mysqlLocal(self):
        d = db.DBSpec.from_url("mysql:///database_name")
        self.failUnlessConnection(d, 'MySQLdb',
                connkw=dict(host=None, db='database_name'))

    def test_fromURL_mysqlAuth(self):
        d = db.DBSpec.from_url("mysql://user:pass@somehost.com/dbname")
        self.failUnlessConnection(d, 'MySQLdb',
                connkw=dict(host='somehost.com', db='dbname', user="user", passwd="pass"))

    def test_fromURL_mysqlAuthNoPass(self):
        d = db.DBSpec.from_url("mysql://user@somehost.com/dbname")
        self.failUnlessConnection(d, 'MySQLdb',
                connkw=dict(host='somehost.com', db='dbname', user="user"))

    def test_fromURL_mysqlAuthNoPassPort(self):
        d = db.DBSpec.from_url("mysql://user@somehost.com:8000/dbname")
        self.failUnlessConnection(d, 'MySQLdb',
                connkw=dict(host='somehost.com', db='dbname', user="user", port=8000))

    def test_fromURL_mysqlAuthNoPassPortArgs(self):
        d = db.DBSpec.from_url("mysql://user@somehost.com:8000/dbname?foo=moo")
        self.failUnlessConnection(d, 'MySQLdb',
                connkw=dict(host='somehost.com', db='dbname', user="user",
                            port=8000, foo="moo"))

class DBSpec_funcs(unittest.TestCase):

    def setUp(self):
        # sqlite does not allow multiple connections to an in-memory database, so
        # we have to set up an on-disk sqlite file
        self.dbfile = os.path.abspath("dbspec_funcs.sqlite")
        if os.path.exists(self.dbfile):
            os.unlink(self.dbfile)
        self.dbspec = db.DBSpec.from_url("sqlite:///" + self.dbfile)
        self.conns = []

    def tearDown(self):
        # be careful to stop all connector
        for conn in self.conns:
            conn.stop()
        # and delete the underlying file
        if os.path.exists(self.dbfile):
            os.unlink(self.dbfile)
        # double-check we haven't left a ThreadPool open
        assert len(threading.enumerate()) < 4

    # track a connector that must be closed
    def trackConn(self, conn):
        self.conns.append(conn)
        return conn

    # put together a fake database, with just a version table
    def makeFakeDB(self):
        conn = self.trackConn(db.DBConnector(self.dbspec))
        conn.start()
        conn.runQueryNow("CREATE TABLE version (`version` integer)")
        conn.runQueryNow("INSERT INTO version values (1)")
        conn.stop()

    ## tests

    def test_open_db_missingFails(self):
        self.assertRaises(db.DatabaseNotReadyError, db.open_db, self.dbspec)

    def test_open_db_existingOK(self):
        self.makeFakeDB()
        conn = self.trackConn(db.open_db(self.dbspec))
        self.assertEqual(conn.get_version(), 1)
        conn.stop()

    def test_create_db_missingOK(self):
        db.create_db(self.dbspec) # note this does not return a DBConnector
        conn = self.trackConn(db.DBConnector(self.dbspec))
        conn.start()
        self.assertEqual(conn.runQueryNow("SELECT * from version"), [(1,)])
        conn.stop()

    def test_create_db_existingFails(self):
        self.makeFakeDB()
        self.assertRaises(db.DBAlreadyExistsError, db.create_db, self.dbspec)

    def test_create_or_upgrade_db_missingOK(self):
        conn = self.trackConn(db.create_or_upgrade_db(self.dbspec))
        self.assertEqual(conn.runQueryNow("SELECT * from version"), [(1,)])

    def test_create_or_upgrade_db_existingOK(self):
        self.makeFakeDB()
        conn = self.trackConn(db.create_or_upgrade_db(self.dbspec))
        self.assertEqual(conn.runQueryNow("SELECT * from version"), [(1,)])

class DBConnector_Basic(unittest.TestCase):
    """
    Basic tests of the DBConnector class - all start with an empty DB
    """

    def setUp(self):
        # use an in-memory sqlite database to test
        self.dbc = db.DBConnector(db.DBSpec.from_url("sqlite://"))
        self.dbc.start()

    def tearDown(self):
        self.dbc.stop()
        # double-check we haven't left a ThreadPool open
        assert len(threading.enumerate()) < 4

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
