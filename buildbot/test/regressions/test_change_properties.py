import os
import shutil

from twisted.trial import unittest

from buildbot.changes.changes import Change

from buildbot import util

from buildbot.db.schema import manager
from buildbot.db.dbspec import DBSpec
from buildbot.db.connector import DBConnector

class TestChangeProperties(unittest.TestCase):
    def setUp(self):
        self.basedir = "ChangeProperties"
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        os.makedirs(self.basedir)

        self.spec = DBSpec.from_url("sqlite:///state.sqlite", self.basedir)

        self.sm = manager.DBSchemaManager(self.spec, self.basedir)
        self.sm.upgrade(quiet=True)
        self.db = DBConnector(self.spec)
        self.db.start()

    def tearDown(self):
        self.db.stop()

        shutil.rmtree(self.basedir)

    def testDBGetChangeNumberedNow(self):
        db = self.db

        c = Change(who="catlee", files=["foo"], comments="", branch="b1")
        c.properties.setProperty("foo", "bar", "property_source")
        db.addChangeToDatabase(c)

        c1 = db.getChangeNumberedNow(c.number)
        self.assertEquals(c1.properties, c.properties)

        # Flush the cache
        db._change_cache = util.LRUCache()

        c1 = db.getChangeNumberedNow(c.number)
        self.assertEquals(c1.properties, c.properties)

    def testDBGetChangeByNumber(self):
        db = self.db

        c = Change(who="catlee", files=["foo"], comments="", branch="b1")
        c.properties.setProperty("foo", "bar", "property_source")
        db.addChangeToDatabase(c)

        d = db.getChangeByNumber(c.number)
        def check(c1):
            self.assertEquals(c1.properties, c.properties)
        d.addCallback(check)

        def flush(ign):
            # Flush the cache
            db._change_cache = util.LRUCache()
            return db.getChangeByNumber(c.number)
        d.addCallback(flush)
        d.addCallback(check)
