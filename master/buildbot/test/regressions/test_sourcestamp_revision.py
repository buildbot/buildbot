from twisted.trial import unittest

from buildbot.sourcestamp import SourceStamp
from buildbot.changes.changes import Change

class TestSourceStampRevision(unittest.TestCase):
    def testNoRevision(self):
        c = Change(who="catlee", files=["foo"], comments="", branch="b1", revision=None)
        ss = SourceStamp(changes=[c])

        self.assertEquals(ss.revision, None)
