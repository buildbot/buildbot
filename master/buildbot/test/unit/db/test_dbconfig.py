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

from twisted.internet import defer
from twisted.internet import threads
from twisted.trial import unittest

from buildbot import config as config_module
from buildbot.db import dbconfig
from buildbot.test.fake import fakemaster


class TestDbConfig(unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self):
        # as we will open the db twice, we can't use in memory sqlite
        self.master = yield fakemaster.make_master(
            self, wantRealReactor=True, wantDb=True, sqlite_memory=False
        )
        self.db_config = {
            "db_url": self.master.db.configured_db_config.db_url,
            "engine_kwargs": self.master.db.configured_db_config.engine_kwargs,
        }
        yield threads.deferToThread(self.createDbConfig)

    def createDbConfig(self):
        self.dbConfig = dbconfig.DbConfig(self.db_config, self.master.basedir)

    def test_basic(self):
        def thd():
            workersInDB = ['foo', 'bar']
            self.dbConfig.set("workers", workersInDB)
            workers = self.dbConfig.get("workers")
            self.assertEqual(workers, workersInDB)

        return threads.deferToThread(thd)

    def test_default(self):
        def thd():
            workers = self.dbConfig.get("workers", "default")
            self.assertEqual(workers, "default")

        return threads.deferToThread(thd)

    def test_error(self):
        def thd():
            with self.assertRaises(KeyError):
                self.dbConfig.get("workers")

        return threads.deferToThread(thd)

    # supports the 3 different ways to declare db_url in the master.cfg
    def test_init1(self):
        obj = dbconfig.DbConfig({"db_url": self.db_config['db_url']}, self.master.basedir)
        self.assertEqual(
            obj.db_config,
            config_module.master.DBConfig(
                self.db_config['db_url'], self.db_config['engine_kwargs']
            ),
        )

    def test_init2(self):
        obj = dbconfig.DbConfig({"db": self.db_config}, self.master.basedir)
        self.assertEqual(
            obj.db_config,
            config_module.master.DBConfig(
                self.db_config['db_url'], self.db_config['engine_kwargs']
            ),
        )

    def test_init3(self):
        obj = dbconfig.DbConfig({}, self.master.basedir)
        self.assertEqual(obj.db_config, config_module.master.DBConfig("sqlite:///state.sqlite"))


class TestDbConfigNotInitialized(unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self):
        # as we will open the db twice, we can't use in memory sqlite
        self.master = yield fakemaster.make_master(
            self, wantRealReactor=True, wantDb=True, sqlite_memory=False
        )
        self.db_url = self.master.db.configured_db_config.db_url

    def createDbConfig(self, db_url=None):
        return dbconfig.DbConfig({"db_url": db_url or self.db_url}, self.master.basedir)

    def test_default(self):
        def thd():
            db = self.createDbConfig()
            self.assertEqual("foo", db.get("workers", "foo"))

        return threads.deferToThread(thd)

    def test_error(self):
        def thd():
            db = self.createDbConfig()
            with self.assertRaises(KeyError):
                db.get("workers")

        return threads.deferToThread(thd)

    def test_bad_url(self):
        def thd():
            db = self.createDbConfig("garbage://")
            with self.assertRaises(KeyError):
                db.get("workers")

        return threads.deferToThread(thd)

    def test_bad_url2(self):
        def thd():
            db = self.createDbConfig("trash")
            with self.assertRaises(KeyError):
                db.get("workers")

        return threads.deferToThread(thd)

    def test_bad_url3(self):
        def thd():
            db = self.createDbConfig("sqlite://bad")
            with self.assertRaises(KeyError):
                db.get("workers")

        return threads.deferToThread(thd)
