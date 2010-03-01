import os
import threading

from zope.interface import implements
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

