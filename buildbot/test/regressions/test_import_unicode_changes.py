import os
import shutil
import cPickle

from twisted.trial import unittest

from buildbot.changes.changes import Change

from buildbot.db.schema import manager
from buildbot.db.dbspec import DBSpec
from buildbot.db.connector import DBConnector

class Thing:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class TestUnicodeChanges(unittest.TestCase):
    def setUp(self):
        self.basedir = "UnicodeChanges"
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        os.makedirs(self.basedir)
        self.db = None

    def tearDown(self):
        if self.db:
            self.db.stop()

    def testUnicodeChange(self):
        # Create changes.pck
        changes = [Change(who=u"Frosty the \N{SNOWMAN}".encode("utf8"),
            files=["foo"], comments=u"Frosty the \N{SNOWMAN}".encode("utf8"), branch="b1", revision=12345)]
        cPickle.dump(Thing(changes=changes), open(os.path.join(self.basedir, "changes.pck"), "w"))

        # Now try the upgrade process, which will import the old changes.
        spec = DBSpec.from_url("sqlite:///state.sqlite", self.basedir)

        sm = manager.DBSchemaManager(spec, self.basedir)
        sm.upgrade()
        self.db = DBConnector(spec)
        self.db.start()

        c = self.db.getChangeNumberedNow(1)

        self.assertEquals(c.who, u"Frosty the \N{SNOWMAN}")
        self.assertEquals(c.comments, u"Frosty the \N{SNOWMAN}")
