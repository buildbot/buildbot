# -*- test-case-name: buildbot.broken_test.test_buildreq -*-

from twisted.trial import unittest
from twisted.internet import defer

from buildbot import sourcestamp
from buildbot.buildrequest import BuildRequest
from buildbot.status.builder import SUCCESS, FAILURE
from buildbot.changes.changes import Change
from buildbot.process.properties import Properties
from buildbot.broken_test.runutils import MasterMixin, StallMixin
from buildbot.eventual import fireEventually, flushEventualQueue

class Request(unittest.TestCase):
    def testMerge(self):
        R = BuildRequest
        S = sourcestamp.SourceStamp
        N = 'test_builder'
        b1 =  R("why", S("branch1", None, None, None), N)
        b1r1 = R("why2", S("branch1", "rev1", None, None), N)
        b1r1a = R("why not", S("branch1", "rev1", None, None), N)
        b1r2 = R("why3", S("branch1", "rev2", None, None), N)
        b2r2 = R("why4", S("branch2", "rev2", None, None), N)
        b1r1p1 = R("why5", S("branch1", "rev1", (3, "diff"), None), N)
        c1 = Change("alice", [], "changed stuff", branch="branch1")
        c2 = Change("alice", [], "changed stuff", branch="branch1")
        c3 = Change("alice", [], "changed stuff", branch="branch1")
        c4 = Change("alice", [], "changed stuff", branch="branch1")
        c5 = Change("alice", [], "changed stuff", branch="branch1")
        c6 = Change("alice", [], "changed stuff", branch="branch1")
        b1c1 = R("changes", S("branch1", None, None, [c1,c2,c3]), N)
        b1c2 = R("changes", S("branch1", None, None, [c4,c5,c6]), N)

        self.failUnless(b1.canBeMergedWith(b1))
        self.failIf(b1.canBeMergedWith(b1r1))
        self.failIf(b1.canBeMergedWith(b2r2))
        self.failIf(b1.canBeMergedWith(b1r1p1))
        self.failIf(b1.canBeMergedWith(b1c1))

        self.failIf(b1r1.canBeMergedWith(b1))
        self.failUnless(b1r1.canBeMergedWith(b1r1))
        self.failIf(b1r1.canBeMergedWith(b2r2))
        self.failIf(b1r1.canBeMergedWith(b1r1p1))
        self.failIf(b1r1.canBeMergedWith(b1c1))

        self.failIf(b1r2.canBeMergedWith(b1))
        self.failIf(b1r2.canBeMergedWith(b1r1))
        self.failUnless(b1r2.canBeMergedWith(b1r2))
        self.failIf(b1r2.canBeMergedWith(b2r2))
        self.failIf(b1r2.canBeMergedWith(b1r1p1))

        self.failIf(b1r1p1.canBeMergedWith(b1))
        self.failIf(b1r1p1.canBeMergedWith(b1r1))
        self.failIf(b1r1p1.canBeMergedWith(b1r2))
        self.failIf(b1r1p1.canBeMergedWith(b2r2))
        self.failIf(b1r1p1.canBeMergedWith(b1c1))

        self.failIf(b1c1.canBeMergedWith(b1))
        self.failIf(b1c1.canBeMergedWith(b1r1))
        self.failIf(b1c1.canBeMergedWith(b1r2))
        self.failIf(b1c1.canBeMergedWith(b2r2))
        self.failIf(b1c1.canBeMergedWith(b1r1p1))
        self.failUnless(b1c1.canBeMergedWith(b1c1))
        self.failUnless(b1c1.canBeMergedWith(b1c2))

        sm = b1.mergeWith([])
        self.failUnlessEqual(sm.branch, "branch1")
        self.failUnlessEqual(sm.revision, None)
        self.failUnlessEqual(sm.patch, None)
        self.failUnlessEqual(sm.changes, ())

        ss = b1r1.mergeWith([b1r1])
        self.failUnlessEqual(ss, S("branch1", "rev1", None, None))
        why = b1r1.mergeReasons([b1r1])
        self.failUnlessEqual(why, "why2")
        why = b1r1.mergeReasons([b1r1a])
        self.failUnlessEqual(why, "why2, why not")

        ss = b1c1.mergeWith([b1c2])
        self.failUnlessEqual(ss, S("branch1", None, None, [c1,c2,c3,c4,c5,c6]))
        why = b1c1.mergeReasons([b1c2])
        self.failUnlessEqual(why, "changes")



# replaces test_buildreq.Set.testBuildSet
# exercises db.DBConnector.:
#    def create_buildset(self, ssid, reason, properties, builderNames, t,
#    def get_buildrequestids_for_buildset(self, bsid):
#    def examine_buildset(self, bsid):
# also uses:
#    def get_unclaimed_buildrequests(self, buildername, old, master_name,
#    def claim_buildrequests(self, now, master_name, master_incarnation, brids,
#    def retire_buildrequests(self, brids, results):

class BuildSet(MasterMixin, StallMixin, unittest.TestCase):
    def test_basic(self):
        self.basedir = "buildset/BuildSet/basic"
        self.create_master()
        db = self.master.db
        run = db.runInteractionNow

        # we must create all the things that go into a buildset
        #c1 = Change(who="brian", files=["foo.c", "subdir/bar.c"],
        #            comments="first change",
        #            revision="1234")
        #db.addChangeToDatabase(c1)
        ss = sourcestamp.SourceStamp(branch="branchy")
        ssid = run(lambda t: db.get_sourcestampid(ss,t))
        props = Properties()
        props.setProperty("pname", "pvalue", "psource")

        bsid = run(lambda t:
                   db.create_buildset(ssid, "reason", props, ["bn1", "bn2"], t))
        mn, mi = "mastername", "incarnation"
        reqs = run(lambda t:
                   db.get_unclaimed_buildrequests("bn1", 1, mn, mi, t))
        self.failUnlessEqual(len(reqs), 1)
        self.failUnlessEqual(reqs[0].reason, "reason")
        self.failUnlessEqual(reqs[0].builderName, "bn1")
        #print reqs[0].properties
        #self.failUnlessEqual(reqs[0].properties["pname"], "pvalue") #BROKEN
        brids = db.get_buildrequestids_for_buildset(bsid)
        bn1_brid = brids["bn1"]
        bn2_brid = brids["bn2"]
        self.failUnlessEqual(bn1_brid, reqs[0].id)
        reqs2 = run(lambda t:
                    db.get_unclaimed_buildrequests("bn2", 1, mn, mi, t))
        self.failUnlessEqual(bn2_brid, reqs2[0].id)

        (successful, finished) = db.examine_buildset(bsid)
        self.failUnlessEqual(successful, None)
        self.failUnlessEqual(finished, False)

        bs = self.master.status.getBuildSets()
        self.failUnlessEqual(len(bs), 1)
        brs = bs[0].getBuilderNamesAndBuildRequests()
        self.failUnlessEqual(sorted(brs.keys()), ["bn1", "bn2"])
        self.failUnlessEqual(sorted(bs[0].getBuilderNames()), ["bn1", "bn2"])
        self.failUnlessEqual(len(bs[0].getBuildRequests()), 2)
        ss2 = bs[0].getSourceStamp()
        self.failUnlessEqual(ss2.branch, "branchy")
        self.failUnlessEqual(bs[0].getReason(), "reason")
        self.failUnlessEqual(bs[0].isFinished(), False)
        self.failUnlessEqual(bs[0].getResults(), None)

        db.retire_buildrequests([bn1_brid], SUCCESS)
        self.failUnlessEqual(db.examine_buildset(bsid), (None, False))
        db.retire_buildrequests([bn2_brid], SUCCESS)
        self.failUnlessEqual(db.examine_buildset(bsid), (True, True))

        bsid2 = run(lambda t:
                    db.create_buildset(ssid, "reason", props, ["bn1","bn2"], t))
        brids2 = db.get_buildrequestids_for_buildset(bsid2)
        self.failUnlessEqual(db.examine_buildset(bsid2), (None, False))
        db.retire_buildrequests([brids2["bn1"]], SUCCESS)
        self.failUnlessEqual(db.examine_buildset(bsid2), (None, False))
        db.retire_buildrequests([brids2["bn2"]], FAILURE)
        self.failUnlessEqual(db.examine_buildset(bsid2), (False, True))

        bsid3 = run(lambda t:
                    db.create_buildset(ssid, "reason", props, ["bn1","bn2"], t))
        brids3 = db.get_buildrequestids_for_buildset(bsid3)
        self.failUnlessEqual(db.examine_buildset(bsid3), (None, False))
        db.retire_buildrequests([brids3["bn1"]], FAILURE)
        self.failUnlessEqual(db.examine_buildset(bsid3), (False, False))
        db.retire_buildrequests([brids3["bn2"]], SUCCESS)
        self.failUnlessEqual(db.examine_buildset(bsid3), (False, True))

    def test_subscribe(self):
        self.basedir = "buildset/BuildSet/subscribe"
        self.create_master()
        db = self.master.db
        run = db.runInteractionNow

        ss = sourcestamp.SourceStamp(branch="branchy")
        ssid = run(lambda t: db.get_sourcestampid(ss,t))

        d = defer.succeed(None)
        d.addCallback(self._setup_subscribe, ssid)
        d.addCallback(self._subscribe_test1)
        d.addCallback(self._setup_subscribe, ssid)
        d.addCallback(self._subscribe_test2)
        d.addCallback(self._setup_subscribe, ssid)
        d.addCallback(self._subscribe_test3)
        return d

    def _setup_subscribe(self, ign, ssid):
        db = self.master.db
        run = db.runInteractionNow
        props = Properties()
        bsid = run(lambda t:
                   db.create_buildset(ssid, "reason", props,
                                      ["bn1", "bn2"], t))
        mn, mi = "mastername", "incarnation"
        brids = db.get_buildrequestids_for_buildset(bsid)
        bss = self.master.status.getBuildSets()[0]
        success_events = []
        bss.waitUntilSuccess().addCallback(success_events.append)
        finished_events = []
        bss.waitUntilFinished().addCallback(finished_events.append)

        return brids, bss, success_events, finished_events

    def _subscribe_test1(self, res):
        db = self.master.db
        (brids, bss, success_events, finished_events) = res
        d = fireEventually()
        def _check1(ign):
            self.failUnlessEqual(len(success_events), 0)
            self.failUnlessEqual(len(finished_events), 0)
            db.retire_buildrequests([brids["bn1"]], SUCCESS)
            return flushEventualQueue()
        d.addCallback(_check1)
        def _check2(ign):
            self.failUnlessEqual(len(success_events), 0)
            self.failUnlessEqual(len(finished_events), 0)
            db.retire_buildrequests([brids["bn2"]], SUCCESS)
            return flushEventualQueue()
        d.addCallback(_check2)
        def _check3(ign):
            self.failUnlessEqual(len(success_events), 1)
            self.failUnlessEqual(len(finished_events), 1)
            self.failUnlessIdentical(bss.__class__,
                                     success_events[0].__class__)
            self.failUnlessEqual(success_events[0].isFinished(), True)
            self.failUnlessEqual(success_events[0].getResults(), SUCCESS)
            self.failUnlessEqual(finished_events[0].getResults(), SUCCESS)
            return flushEventualQueue()
        d.addCallback(_check3)
        return d

    def _subscribe_test2(self, res):
        db = self.master.db
        (brids, bss, success_events, finished_events) = res
        d = fireEventually()
        def _check1(ign):
            self.failUnlessEqual(len(success_events), 0)
            self.failUnlessEqual(len(finished_events), 0)
            db.retire_buildrequests([brids["bn1"]], SUCCESS)
            return flushEventualQueue()
        d.addCallback(_check1)
        def _check2(ign):
            self.failUnlessEqual(len(success_events), 0)
            self.failUnlessEqual(len(finished_events), 0)
            db.retire_buildrequests([brids["bn2"]], FAILURE)
            return flushEventualQueue()
        d.addCallback(_check2)
        def _check3(ign):
            self.failUnlessEqual(len(success_events), 1)
            self.failUnlessEqual(len(finished_events), 1)
            self.failUnlessIdentical(bss.__class__,
                                     success_events[0].__class__)
            self.failUnlessEqual(success_events[0].isFinished(), True)
            self.failUnlessEqual(success_events[0].getResults(), FAILURE)
            self.failUnlessEqual(finished_events[0].getResults(), FAILURE)
            return flushEventualQueue()
        d.addCallback(_check3)
        return d

    def _subscribe_test3(self, res):
        db = self.master.db
        (brids, bss, success_events, finished_events) = res
        d = fireEventually()
        def _check1(ign):
            self.failUnlessEqual(len(success_events), 0)
            self.failUnlessEqual(len(finished_events), 0)
            db.retire_buildrequests([brids["bn1"]], FAILURE)
            return flushEventualQueue()
        d.addCallback(_check1)
        def _check2(ign):
            self.failUnlessEqual(len(success_events), 1)
            self.failUnlessEqual(len(finished_events), 0)
            self.failUnlessEqual(success_events[0].isFinished(), False)
            self.failUnlessEqual(success_events[0].getResults(), None)
            db.retire_buildrequests([brids["bn2"]], SUCCESS)
            return flushEventualQueue()
        d.addCallback(_check2)
        def _check3(ign):
            self.failUnlessEqual(len(success_events), 1)
            self.failUnlessEqual(len(finished_events), 1)
            self.failUnlessIdentical(bss.__class__,
                                     success_events[0].__class__)
            self.failUnlessEqual(success_events[0].isFinished(), True)
            self.failUnlessEqual(success_events[0].getResults(), FAILURE)
            self.failUnlessEqual(finished_events[0].getResults(), FAILURE)
            return flushEventualQueue()
        d.addCallback(_check3)
        return d

