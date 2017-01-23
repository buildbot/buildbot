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

from twisted.internet import defer
from twisted.internet import threads
from twisted.trial import unittest

from buildbot.db import dbconfig
from buildbot.test.util import db


class TestDbConfig(db.RealDatabaseMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        # as we will open the db twice, we can't use in memory sqlite
        yield self.setUpRealDatabase(table_names=['objects', 'object_state'], sqlite_memory=False)
        yield threads.deferToThread(self.createDbConfig)

    def createDbConfig(self):
        self.dbConfig = dbconfig.DbConfig(
            {"db_url": self.db_url}, self.basedir)

    def tearDown(self):
        return self.tearDownRealDatabase()

    def test_basic(self):
        def thd():
            workersInDB = ['foo', 'bar']
            self.dbConfig.set(u"workers", workersInDB)
            workers = self.dbConfig.get(u"workers")
            self.assertEqual(workers, workersInDB)

        return threads.deferToThread(thd)

    def test_default(self):
        def thd():
            workers = self.dbConfig.get(u"workers", "default")
            self.assertEqual(workers, "default")

        return threads.deferToThread(thd)

    def test_error(self):
        def thd():
            self.assertRaises(KeyError, self.dbConfig.get, u"workers")

        return threads.deferToThread(thd)

    # supports the 3 different ways to declare db_url in the master.cfg
    def test_init1(self):
        obj = dbconfig.DbConfig({"db_url": self.db_url}, self.basedir)
        self.assertEqual(obj.db_url, self.db_url)

    def test_init2(self):
        obj = dbconfig.DbConfig({"db": {"db_url": self.db_url}}, self.basedir)
        self.assertEqual(obj.db_url, self.db_url)

    def test_init3(self):
        obj = dbconfig.DbConfig({}, self.basedir)
        self.assertEqual(obj.db_url, "sqlite:///state.sqlite")


class TestDbConfigNotInitialized(db.RealDatabaseMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        # as we will open the db twice, we can't use in memory sqlite
        yield self.setUpRealDatabase(table_names=[], sqlite_memory=False)

    def createDbConfig(self, db_url=None):
        return dbconfig.DbConfig({"db_url": db_url or self.db_url}, self.basedir)

    def test_default(self):
        def thd():
            db = self.createDbConfig()
            self.assertEqual("foo", db.get(u"workers", "foo"))

        return threads.deferToThread(thd)

    def test_error(self):
        def thd():
            db = self.createDbConfig()
            self.assertRaises(KeyError, db.get, u"workers")

        return threads.deferToThread(thd)

    def test_bad_url(self):
        def thd():
            db = self.createDbConfig("garbage://")
            self.assertRaises(KeyError, db.get, u"workers")

        return threads.deferToThread(thd)

    def test_bad_url2(self):
        def thd():
            db = self.createDbConfig("trash")
            self.assertRaises(KeyError, db.get, u"workers")

        return threads.deferToThread(thd)

    def test_bad_url3(self):
        def thd():
            db = self.createDbConfig("sqlite://bad")
            self.assertRaises(KeyError, db.get, u"workers")

        return threads.deferToThread(thd)
