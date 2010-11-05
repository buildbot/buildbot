from twisted.trial import unittest
from sqlalchemy.engine import url
from buildbot.db import enginestrategy

class BuildbotEngineStrategy_special_cases(unittest.TestCase):
    "Test the special case methods, without actually creating a db"

    def setUp(self):
        self.strat = enginestrategy.BuildbotEngineStrategy()

    def test_sqlite_pct_sub(self):
        u = url.make_url("sqlite:///%(basedir)s/x/state.sqlite")
        kwargs = dict(basedir='/my-base-dir')
        u, kwargs, max_conns = self.strat.special_case_sqlite(u, kwargs)
        self.assertEqual([ str(u), max_conns, kwargs ],
            [ "sqlite:////my-base-dir/x/state.sqlite", None,
              dict(basedir='/my-base-dir') ])

    def test_sqlite_relpath(self):
        u = url.make_url("sqlite:///x/state.sqlite")
        kwargs = dict(basedir='/my-base-dir')
        u, kwargs, max_conns = self.strat.special_case_sqlite(u, kwargs)
        self.assertEqual([ str(u), max_conns, kwargs ],
            [ "sqlite:////my-base-dir/x/state.sqlite", None,
              dict(basedir='/my-base-dir') ])

    def test_sqlite_abspath(self):
        u = url.make_url("sqlite:////x/state.sqlite")
        kwargs = dict(basedir='/my-base-dir')
        u, kwargs, max_conns = self.strat.special_case_sqlite(u, kwargs)
        self.assertEqual([ str(u), max_conns, kwargs ],
            [ "sqlite:////x/state.sqlite", None,
              dict(basedir='/my-base-dir') ])

    def test_sqlite_memory(self):
        u = url.make_url("sqlite://")
        kwargs = dict(basedir='my-base-dir')
        u, kwargs, max_conns = self.strat.special_case_sqlite(u, kwargs)
        self.assertEqual([ str(u), max_conns, kwargs ],
            [ "sqlite://", 1, # only one conn at a time
              dict(basedir='my-base-dir',
                   pool_size=1) ]) # extra in-memory args

    def test_mysql_simple(self):
        u = url.make_url("mysql://host/dbname")
        kwargs = dict(basedir='my-base-dir')
        u, kwargs, max_conns = self.strat.special_case_mysql(u, kwargs)
        self.assertEqual([ str(u), max_conns, kwargs ],
                [ "mysql://host/dbname?charset=utf8&use_unicode=True", None,
              dict(basedir='my-base-dir', pool_recycle=3600) ])

    def test_mysql_userport(self):
        u = url.make_url("mysql://user:pass@host:1234/dbname")
        kwargs = dict(basedir='my-base-dir')
        u, kwargs, max_conns = self.strat.special_case_mysql(u, kwargs)
        self.assertEqual([ str(u), max_conns, kwargs ],
                [ "mysql://user:pass@host:1234/dbname?charset=utf8&use_unicode=True", None,
              dict(basedir='my-base-dir', pool_recycle=3600) ])

    def test_mysql_local(self):
        u = url.make_url("mysql:///dbname")
        kwargs = dict(basedir='my-base-dir')
        u, kwargs, max_conns = self.strat.special_case_mysql(u, kwargs)
        self.assertEqual([ str(u), max_conns, kwargs ],
                [ "mysql:///dbname?charset=utf8&use_unicode=True", None,
              dict(basedir='my-base-dir', pool_recycle=3600) ])

    def test_mysql_args(self):
        u = url.make_url("mysql:///dbname?foo=bar")
        kwargs = dict(basedir='my-base-dir')
        u, kwargs, max_conns = self.strat.special_case_mysql(u, kwargs)
        self.assertEqual([ str(u), max_conns, kwargs ],
                [ "mysql:///dbname?charset=utf8&foo=bar&use_unicode=True", None,
              dict(basedir='my-base-dir', pool_recycle=3600) ])

    def test_mysql_max_idle(self):
        u = url.make_url("mysql:///dbname?max_idle=1234")
        kwargs = dict(basedir='my-base-dir')
        u, kwargs, max_conns = self.strat.special_case_mysql(u, kwargs)
        self.assertEqual([ str(u), max_conns, kwargs ],
                [ "mysql:///dbname?charset=utf8&use_unicode=True", None,
              dict(basedir='my-base-dir', pool_recycle=1234) ])

    def test_mysql_good_charset(self):
        u = url.make_url("mysql:///dbname?charset=utf8")
        kwargs = dict(basedir='my-base-dir')
        u, kwargs, max_conns = self.strat.special_case_mysql(u, kwargs)
        self.assertEqual([ str(u), max_conns, kwargs ],
                [ "mysql:///dbname?charset=utf8&use_unicode=True", None,
              dict(basedir='my-base-dir', pool_recycle=3600) ])

    def test_mysql_bad_charset(self):
        u = url.make_url("mysql:///dbname?charset=ebcdic")
        kwargs = dict(basedir='my-base-dir')
        self.assertRaises(TypeError, lambda : self.strat.special_case_mysql(u, kwargs))

    def test_mysql_good_use_unicode(self):
        u = url.make_url("mysql:///dbname?use_unicode=True")
        kwargs = dict(basedir='my-base-dir')
        u, kwargs, max_conns = self.strat.special_case_mysql(u, kwargs)
        self.assertEqual([ str(u), max_conns, kwargs ],
                [ "mysql:///dbname?charset=utf8&use_unicode=True", None,
              dict(basedir='my-base-dir', pool_recycle=3600) ])

    def test_mysql_bad_use_unicode(self):
        u = url.make_url("mysql:///dbname?use_unicode=maybe")
        kwargs = dict(basedir='my-base-dir')
        self.assertRaises(TypeError, lambda : self.strat.special_case_mysql(u, kwargs))

class BuildbotEngineStrategy(unittest.TestCase):
    "Test create_engine by creating a sqlite in-memory db"

    def test_create_engine(self):
        engine = enginestrategy.create_engine('sqlite://', basedir="/base")
        self.assertEqual(engine.scalar("SELECT 13 + 14"), 27)
