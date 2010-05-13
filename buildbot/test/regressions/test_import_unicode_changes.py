import os
import shutil
import cPickle

from twisted.trial import unittest

from buildbot.changes.changes import Change, OldChangeMaster

from buildbot.db.schema import manager
from buildbot.db.dbspec import DBSpec
from buildbot.db.connector import DBConnector

import buildbot

class Thing:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class TestUnicodeChanges(unittest.TestCase):
    def setUp(self):
        self.basedir = "UnicodeChanges"
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        os.makedirs(self.basedir)

        # Now try the upgrade process, which will import the old changes.
        self.spec = DBSpec.from_url("sqlite:///state.sqlite", self.basedir)

        self.db = DBConnector(self.spec)
        self.db.start()

    def tearDown(self):
        if self.db:
            self.db.stop()

    def testUnicodeChange(self):
        # Create changes.pck
        changes = [Change(who=u"Frosty the \N{SNOWMAN}".encode("utf8"),
            files=["foo"], comments=u"Frosty the \N{SNOWMAN}".encode("utf8"),
            branch="b1", revision=12345)]
        cPickle.dump(Thing(changes=changes), open(os.path.join(self.basedir,
            "changes.pck"), "w"))

        sm = manager.DBSchemaManager(self.spec, self.basedir)
        sm.upgrade(quiet=True)

        c = self.db.getChangeNumberedNow(1)

        self.assertEquals(c.who, u"Frosty the \N{SNOWMAN}")
        self.assertEquals(c.comments, u"Frosty the \N{SNOWMAN}")

    def testNonUnicodeChange(self):
        # Create changes.pck
        changes = [Change(who="\xff\xff\x00", files=["foo"],
            comments="\xff\xff\x00", branch="b1", revision=12345)]
        cPickle.dump(Thing(changes=changes), open(os.path.join(self.basedir,
            "changes.pck"), "w"))

        sm = manager.DBSchemaManager(self.spec, self.basedir)
        self.assertRaises(UnicodeError, lambda : sm.upgrade(quiet=True))

    def testAsciiChange(self):
        # Create changes.pck
        changes = [Change(who="Frosty the Snowman",
            files=["foo"], comments="Frosty the Snowman", branch="b1", revision=12345)]
        cPickle.dump(Thing(changes=changes), open(os.path.join(self.basedir,
            "changes.pck"), "w"))

        sm = manager.DBSchemaManager(self.spec, self.basedir)
        sm.upgrade(quiet=True)

        c = self.db.getChangeNumberedNow(1)

        self.assertEquals(c.who, "Frosty the Snowman")
        self.assertEquals(c.comments, "Frosty the Snowman")

    def testUTF16Change(self):
        # Create changes.pck
        cm = OldChangeMaster()
        cm.changes = [Change(who=u"Frosty the \N{SNOWMAN}".encode("utf16"),
            files=["foo"], comments=u"Frosty the \N{SNOWMAN}".encode("utf16"),
            branch="b1", revision=12345)]

        # instead of running contrib/fix_changes_pickle_encoding.py, we just call
        # the changemanager's recode_changes directly - it's the function at the
        # heart of the script anyway.
        cm.recode_changes('utf16', quiet=True)

        # and dump the recoded changemanager to changes.pck before trying a schema upgrade
        cPickle.dump(cm, open(os.path.join(self.basedir, "changes.pck"), "w"))

        sm = manager.DBSchemaManager(self.spec, self.basedir)
        sm.upgrade(quiet=True)

        c = self.db.getChangeNumberedNow(1)

        self.assertEquals(c.who, u"Frosty the \N{SNOWMAN}")
        self.assertEquals(c.comments, u"Frosty the \N{SNOWMAN}")

class TestMySQLDBUnicodeChanges(TestUnicodeChanges):
    def setUp(self):
        self.basedir = "MySQLDBUnicodeChanges"
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        os.makedirs(self.basedir)

        # Now try the upgrade process, which will import the old changes.
        self.spec = DBSpec.from_url(
                "mysql://buildbot_test:buildbot_test@localhost/buildbot_test", self.basedir)

        self.db = DBConnector(self.spec)
        self.db.start()

        result = self.db.runQueryNow("SHOW TABLES")
        for row in result:
            self.db.runQueryNow("DROP TABLE %s" % row[0])
        self.db.runQueryNow("COMMIT")

try:
    import MySQLdb
    conn = MySQLdb.connect(user="buildbot_test", db="buildbot_test",
            passwd="buildbot_test", use_unicode=True, charset='utf8')
except:
    TestMySQLDBUnicodeChanges.skip = True
