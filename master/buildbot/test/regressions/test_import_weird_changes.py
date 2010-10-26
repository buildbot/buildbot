import os
import shutil
import cPickle

from twisted.trial import unittest

from buildbot.changes.changes import Change

from buildbot.db.schema import manager
from buildbot.db.dbspec import DBSpec
from buildbot.db.connector import DBConnector

class TestWeirdChanges(unittest.TestCase):
    def setUp(self):
        self.basedir = "WeirdChanges"
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
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)

    def mkchanges(self, changes):
        import buildbot.changes.changes
        cm = buildbot.changes.changes.OldChangeMaster()
        cm.changes = changes
        return cm

    def testListsAsFilenames(self):
        # Create changes.pck
        changes = [Change(who=u"Frosty the \N{SNOWMAN}".encode("utf8"),
            files=[["foo","bar"],['bing']], comments=u"Frosty the \N{SNOWMAN}".encode("utf8"),
            branch="b1", revision=12345)]
        cPickle.dump(self.mkchanges(changes), open(os.path.join(self.basedir,
            "changes.pck"), "wb"))

        sm = manager.DBSchemaManager(self.spec, self.basedir)
        sm.upgrade(quiet=True)

        c = self.db.getChangeNumberedNow(1)

        self.assertEquals(sorted(c.files), sorted([u"foo", u"bar", u"bing"]))
