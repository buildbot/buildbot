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

from sqlalchemy.engine import url
from sqlalchemy.pool import NullPool

from twisted.python import runtime
from twisted.trial import unittest

from buildbot.db import enginestrategy


class BuildbotEngineStrategy_special_cases(unittest.TestCase):

    "Test the special case methods, without actually creating a db"

    # used several times below
    mysql_kwargs = dict(
        basedir='my-base-dir',
        connect_args=dict(init_command='SET default_storage_engine=MyISAM'),
        pool_recycle=3600)
    sqlite_kwargs = dict(basedir='/my-base-dir', poolclass=NullPool)

    def setUp(self):
        self.strat = enginestrategy.BuildbotEngineStrategy()

    # utility

    def filter_kwargs(self, kwargs):
        # filter out the listeners list to just include the class name
        if 'listeners' in kwargs:
            kwargs['listeners'] = [lstnr.__class__.__name__
                                   for lstnr in kwargs['listeners']]
        return kwargs

    # tests

    def test_sqlite_pct_sub(self):
        u = url.make_url("sqlite:///%(basedir)s/x/state.sqlite")
        kwargs = dict(basedir='/my-base-dir')
        u, kwargs, max_conns = self.strat.special_case_sqlite(u, kwargs)
        self.assertEqual([str(u), max_conns, self.filter_kwargs(kwargs)],
                         ["sqlite:////my-base-dir/x/state.sqlite", 1,
                          self.sqlite_kwargs])

    def test_sqlite_relpath(self):
        url_src = "sqlite:///x/state.sqlite"
        basedir = "/my-base-dir"
        expected_url = "sqlite:////my-base-dir/x/state.sqlite"

        # this looks a whole lot different on windows
        if runtime.platformType == 'win32':
            url_src = r'sqlite:///X\STATE.SQLITE'
            basedir = r'C:\MYBASE~1'
            expected_url = r'sqlite:///C:\MYBASE~1\X\STATE.SQLITE'

        exp_kwargs = self.sqlite_kwargs.copy()
        exp_kwargs['basedir'] = basedir

        u = url.make_url(url_src)
        kwargs = dict(basedir=basedir)
        u, kwargs, max_conns = self.strat.special_case_sqlite(u, kwargs)
        self.assertEqual([str(u), max_conns, self.filter_kwargs(kwargs)],
                         [expected_url, 1, exp_kwargs])

    def test_sqlite_abspath(self):
        u = url.make_url("sqlite:////x/state.sqlite")
        kwargs = dict(basedir='/my-base-dir')
        u, kwargs, max_conns = self.strat.special_case_sqlite(u, kwargs)
        self.assertEqual([str(u), max_conns, self.filter_kwargs(kwargs)],
                         ["sqlite:////x/state.sqlite", 1, self.sqlite_kwargs])

    def test_sqlite_memory(self):
        u = url.make_url("sqlite://")
        kwargs = dict(basedir='my-base-dir')
        u, kwargs, max_conns = self.strat.special_case_sqlite(u, kwargs)
        self.assertEqual([str(u), max_conns, self.filter_kwargs(kwargs)],
                         ["sqlite://", 1,  # only one conn at a time
                          dict(basedir='my-base-dir',
                               connect_args=dict(check_same_thread=False))])

    def test_mysql_simple(self):
        u = url.make_url("mysql://host/dbname")
        kwargs = dict(basedir='my-base-dir')
        u, kwargs, max_conns = self.strat.special_case_mysql(u, kwargs)
        self.assertEqual([str(u), max_conns, self.filter_kwargs(kwargs)],
                         ["mysql://host/dbname?charset=utf8&use_unicode=True", None,
                          self.mysql_kwargs])

    def test_mysql_userport(self):
        u = url.make_url("mysql://user:pass@host:1234/dbname")
        kwargs = dict(basedir='my-base-dir')
        u, kwargs, max_conns = self.strat.special_case_mysql(u, kwargs)
        self.assertEqual([str(u), max_conns, self.filter_kwargs(kwargs)],
                         ["mysql://user:pass@host:1234/dbname?"
                          "charset=utf8&use_unicode=True", None, self.mysql_kwargs])

    def test_mysql_local(self):
        u = url.make_url("mysql:///dbname")
        kwargs = dict(basedir='my-base-dir')
        u, kwargs, max_conns = self.strat.special_case_mysql(u, kwargs)
        self.assertEqual([str(u), max_conns, self.filter_kwargs(kwargs)],
                         ["mysql:///dbname?charset=utf8&use_unicode=True", None,
                          self.mysql_kwargs])

    def test_mysql_args(self):
        u = url.make_url("mysql:///dbname?foo=bar")
        kwargs = dict(basedir='my-base-dir')
        u, kwargs, max_conns = self.strat.special_case_mysql(u, kwargs)
        self.assertEqual([str(u), max_conns, self.filter_kwargs(kwargs)],
                         ["mysql:///dbname?charset=utf8&foo=bar&use_unicode=True",
                          None, self.mysql_kwargs])

    def test_mysql_max_idle(self):
        u = url.make_url("mysql:///dbname?max_idle=1234")
        kwargs = dict(basedir='my-base-dir')
        u, kwargs, max_conns = self.strat.special_case_mysql(u, kwargs)
        exp = self.mysql_kwargs.copy()
        exp['pool_recycle'] = 1234
        self.assertEqual([str(u), max_conns, self.filter_kwargs(kwargs)],
                         ["mysql:///dbname?charset=utf8&use_unicode=True", None,
                          exp])

    def test_mysql_good_charset(self):
        u = url.make_url("mysql:///dbname?charset=utf8")
        kwargs = dict(basedir='my-base-dir')
        u, kwargs, max_conns = self.strat.special_case_mysql(u, kwargs)
        self.assertEqual([str(u), max_conns, self.filter_kwargs(kwargs)],
                         ["mysql:///dbname?charset=utf8&use_unicode=True", None,
                          self.mysql_kwargs])

    def test_mysql_bad_charset(self):
        u = url.make_url("mysql:///dbname?charset=ebcdic")
        kwargs = dict(basedir='my-base-dir')
        self.assertRaises(TypeError,
                          lambda: self.strat.special_case_mysql(u, kwargs))

    def test_mysql_good_use_unicode(self):
        u = url.make_url("mysql:///dbname?use_unicode=True")
        kwargs = dict(basedir='my-base-dir')
        u, kwargs, max_conns = self.strat.special_case_mysql(u, kwargs)
        self.assertEqual([str(u), max_conns, self.filter_kwargs(kwargs)],
                         ["mysql:///dbname?charset=utf8&use_unicode=True", None,
                          self.mysql_kwargs])

    def test_mysql_bad_use_unicode(self):
        u = url.make_url("mysql:///dbname?use_unicode=maybe")
        kwargs = dict(basedir='my-base-dir')
        self.assertRaises(TypeError,
                          lambda: self.strat.special_case_mysql(u, kwargs))

    def test_mysql_storage_engine(self):
        u = url.make_url("mysql:///dbname?storage_engine=foo")
        kwargs = dict(basedir='my-base-dir')
        u, kwargs, max_conns = self.strat.special_case_mysql(u, kwargs)
        exp = self.mysql_kwargs.copy()
        exp['connect_args'] = dict(
            init_command='SET default_storage_engine=foo')
        self.assertEqual([str(u), max_conns, self.filter_kwargs(kwargs)],
                         ["mysql:///dbname?charset=utf8&use_unicode=True", None,
                          exp])


class BuildbotEngineStrategy(unittest.TestCase):

    "Test create_engine by creating a sqlite in-memory db"

    def test_create_engine(self):
        engine = enginestrategy.create_engine('sqlite://', basedir="/base")
        self.assertEqual(engine.scalar("SELECT 13 + 14"), 27)
