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

import os
import mock
from twisted.trial import unittest
from buildbot.db import connector
from buildbot.test.util import db

class DBConnector_Basic(db.RealDatabaseMixin, unittest.TestCase):
    """
    Basic tests of the DBConnector class - all start with an empty DB
    """

    def setUp(self):
        d = self.setUpRealDatabase()
        def make_dbc(_):
            self.dbc = connector.DBConnector(mock.Mock(), self.db_url,
                                        os.path.abspath('basedir'))
            self.dbc.start()
        d.addCallback(make_dbc)
        return d

    def tearDown(self):
        self.dbc.stop()
        return self.tearDownRealDatabase()

    def test_runQueryNow_simple(self):
        self.assertEqual(list(self.dbc.runQueryNow("SELECT 1")),
                         [(1,)])

    def test_runQueryNow_exception(self):
        self.assertRaises(Exception, lambda :
            self.dbc.runQueryNow("EAT * FROM cookies"))

    def test_runInterationNow_simple(self):
        def inter(cursor, *args, **kwargs):
            cursor.execute("SELECT 1")
            self.assertEqual(list(cursor.fetchall()), [(1,)])
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
            self.assertEqual(list(res), [(1,)])
        d.addCallback(cb)
        return d
