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

from buildbot.db import util

class FakeDBAPI(object):
    def __init__(self, paramstyle):
        self.paramstyle = paramstyle

class SQLUtils(unittest.TestCase):

    def test_sql_insert_single_qmark(self):
        dbapi = FakeDBAPI('qmark')
        self.assertEqual(util.sql_insert(dbapi, 'colors', ('color',)),
                "INSERT INTO colors (color) VALUES (?)")

    def test_sql_insert_multi_qmark(self):
        dbapi = FakeDBAPI('qmark')
        self.assertEqual(util.sql_insert(dbapi, 'widgets', ('len', 'wid')),
                "INSERT INTO widgets (len, wid) VALUES (?,?)")

    def test_sql_insert_single_numeric(self):
        dbapi = FakeDBAPI('numeric')
        self.assertEqual(util.sql_insert(dbapi, 'colors', ('color',)),
                "INSERT INTO colors (color) VALUES (:1)")

    def test_sql_insert_multi_numeric(self):
        dbapi = FakeDBAPI('numeric')
        self.assertEqual(util.sql_insert(dbapi, 'widgets', ('len', 'wid')),
                "INSERT INTO widgets (len, wid) VALUES (:1,:2)")

    def test_sql_insert_single_format(self):
        dbapi = FakeDBAPI('format')
        self.assertEqual(util.sql_insert(dbapi, 'colors', ('color',)),
                "INSERT INTO colors (color) VALUES (%s)")

    def test_sql_insert_multi_format(self):
        dbapi = FakeDBAPI('format')
        self.assertEqual(util.sql_insert(dbapi, 'widgets', ('len', 'wid')),
                "INSERT INTO widgets (len, wid) VALUES (%s,%s)")

