# -*- test-case-name: buildbot.test.test_locks -*-

import random

from twisted.trial import unittest
from twisted.internet import defer, reactor

from buildbot import master
from buildbot.steps import dummy
from buildbot.sourcestamp import SourceStamp
from buildbot.process.base import BuildRequest
from buildbot.test.runutils import RunMixin
from buildbot import locks

def claimHarder(lock, owner, la):
    """Return a Deferred that will fire when the lock is claimed. Keep trying
    until we succeed."""
    if lock.isAvailable(la):
        #print "claimHarder(%s): claiming" % owner
        lock.claim(owner, la)
        return defer.succeed(lock)
    #print "claimHarder(%s): waiting" % owner
    d = lock.waitUntilMaybeAvailable(owner, la)
    d.addCallback(claimHarder, owner, la)
    return d

def hold(lock, owner, la, mode="now"):
    if mode == "now":
        lock.release(owner, la)
    elif mode == "very soon":
        reactor.callLater(0, lock.release, owner, la)
    elif mode == "soon":
        reactor.callLater(0.1, lock.release, owner, la)

class Unit(unittest.TestCase):
    def testNowCounting(self):
        lid = locks.MasterLock('dummy')
        la = locks.LockAccess(lid, 'counting')
        return self._testNow(la)

    def testNowExclusive(self):
        lid = locks.MasterLock('dummy')
        la = locks.LockAccess(lid, 'exclusive')
        return self._testNow(la)

    def _testNow(self, la):
        l = locks.BaseLock("name")
        self.failUnless(l.isAvailable(la))
        l.claim("owner1", la)
        self.failIf(l.isAvailable(la))
        l.release("owner1", la)
        self.failUnless(l.isAvailable(la))

    def testNowMixed1(self):
        """ Test exclusive is not possible when a counting has the lock """
        lid = locks.MasterLock('dummy')
        lac = locks.LockAccess(lid, 'counting')
        lae = locks.LockAccess(lid, 'exclusive')
        l = locks.BaseLock("name", maxCount=2)
        self.failUnless(l.isAvailable(lac))
        l.claim("count-owner", lac)
        self.failIf(l.isAvailable(lae))
        l.release("count-owner", lac)
        self.failUnless(l.isAvailable(lac))

    def testNowMixed2(self):
        """ Test counting is not possible when an exclsuive has the lock """
        lid = locks.MasterLock('dummy')
        lac = locks.LockAccess(lid, 'counting')
        lae = locks.LockAccess(lid, 'exclusive')
        l = locks.BaseLock("name", maxCount=2)
        self.failUnless(l.isAvailable(lae))
        l.claim("count-owner", lae)
        self.failIf(l.isAvailable(lac))
        l.release("count-owner", lae)
        self.failUnless(l.isAvailable(lae))

    def testLaterCounting(self):
        lid = locks.MasterLock('dummy')
        la = locks.LockAccess(lid, 'counting')
        return self._testLater(la)

    def testLaterExclusive(self):
        lid = locks.MasterLock('dummy')
        la = locks.LockAccess(lid, 'exclusive')
        return self._testLater(la)

    def _testLater(self, la):
        lock = locks.BaseLock("name")
        d = claimHarder(lock, "owner1", la)
        d.addCallback(lambda lock: lock.release("owner1", la))
        return d

    def testCompetitionCounting(self):
        lid = locks.MasterLock('dummy')
        la = locks.LockAccess(lid, 'counting')
        return self._testCompetition(la)

    def testCompetitionExclusive(self):
        lid = locks.MasterLock('dummy')
        la = locks.LockAccess(lid, 'exclusive')
        return self._testCompetition(la)

    def _testCompetition(self, la):
        lock = locks.BaseLock("name")
        d = claimHarder(lock, "owner1", la)
        d.addCallback(self._claim1, la)
        return d
    def _claim1(self, lock, la):
        # we should have claimed it by now
        self.failIf(lock.isAvailable(la))
        # now set up two competing owners. We don't know which will get the
        # lock first.
        d2 = claimHarder(lock, "owner2", la)
        d2.addCallback(hold, "owner2", la, "now")
        d3 = claimHarder(lock, "owner3", la)
        d3.addCallback(hold, "owner3", la, "soon")
        dl = defer.DeferredList([d2,d3])
        dl.addCallback(self._cleanup, lock, la)
        # and release the lock in a moment
        reactor.callLater(0.1, lock.release, "owner1", la)
        return dl

    def _cleanup(self, res, lock, la):
        d = claimHarder(lock, "cleanup", la)
        d.addCallback(lambda lock: lock.release("cleanup", la))
        return d

    def testRandomCounting(self):
        lid = locks.MasterLock('dummy')
        la = locks.LockAccess(lid, 'counting')
        return self._testRandom(la)

    def testRandomExclusive(self):
        lid = locks.MasterLock('dummy')
        la = locks.LockAccess(lid, 'exclusive')
        return self._testRandom(la)

    def _testRandom(self, la):
        lock = locks.BaseLock("name")
        dl = []
        for i in range(100):
            owner = "owner%d" % i
            mode = random.choice(["now", "very soon", "soon"])
            d = claimHarder(lock, owner, la)
            d.addCallback(hold, owner, la, mode)
            dl.append(d)
        d = defer.DeferredList(dl)
        d.addCallback(self._cleanup, lock, la)
        return d

class Multi(unittest.TestCase):
    def testNowCounting(self):
        lid = locks.MasterLock('dummy')
        la = locks.LockAccess(lid, 'counting')
        lock = locks.BaseLock("name", 2)
        self.failUnless(lock.isAvailable(la))
        lock.claim("owner1", la)
        self.failUnless(lock.isAvailable(la))
        lock.claim("owner2", la)
        self.failIf(lock.isAvailable(la))
        lock.release("owner1", la)
        self.failUnless(lock.isAvailable(la))
        lock.release("owner2", la)
        self.failUnless(lock.isAvailable(la))

    def testLaterCounting(self):
        lid = locks.MasterLock('dummy')
        la = locks.LockAccess(lid, 'counting')
        lock = locks.BaseLock("name", 2)
        lock.claim("owner1", la)
        lock.claim("owner2", la)
        d = claimHarder(lock, "owner3", la)
        d.addCallback(lambda lock: lock.release("owner3", la))
        lock.release("owner2", la)
        lock.release("owner1", la)
        return d

    def _cleanup(self, res, lock, count, la):
        dl = []
        for i in range(count):
            d = claimHarder(lock, "cleanup%d" % i, la)
            dl.append(d)
        d2 = defer.DeferredList(dl)
        # once all locks are claimed, we know that any previous owners have
        # been flushed out
        def _release(res):
            for i in range(count):
                lock.release("cleanup%d" % i, la)
        d2.addCallback(_release)
        return d2

    def testRandomCounting(self):
        lid = locks.MasterLock('dummy')
        la = locks.LockAccess(lid, 'counting')
        COUNT = 5
        lock = locks.BaseLock("name", COUNT)
        dl = []
        for i in range(100):
            owner = "owner%d" % i
            mode = random.choice(["now", "very soon", "soon"])
            d = claimHarder(lock, owner, la)
            def _check(lock):
                self.failIf(len(lock.owners) > COUNT)
                return lock
            d.addCallback(_check)
            d.addCallback(hold, owner, la, mode)
            dl.append(d)
        d = defer.DeferredList(dl)
        d.addCallback(self._cleanup, lock, COUNT, la)
        return d

class Dummy:
    pass

def slave(slavename):
    slavebuilder = Dummy()
    slavebuilder.slave = Dummy()
    slavebuilder.slave.slavename = slavename
    return slavebuilder

class MakeRealLock(unittest.TestCase):

    def make(self, lockid):
        return lockid.lockClass(lockid)

    def testMaster(self):
        mid1 = locks.MasterLock("name1")
        mid2 = locks.MasterLock("name1")
        mid3 = locks.MasterLock("name3")
        mid4 = locks.MasterLock("name1", 3)
        self.failUnlessEqual(mid1, mid2)
        self.failIfEqual(mid1, mid3)
        # they should all be hashable
        d = {mid1: 1, mid2: 2, mid3: 3, mid4: 4}

        l1 = self.make(mid1)
        self.failUnlessEqual(l1.name, "name1")
        self.failUnlessEqual(l1.maxCount, 1)
        self.failUnlessIdentical(l1.getLock(slave("slave1")), l1)
        l4 = self.make(mid4)
        self.failUnlessEqual(l4.name, "name1")
        self.failUnlessEqual(l4.maxCount, 3)
        self.failUnlessIdentical(l4.getLock(slave("slave1")), l4)

    def testSlave(self):
        sid1 = locks.SlaveLock("name1")
        sid2 = locks.SlaveLock("name1")
        sid3 = locks.SlaveLock("name3")
        sid4 = locks.SlaveLock("name1", maxCount=3)
        mcfs = {"bigslave": 4, "smallslave": 1}
        sid5 = locks.SlaveLock("name1", maxCount=3, maxCountForSlave=mcfs)
        mcfs2 = {"bigslave": 4, "smallslave": 1}
        sid5a = locks.SlaveLock("name1", maxCount=3, maxCountForSlave=mcfs2)
        mcfs3 = {"bigslave": 1, "smallslave": 99}
        sid5b = locks.SlaveLock("name1", maxCount=3, maxCountForSlave=mcfs3)
        self.failUnlessEqual(sid1, sid2)
        self.failIfEqual(sid1, sid3)
        self.failIfEqual(sid1, sid4)
        self.failIfEqual(sid1, sid5)
        self.failUnlessEqual(sid5, sid5a)
        self.failIfEqual(sid5a, sid5b)
        # they should all be hashable
        d = {sid1: 1, sid2: 2, sid3: 3, sid4: 4, sid5: 5, sid5a: 6, sid5b: 7}

        l1 = self.make(sid1)
        self.failUnlessEqual(l1.name, "name1")
        self.failUnlessEqual(l1.maxCount, 1)
        l1s1 = l1.getLock(slave("slave1"))
        self.failIfIdentical(l1s1, l1)

        l4 = self.make(sid4)
        self.failUnlessEqual(l4.maxCount, 3)
        l4s1 = l4.getLock(slave("slave1"))
        self.failUnlessEqual(l4s1.maxCount, 3)

        l5 = self.make(sid5)
        l5s1 = l5.getLock(slave("bigslave"))
        l5s2 = l5.getLock(slave("smallslave"))
        l5s3 = l5.getLock(slave("unnamedslave"))
        self.failUnlessEqual(l5s1.maxCount, 4)
        self.failUnlessEqual(l5s2.maxCount, 1)
        self.failUnlessEqual(l5s3.maxCount, 3)

class GetLock(unittest.TestCase):
    def testGet(self):
        # the master.cfg file contains "lock ids", which are instances of
        # MasterLock and SlaveLock but which are not actually Locks per se.
        # When the build starts, these markers are turned into RealMasterLock
        # and RealSlaveLock instances. This insures that any builds running
        # on slaves that were unaffected by the config change are still
        # referring to the same Lock instance as new builds by builders that
        # *were* affected by the change. There have been bugs in the past in
        # which this didn't happen, and the Locks were bypassed because half
        # the builders were using one incarnation of the lock while the other
        # half were using a separate (but equal) incarnation.
        #
        # Changing the lock id in any way should cause it to be replaced in
        # the BotMaster. This will result in a couple of funky artifacts:
        # builds in progress might pay attention to a different lock, so we
        # might bypass the locking for the duration of a couple builds.
        # There's also the problem of old Locks lingering around in
        # BotMaster.locks, but they're small and shouldn't really cause a
        # problem.

        b = master.BotMaster()
        l1 = locks.MasterLock("one")
        l1a = locks.MasterLock("one")
        l2 = locks.MasterLock("one", maxCount=4)

        rl1 = b.getLockByID(l1)
        rl2 = b.getLockByID(l1a)
        self.failUnlessIdentical(rl1, rl2)
        rl3 = b.getLockByID(l2)
        self.failIfIdentical(rl1, rl3)

        s1 = locks.SlaveLock("one")
        s1a = locks.SlaveLock("one")
        s2 = locks.SlaveLock("one", maxCount=4)
        s3 = locks.SlaveLock("one", maxCount=4,
                             maxCountForSlave={"a":1, "b":2})
        s3a = locks.SlaveLock("one", maxCount=4,
                              maxCountForSlave={"a":1, "b":2})
        s4 = locks.SlaveLock("one", maxCount=4,
                             maxCountForSlave={"a":4, "b":4})

        rl1 = b.getLockByID(s1)
        rl2 = b.getLockByID(s1a)
        self.failUnlessIdentical(rl1, rl2)
        rl3 = b.getLockByID(s2)
        self.failIfIdentical(rl1, rl3)
        rl4 = b.getLockByID(s3)
        self.failIfIdentical(rl1, rl4)
        self.failIfIdentical(rl3, rl4)
        rl5 = b.getLockByID(s3a)
        self.failUnlessIdentical(rl4, rl5)
        rl6 = b.getLockByID(s4)
        self.failIfIdentical(rl5, rl6)



class LockStep(dummy.Dummy):
    def start(self):
        number = self.build.requests[0].number
        self.build.requests[0].events.append(("start", number))
        dummy.Dummy.start(self)
    def done(self):
        number = self.build.requests[0].number
        self.build.requests[0].events.append(("done", number))
        dummy.Dummy.done(self)

config_1 = """
from buildbot import locks
from buildbot.process import factory
from buildbot.buildslave import BuildSlave
from buildbot.config import BuilderConfig
s = factory.s
from buildbot.test.test_locks import LockStep

BuildmasterConfig = c = {}
c['slaves'] = [BuildSlave('bot1', 'sekrit'), BuildSlave('bot2', 'sekrit')]
c['schedulers'] = []
c['slavePortnum'] = 0

first_lock = locks.SlaveLock('first')
second_lock = locks.MasterLock('second')
f1 = factory.BuildFactory([s(LockStep, timeout=2, locks=[first_lock])])
f2 = factory.BuildFactory([s(LockStep, timeout=3, locks=[second_lock])])
f3 = factory.BuildFactory([s(LockStep, timeout=2, locks=[])])

b1a = BuilderConfig(name='full1a', slavename='bot1', factory=f1)
b1b = BuilderConfig(name='full1b', slavename='bot1', factory=f1)
b1c = BuilderConfig(name='full1c', slavename='bot1', factory=f3,
                    locks=[first_lock, second_lock])
b1d = BuilderConfig(name='full1d', slavename='bot1', factory=f2)

b2a = BuilderConfig(name='full2a', slavename='bot2', factory=f1)
b2b = BuilderConfig(name='full2b', slavename='bot2', factory=f3,
                    locks=[second_lock])
c['builders'] = [b1a, b1b, b1c, b1d, b2a, b2b]
"""

config_1a = config_1 + \
"""
b1b = BuilderConfig(name='full1b', builddir='1B', slavename='bot1', factory=f1)
c['builders'] = [b1a, b1b, b1c, b1d, b2a, b2b]
"""


class Locks(RunMixin, unittest.TestCase):
    def setUp(self):
        N = 'test_builder'
        RunMixin.setUp(self)
        self.req1 = req1 = BuildRequest("forced build", SourceStamp(), N)
        req1.number = 1
        self.req2 = req2 = BuildRequest("forced build", SourceStamp(), N)
        req2.number = 2
        self.req3 = req3 = BuildRequest("forced build", SourceStamp(), N)
        req3.number = 3
        req1.events = req2.events = req3.events = self.events = []
        d = self.master.loadConfig(config_1)
        d.addCallback(lambda res: self.master.startService())
        d.addCallback(lambda res: self.connectSlave(
                    ["full1a", "full1b", "full1c", "full1d"],
                    "bot1"))
        d.addCallback(lambda res: self.connectSlave(["full2a", "full2b"], "bot2"))
        return d

    def testLock1(self):
        self.control.getBuilder("full1a").requestBuild(self.req1)
        self.control.getBuilder("full1b").requestBuild(self.req2)
        d = defer.DeferredList([self.req1.waitUntilFinished(),
                                self.req2.waitUntilFinished()])
        d.addCallback(self._testLock1_1)
        return d

    def _testLock1_1(self, res):
        # full1a should complete its step before full1b starts it
        self.failUnlessEqual(self.events,
                             [("start", 1), ("done", 1),
                              ("start", 2), ("done", 2)])

    def dont_testLock1a(self): ## disabled -- test itself is buggy
        # just like testLock1, but we reload the config file first, with a
        # change that causes full1b to be changed. This tickles a design bug
        # in which full1a and full1b wind up with distinct Lock instances.
        d = self.master.loadConfig(config_1a)
        d.addCallback(self._testLock1a_1)
        return d
    def _testLock1a_1(self, res):
        self.control.getBuilder("full1a").requestBuild(self.req1)
        self.control.getBuilder("full1b").requestBuild(self.req2)
        d = defer.DeferredList([self.req1.waitUntilFinished(),
                                self.req2.waitUntilFinished()])
        d.addCallback(self._testLock1a_2)
        return d

    def _testLock1a_2(self, res):
        # full1a should complete its step before full1b starts it
        self.failUnlessEqual(self.events,
                             [("start", 1), ("done", 1),
                              ("start", 2), ("done", 2)])

    def testLock2(self):
        # two builds run on separate slaves with slave-scoped locks should
        # not interfere
        self.control.getBuilder("full1a").requestBuild(self.req1)
        self.control.getBuilder("full2a").requestBuild(self.req2)
        d = defer.DeferredList([self.req1.waitUntilFinished(),
                                self.req2.waitUntilFinished()])
        d.addCallback(self._testLock2_1)
        return d

    def _testLock2_1(self, res):
        # full2a should start its step before full1a finishes it. They run on
        # different slaves, however, so they might start in either order.
        self.failUnless(self.events[:2] == [("start", 1), ("start", 2)] or
                        self.events[:2] == [("start", 2), ("start", 1)])

    def dont_testLock3(self): ## disabled -- test fails sporadically
        # two builds run on separate slaves with master-scoped locks should
        # not overlap
        self.control.getBuilder("full1c").requestBuild(self.req1)
        self.control.getBuilder("full2b").requestBuild(self.req2)
        d = defer.DeferredList([self.req1.waitUntilFinished(),
                                self.req2.waitUntilFinished()])
        d.addCallback(self._testLock3_1)
        return d

    def _testLock3_1(self, res):
        # full2b should not start until after full1c finishes. The builds run
        # on different slaves, so we can't really predict which will start
        # first. The important thing is that they don't overlap.
        self.failUnless(self.events == [("start", 1), ("done", 1),
                                        ("start", 2), ("done", 2)]
                        or self.events == [("start", 2), ("done", 2),
                                           ("start", 1), ("done", 1)]
                        )

    # This test has been disabled due to flakeyness/intermittentness
#    def testLock4(self):
#        self.control.getBuilder("full1a").requestBuild(self.req1)
#        self.control.getBuilder("full1c").requestBuild(self.req2)
#        self.control.getBuilder("full1d").requestBuild(self.req3)
#        d = defer.DeferredList([self.req1.waitUntilFinished(),
#                                self.req2.waitUntilFinished(),
#                                self.req3.waitUntilFinished()])
#        d.addCallback(self._testLock4_1)
#        return d
#
#    def _testLock4_1(self, res):
#        # full1a starts, then full1d starts (because they do not interfere).
#        # Once both are done, full1c can run.
#        self.failUnlessEqual(self.events,
#                             [("start", 1), ("start", 3),
#                              ("done", 1), ("done", 3),
#                              ("start", 2), ("done", 2)])

class BuilderLocks(RunMixin, unittest.TestCase):
    config = """\
from buildbot import locks
from buildbot.process import factory
from buildbot.buildslave import BuildSlave
from buildbot.config import BuilderConfig
s = factory.s
from buildbot.test.test_locks import LockStep

BuildmasterConfig = c = {}
c['slaves'] = [BuildSlave('bot1', 'sekrit'), BuildSlave('bot2', 'sekrit')]
c['schedulers'] = []
c['slavePortnum'] = 0

master_lock = locks.MasterLock('master', maxCount=2)
f_excl = factory.BuildFactory([s(LockStep, timeout=0,
                               locks=[master_lock.access("exclusive")])])
f_count = factory.BuildFactory([s(LockStep, timeout=0,
                                locks=[master_lock])])

slaves = ['bot1', 'bot2']
c['builders'] = [
  BuilderConfig(name='excl_A', slavenames=slaves, factory=f_excl),
  BuilderConfig(name='excl_B', slavenames=slaves, factory=f_excl),
  BuilderConfig(name='count_A', slavenames=slaves, factory=f_count),
  BuilderConfig(name='count_B', slavenames=slaves, factory=f_count),
]
"""

    def setUp(self):
        N = 'test_builder'
        RunMixin.setUp(self)
        self.reqs = [BuildRequest("forced build", SourceStamp(), N)
                     for i in range(4)]
        self.events = []
        for i in range(4):
            self.reqs[i].number = i
            self.reqs[i].events = self.events
        d = self.master.loadConfig(self.config)
        d.addCallback(lambda res: self.master.startService())
        d.addCallback(lambda res: self.connectSlave(
                    ["excl_A", "excl_B", "count_A", "count_B"], "bot1"))
        d.addCallback(lambda res: self.connectSlave(
                    ["excl_A", "excl_B", "count_A", "count_B"], "bot2"))
        return d

    def testOrder(self):
        self.control.getBuilder("excl_A").requestBuild(self.reqs[0])
        self.control.getBuilder("excl_B").requestBuild(self.reqs[1])
        self.control.getBuilder("count_A").requestBuild(self.reqs[2])
        self.control.getBuilder("count_B").requestBuild(self.reqs[3])
        d = defer.DeferredList([r.waitUntilFinished()
                                for r in self.reqs])
        d.addCallback(self._testOrder)
        return d

    def _testOrder(self, res):
        # excl_A and excl_B cannot overlap with any other steps.
        self.assert_(("start", 0) in self.events)
        self.assert_(("done", 0) in self.events)
        self.assert_(self.events.index(("start", 0)) + 1 ==
                     self.events.index(("done", 0)))

        self.assert_(("start", 1) in self.events)
        self.assert_(("done", 1) in self.events)
        self.assert_(self.events.index(("start", 1)) + 1 ==
                     self.events.index(("done", 1)))

        # FIXME: We really want to test that count_A and count_B were
        # overlapped, but don't have a reliable way to do this.
