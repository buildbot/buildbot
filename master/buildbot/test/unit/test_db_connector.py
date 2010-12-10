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

from twisted.trial import unittest

from buildbot.db import dbspec, connector
from buildbot.test.util import threads

class DBConnector_Basic(threads.ThreadLeakMixin, unittest.TestCase):
    """
    Basic tests of the DBConnector class - all start with an empty DB
    """

    def setUp(self):
        self.setUpThreadLeak()
        # use an in-memory sqlite database to test
        self.dbc = connector.DBConnector(dbspec.DBSpec.from_url("sqlite://"))
        self.dbc.start()

    def tearDown(self):
        self.dbc.stop()
        self.tearDownThreadLeak()

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
