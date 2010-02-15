# -*- test-case-name: buildbot.test.test_scheduler -*-

import os, time

from twisted.trial import unittest

from buildbot import scheduler, sourcestamp
from buildbot.changes.changes import Change
from buildbot.clients import tryclient

from buildbot.test.runutils import MasterMixin, StallMixin
from buildbot.test.pollmixin import PollMixin

class Scheduling(MasterMixin, StallMixin, PollMixin, unittest.TestCase):
    def setSchedulers(self, *schedulers):
        return self.master.scheduler_manager.updateSchedulers(schedulers)

    def testPeriodic1(self):
        self.basedir = 'scheduler/Scheduling/testPeriodic1'
        self.create_master()
        d = self.setSchedulers(scheduler.Periodic("quickly", ["a","b"], 2))
        d.addCallback(lambda ign: self.master.scheduler_manager.trigger())
        d.addCallback(self.stall, 2)
        d.addCallback(lambda ign: self.master.scheduler_manager.when_quiet())
        d.addCallback(self._testPeriodic1_1)
        return d
    def _testPeriodic1_1(self, res):
        bsids = self.master.db.get_active_buildset_ids()
        self.failUnless(len(bsids) > 1)

        (external_idstring, reason, ssid, complete, results) = self.master.db.get_buildset_info(bsids[0])
        reqs = self.master.db.get_buildrequestids_for_buildset(bsids[0])
        self.failUnlessEqual(sorted(reqs.keys()), ["a","b"])
        self.failUnlessEqual(reason, "The Periodic scheduler named 'quickly' triggered this build")

    def testNightly(self):
        # now == 15-Nov-2005, 00:05:36 AM . By using mktime, this is
        # converted into the local timezone, which happens to match what
        # Nightly is going to do anyway.
        MIN=60; HOUR=60*MIN; DAY=24*3600
        now = time.mktime((2005, 11, 15, 0, 5, 36, 1, 319, -1))

        s = scheduler.Nightly('nightly', ["a"], hour=3)
        t = s._calculateNextRunTimeFrom(now)
        self.failUnlessEqual(int(t-now), 2*HOUR+54*MIN+24)

        s = scheduler.Nightly('nightly', ["a"], minute=[3,8,54])
        t = s._calculateNextRunTimeFrom(now)
        self.failUnlessEqual(int(t-now), 2*MIN+24)

        s = scheduler.Nightly('nightly', ["a"],
                              dayOfMonth=16, hour=1, minute=6)
        t = s._calculateNextRunTimeFrom(now)
        self.failUnlessEqual(int(t-now), DAY+HOUR+24)

        s = scheduler.Nightly('nightly', ["a"],
                              dayOfMonth=16, hour=1, minute=3)
        t = s._calculateNextRunTimeFrom(now)
        self.failUnlessEqual(int(t-now), DAY+57*MIN+24)

        s = scheduler.Nightly('nightly', ["a"],
                              dayOfMonth=15, hour=1, minute=3)
        t = s._calculateNextRunTimeFrom(now)
        self.failUnlessEqual(int(t-now), 57*MIN+24)

        s = scheduler.Nightly('nightly', ["a"],
                              dayOfMonth=15, hour=0, minute=3)
        t = s._calculateNextRunTimeFrom(now)
        self.failUnlessEqual(int(t-now), 30*DAY-3*MIN+24)


    def isImportant(self, change):
        if "important" in change.files:
            return True
        return False

    def testOffBranch(self):
        self.basedir = 'scheduler/Scheduling/OffBranch'
        self.create_master()
        s = scheduler.Scheduler("b1", "branch1", 2, ["a","b"],
                                fileIsImportant=self.isImportant)
        d = self.setSchedulers(s)

        def _addChange(ign, c):
            self.master.change_svc.addChange(c)
            return self.master.scheduler_manager.when_quiet()

        c0 = Change("carol", ["important"], "other branch", branch="other")
        d.addCallback(_addChange, c0)

        def _check(ign):
            important, unimportant = self.master.db.runInteractionNow(
                    lambda t: self.master.db.scheduler_get_classified_changes(s.schedulerid, t))
            self.failIf(important)
            self.failIf(unimportant)

        d.addCallback(_check)

    def testImportantChanges(self):
        self.basedir = 'scheduler/Scheduling/ImportantChanges'
        self.create_master()
        s = scheduler.Scheduler("b1", "branch1", 2, ["a","b"],
                                fileIsImportant=self.isImportant)

        # Hijack run to prevent changes from being processed
        oldrun = s.run
        s.run = lambda: None

        d = self.setSchedulers(s)

        def _addChange(ign, c):
            self.master.change_svc.addChange(c)
            self.master.scheduler_manager.trigger()
            return self.master.db.runInteraction(s.classify_changes)

        c1 = Change("alice", ["important", "not important"], "some changes",
                    branch="branch1")
        d.addCallback(_addChange, c1)
        c2 = Change("bob", ["not important", "boring"], "some more changes",
                    branch="branch1")
        d.addCallback(_addChange, c2)
        c3 = Change("carol", ["important", "dull"], "even more changes",
                    branch="branch1")
        d.addCallback(_addChange, c3)

        def _check(ign):
            important, unimportant = self.master.db.runInteractionNow(
                    lambda t: self.master.db.scheduler_get_classified_changes(s.schedulerid, t))
            important = [c.number for c in important]
            unimportant = [c.number for c in unimportant]
            self.failUnlessEqual(important, [c1.number,c3.number])
            self.failUnlessEqual(unimportant, [c2.number])
            s.run = oldrun
            d1 = s.run()
            d1.addCallback(lambda ign: self.master.scheduler_manager.trigger())
            d1.addCallback(lambda ign: self.master.scheduler_manager.when_quiet())
            return d1

        d.addCallback(_check)
        d.addCallback(self._testBranch_1)
        return d

    def _testBranch_1(self, res):
        bsids = self.master.db.get_active_buildset_ids()
        self.failUnlessEqual(len(bsids), 1)

        (external_idstring, reason, ssid, complete, results) = self.master.db.get_buildset_info(bsids[0])
        s = self.master.db.getSourceStampNumberedNow(ssid)
        self.failUnlessEqual(s.branch, "branch1")
        # TODO: Fixme when change.revision = None is mapped to something else
        self.failUnlessEqual(s.revision, 'None')
        self.failUnlessEqual(len(s.changes), 3)
        self.failUnlessEqual(s.patch, None)


    def testAnyBranch(self):
        self.basedir = 'scheduler/Scheduling/AnyBranch'
        self.create_master()
        s = scheduler.AnyBranchScheduler("b1", 1, ["a", "b"],
                                         fileIsImportant=self.isImportant)
        d = self.setSchedulers(s)

        def _addChange(ign, c):
            self.master.change_svc.addChange(c)

        c1 = Change("alice", ["important", "not important"], "some changes",
                    branch="branch1")
        d.addCallback(_addChange, c1)
        c2 = Change("bob", ["not important", "boring"], "some more changes",
                    branch="branch1")
        d.addCallback(_addChange, c2)
        c3 = Change("carol", ["important", "dull"], "even more changes",
                    branch="branch1")
        d.addCallback(_addChange, c3)

        c4 = Change("carol", ["important"], "other branch", branch="branch2")
        d.addCallback(_addChange, c4)

        c5 = Change("carol", ["important"], "default branch", branch=None)
        d.addCallback(_addChange, c5)

        d.addCallback(lambda ign: self.master.scheduler_manager.when_quiet())

        d.addCallback(self._testAnyBranch_1)
        return d
    def _testAnyBranch_1(self, res):
        bsids = self.master.db.get_active_buildset_ids()
        self.failUnlessEqual(len(bsids), 3)

        sources = []
        for bsid in bsids:
            (external_idstring, reason, ssid, complete, results) = self.master.db.get_buildset_info(bsid)
            s = self.master.db.getSourceStampNumberedNow(ssid)
            sources.append(s)

        sources.sort(lambda a,b: cmp(a.branch, b.branch))

        s1 = sources[0]
        self.failUnlessEqual(s1.branch, None)
        # TODO: Fixme when change.revision = None is mapped to something else
        self.failUnlessEqual(s1.revision, "None")
        self.failUnlessEqual(len(s1.changes), 1)
        self.failUnlessEqual(s1.patch, None)

        s2 = sources[1]
        self.failUnlessEqual(s2.branch, "branch1")
        # TODO: Fixme when change.revision = None is mapped to something else
        self.failUnlessEqual(s2.revision, "None")
        self.failUnlessEqual(len(s2.changes), 3)
        self.failUnlessEqual(s2.patch, None)

        s3 = sources[2]
        self.failUnlessEqual(s3.branch, "branch2")
        # TODO: Fixme when change.revision = None is mapped to something else
        self.failUnlessEqual(s3.revision, "None")
        self.failUnlessEqual(len(s3.changes), 1)
        self.failUnlessEqual(s3.patch, None)

    def testAnyBranch2(self):
        # like testAnyBranch but without fileIsImportant
        self.basedir = 'scheduler/Scheduling/AnyBranch2'
        self.create_master()
        s = scheduler.AnyBranchScheduler("b1", 2, ["a","b"])

        d = self.setSchedulers(s)

        def _addChange(ign, c):
            self.master.change_svc.addChange(c)

        c1 = Change("alice", ["important", "not important"], "some changes",
                    branch="branch1")
        d.addCallback(_addChange, c1)
        c2 = Change("bob", ["not important", "boring"], "some more changes",
                    branch="branch1")
        d.addCallback(_addChange, c2)
        c3 = Change("carol", ["important", "dull"], "even more changes",
                    branch="branch1")
        d.addCallback(_addChange, c3)

        c4 = Change("carol", ["important"], "other branch", branch="branch2")
        d.addCallback(_addChange, c4)

        d.addCallback(lambda ign: self.master.scheduler_manager.when_quiet())
        d.addCallback(self._testAnyBranch2_1)
        return d
    def _testAnyBranch2_1(self, res):
        bsids = self.master.db.get_active_buildset_ids()
        self.failUnlessEqual(len(bsids), 2)

        sources = []
        for bsid in bsids:
            (external_idstring, reason, ssid, complete, results) = self.master.db.get_buildset_info(bsid)
            s = self.master.db.getSourceStampNumberedNow(ssid)
            sources.append(s)
        sources.sort(lambda a,b: cmp(a.branch, b.branch))

        s1 = sources[0]
        self.failUnlessEqual(s1.branch, "branch1")
        # TODO: Fixme when change.revision = None is mapped to something else
        self.failUnlessEqual(s1.revision, "None")
        self.failUnlessEqual(len(s1.changes), 3)
        self.failUnlessEqual(s1.patch, None)

        s2 = sources[1]
        self.failUnlessEqual(s2.branch, "branch2")
        # TODO: Fixme when change.revision = None is mapped to something else
        self.failUnlessEqual(s2.revision, "None")
        self.failUnlessEqual(len(s2.changes), 1)
        self.failUnlessEqual(s2.patch, None)


    def createMaildir(self, jobdir):
        os.mkdir(jobdir)
        os.mkdir(os.path.join(jobdir, "new"))
        os.mkdir(os.path.join(jobdir, "cur"))
        os.mkdir(os.path.join(jobdir, "tmp"))

    jobcounter = 1
    def pushJob(self, jobdir, job):
        while 1:
            filename = "job_%d" % self.jobcounter
            self.jobcounter += 1
            if os.path.exists(os.path.join(jobdir, "new", filename)):
                continue
            if os.path.exists(os.path.join(jobdir, "tmp", filename)):
                continue
            if os.path.exists(os.path.join(jobdir, "cur", filename)):
                continue
            break
        f = open(os.path.join(jobdir, "tmp", filename), "w")
        f.write(job)
        f.close()
        os.rename(os.path.join(jobdir, "tmp", filename),
                  os.path.join(jobdir, "new", filename))

    def testTryJobdir(self):
        self.basedir = "scheduler/Scheduling/TryJobdir"
        self.create_master()
        db = self.master.db
        jobdir = "jobdir1"
        jobdir_abs = os.path.join(self.master.basedir, jobdir)
        self.createMaildir(jobdir_abs)
        s = scheduler.Try_Jobdir("try1", ["a", "b"], jobdir)
        s.watcher.pollinterval = 1.0 # set this before startService
        d = self.setSchedulers(s)
        def _then(ign):
            job1 = tryclient.createJobfile("buildsetID",
                                           "branch1", "123", 1, "diff",
                                           ["a", "b"])
            self.pushJob(jobdir_abs, job1)
        d.addCallback(_then)

        def _poll():
            return bool(db.get_active_buildset_ids())
        d.addCallback(lambda ign: self.poll(_poll, 0.1))
        def _check(ign):
            bsids = db.get_active_buildset_ids()
            (external_idstring, reason, ssid, complete, results) = \
                                db.get_buildset_info(bsids[0])
            reqs = db.get_buildrequestids_for_buildset(bsids[0])
            self.failUnlessEqual(sorted(reqs.keys()), ["a","b"])
            s = db.getSourceStampNumberedNow(ssid)
            self.failUnlessEqual(s.branch, "branch1")
            self.failUnlessEqual(s.revision, "123")
            self.failUnlessEqual(s.patch, (1, "diff"))
        d.addCallback(_check)
        return d


    def testTryUserpass(self):
        self.basedir = "scheduler/Scheduling/TryUserpass"
        self.create_master()
        db = self.master.db
        up = [("alice","pw1"), ("bob","pw2")]
        s = scheduler.Try_Userpass("try2", ["a", "b"], 0, userpass=up)
        d = self.setSchedulers(s)
        def _then(ign):
            port = s.getPort()
            config = {'connect': 'pb',
                      'username': 'alice',
                      'passwd': 'pw1',
                      'master': "localhost:%d" % port,
                      'builders': ["a", "b"],
                      }
            self.tryclient = t = tryclient.Try(config)
            ss = sourcestamp.SourceStamp("branch1", "123", (1, "diff"))
            t.sourcestamp = ss
            return t.deliverJob()
        d.addCallback(_then)
        def _job_delivered(ign):
            # at this point, the Try object should have a RemoteReference to
            # the status object.
            self.failUnless(self.tryclient.buildsetStatus)
        d.addCallback(_job_delivered)
        def _poll():
            return bool(db.get_active_buildset_ids())
        d.addCallback(lambda ign: self.poll(_poll, 0.1))
        def _check(ign):
            bsids = db.get_active_buildset_ids()
            (external_idstring, reason, ssid, complete, results) = \
                                db.get_buildset_info(bsids[0])
            reqs = db.get_buildrequestids_for_buildset(bsids[0])
            self.failUnlessEqual(sorted(reqs.keys()), ["a","b"])
            s = db.getSourceStampNumberedNow(ssid)
            self.failUnlessEqual(s.branch, "branch1")
            self.failUnlessEqual(s.revision, "123")
            self.failUnlessEqual(s.patch, (1, "diff"))
            self.tryclient.cleanup()
        d.addCallback(_check)
        return d

    def testCategory(self):
        self.basedir = "scheduler/Scheduling/Category"
        self.create_master()
        db = self.master.db

        # The basic Scheduler automatically removes classified changes from
        # the DB and fires a build. We use a subclass which leaves them in
        # the DB, so we can look at them later.

        s1 = NotScheduler("b1", "branch1", 2, ["a","b"],
                          categories=["categoryA", "both"])
        s2 = NotScheduler("b2", "branch1", 2, ["a","b"],
                          categories=["categoryB", "both"])
        s3 = NotScheduler("b3", "branch1", 2, ["a","b"])
        d = self.setSchedulers(s1, s2, s3)

        c0 = Change("carol", ["important"], "branch1", branch="branch1",
                    category="categoryA", revision="c0")
        c1 = Change("carol", ["important"], "branch1", branch="branch1",
                    category="categoryB", revision="c1")
        c2 = Change("carol", ["important"], "branch1", branch="branch1",
                    revision="c2")
        c3 = Change("carol", ["important"], "branch1", branch="branch1",
                    category="both", revision="c3")

        def _then(ign):
            self.control.addChange(c0)
            self.control.addChange(c1)
            self.control.addChange(c2)
            self.control.addChange(c3)
            # those all trigger the SchedulerManager Loop, which will run
            # classify_changes(). We must now wait for the loop to finish.
            return self.wait_until_idle()
        d.addCallback(_then)

        def _check(t):
            def _get_revs(changes):
                return sorted([c.revision for c in changes])
            (i,u) = db.scheduler_get_classified_changes(s1.schedulerid, t)
            self.failUnlessEqual(_get_revs(i), ["c0", "c3"])
            (i,u) = db.scheduler_get_classified_changes(s2.schedulerid, t)
            self.failUnlessEqual(_get_revs(i), ["c1", "c3"])
            (i,u) = db.scheduler_get_classified_changes(s3.schedulerid, t)
            self.failUnlessEqual(_get_revs(i), ["c0", "c1", "c2", "c3"])
        d.addCallback(lambda ign: db.runInteraction(_check))
        return d

class NotScheduler(scheduler.Scheduler):
    def decide_and_remove_changes(self, t, important, unimportant):
        # leave the classified changes in the DB
        return None
