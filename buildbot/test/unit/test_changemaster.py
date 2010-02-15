# -*- test-case-name: buildbot.test.test_changemaster -*-

from twisted.trial import unittest

from buildbot.changes.changes import Change
from buildbot.test.runutils import MasterMixin, StallMixin

class TestManager(MasterMixin, StallMixin, unittest.TestCase):
    def testAddChange(self):
        self.basedir = "changemaster/manager/addchange"
        self.create_master()

        m = self.master.change_svc

        change = Change('user', [], 'comments', revision="123")
        m.addChange(change)
        d = self.stall(None, 0.5)
        def _check(ign):
            events = list(m.eventGenerator())
            self.failUnlessEqual(len(events), 1)
            self.failUnlessEqual(events[0].who, "user")
            self.failUnlessEqual(events[0].files, [])
            self.failUnlessEqual(events[0].number, 1)
            c1 = m.getChangeNumberedNow(1)
            self.failUnlessIdentical(c1, events[0]) # should be cached
            r = m.getChangesGreaterThan(0)
            self.failUnlessEqual(r, [c1])
            self.c1 = c1
        d.addCallback(_check)
        d.addCallback(lambda ign: m.getChangeByNumber(1))
        d.addCallback(lambda r: self.failUnlessEqual(r, self.c1))
        d.addCallback(lambda ign: m.getChangesByNumber([1]))
        d.addCallback(lambda r: self.failUnlessEqual(r, [self.c1]))

        change2 = Change('otheruser', ["foo.c"], "comments2", revision="124")
        d.addCallback(lambda ign: m.addChange(change2))
        d.addCallback(self.stall, 0.5)
        def _then(ign):
            events = list(m.eventGenerator())
            self.failUnlessEqual(len(events), 2)
            self.failUnlessEqual(events[0].who, "otheruser")
            self.failUnlessEqual(events[0].files, ["foo.c"])
            self.failUnlessEqual(events[0].number, 2)
            self.failUnlessEqual(events[1], self.c1)
            c1a = m.getChangeNumberedNow(1)
            self.failUnlessIdentical(c1a, self.c1)
            c2 = m.getChangeNumberedNow(2)
            self.failUnlessIdentical(c2, events[0])
            r = m.getChangesGreaterThan(0)
            self.failUnlessEqual(r, [self.c1, c2])

            d = m.getChangeByNumber(2)
            d.addCallback(lambda r: self.failUnlessEqual(r, c2))
            d.addCallback(lambda ign: m.getChangesByNumber([2,1]))
            d.addCallback(lambda r: self.failUnlessEqual(r, [c2,self.c1]))
            return d
        d.addCallback(_then)
        return d
