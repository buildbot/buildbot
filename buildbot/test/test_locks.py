# -*- test-case-name: buildbot.test.test_locks -*-

from twisted.trial import unittest
from twisted.internet import defer

from buildbot import interfaces
from buildbot.process import step
from buildbot.sourcestamp import SourceStamp
from buildbot.process.base import BuildRequest
from buildbot.test.runutils import RunMixin
from buildbot.twcompat import maybeWait

class LockStep(step.Dummy):
    def start(self):
        number = self.build.requests[0].number
        self.build.requests[0].events.append(("start", number))
        step.Dummy.start(self)
    def done(self):
        number = self.build.requests[0].number
        self.build.requests[0].events.append(("done", number))
        step.Dummy.done(self)

config_1 = """
from buildbot import locks
from buildbot.process import step, factory
s = factory.s
from buildbot.test.test_locks import LockStep

BuildmasterConfig = c = {}
c['bots'] = [('bot1', 'sekrit'), ('bot2', 'sekrit')]
c['sources'] = []
c['schedulers'] = []
c['slavePortnum'] = 0

first_lock = locks.SlaveLock('first')
second_lock = locks.MasterLock('second')
f1 = factory.BuildFactory([s(LockStep, timeout=2, locks=[first_lock])])
f2 = factory.BuildFactory([s(LockStep, timeout=3, locks=[second_lock])])
f3 = factory.BuildFactory([s(LockStep, timeout=2, locks=[])])

b1a = {'name': 'full1a', 'slavename': 'bot1', 'builddir': '1a', 'factory': f1}
b1b = {'name': 'full1b', 'slavename': 'bot1', 'builddir': '1b', 'factory': f1}
b1c = {'name': 'full1c', 'slavename': 'bot1', 'builddir': '1c', 'factory': f3,
       'locks': [first_lock, second_lock]}
b1d = {'name': 'full1d', 'slavename': 'bot1', 'builddir': '1d', 'factory': f2}
b2a = {'name': 'full2a', 'slavename': 'bot2', 'builddir': '2a', 'factory': f1}
b2b = {'name': 'full2b', 'slavename': 'bot2', 'builddir': '2b', 'factory': f3,
       'locks': [second_lock]}
c['builders'] = [b1a, b1b, b1c, b1d, b2a, b2b]
"""

config_1a = config_1 + \
"""
b1b = {'name': 'full1b', 'slavename': 'bot1', 'builddir': '1B', 'factory': f1}
c['builders'] = [b1a, b1b, b1c, b1d, b2a, b2b]
"""


class Locks(RunMixin, unittest.TestCase):
    def setUp(self):
        RunMixin.setUp(self)
        self.req1 = req1 = BuildRequest("forced build", SourceStamp())
        req1.number = 1
        self.req2 = req2 = BuildRequest("forced build", SourceStamp())
        req2.number = 2
        self.req3 = req3 = BuildRequest("forced build", SourceStamp())
        req3.number = 3
        req1.events = req2.events = req3.events = self.events = []
        d = self.master.loadConfig(config_1)
        d.addCallback(lambda res: self.master.startService())
        d.addCallback(lambda res: self.connectSlaves(["bot1", "bot2"],
                                                     ["full1a", "full1b",
                                                      "full1c", "full1d",
                                                      "full2a", "full2b"]))
        return maybeWait(d)

    def testLock1(self):
        self.control.getBuilder("full1a").requestBuild(self.req1)
        self.control.getBuilder("full1b").requestBuild(self.req2)
        d = defer.DeferredList([self.req1.waitUntilFinished(),
                                self.req2.waitUntilFinished()])
        d.addCallback(self._testLock1_1)
        return maybeWait(d)

    def _testLock1_1(self, res):
        # full1a should complete its step before full1b starts it
        self.failUnlessEqual(self.events,
                             [("start", 1), ("done", 1),
                              ("start", 2), ("done", 2)])

    def testLock1a(self):
        # just like testLock1, but we reload the config file first, with a
        # change that causes full1b to be changed. This tickles a design bug
        # in which full1a and full1b wind up with distinct Lock instances.
        d = self.master.loadConfig(config_1a)
        d.addCallback(self._testLock1a_1)
        return maybeWait(d)
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
        return maybeWait(d)

    def _testLock2_1(self, res):
        # full2a should start its step before full1a finishes it. They run on
        # different slaves, however, so they might start in either order.
        self.failUnless(self.events[:2] == [("start", 1), ("start", 2)] or
                        self.events[:2] == [("start", 2), ("start", 1)])

    def testLock3(self):
        # two builds run on separate slaves with master-scoped locks should
        # not overlap
        self.control.getBuilder("full1c").requestBuild(self.req1)
        self.control.getBuilder("full2b").requestBuild(self.req2)
        d = defer.DeferredList([self.req1.waitUntilFinished(),
                                self.req2.waitUntilFinished()])
        d.addCallback(self._testLock3_1)
        return maybeWait(d)

    def _testLock3_1(self, res):
        # full2b should not start until after full1c finishes. The builds run
        # on different slaves, so we can't really predict which will start
        # first. The important thing is that they don't overlap.
        self.failUnless(self.events == [("start", 1), ("done", 1),
                                        ("start", 2), ("done", 2)]
                        or self.events == [("start", 2), ("done", 2),
                                           ("start", 1), ("done", 1)]
                        )

    def testLock4(self):
        self.control.getBuilder("full1a").requestBuild(self.req1)
        self.control.getBuilder("full1c").requestBuild(self.req2)
        self.control.getBuilder("full1d").requestBuild(self.req3)
        d = defer.DeferredList([self.req1.waitUntilFinished(),
                                self.req2.waitUntilFinished(),
                                self.req3.waitUntilFinished()])
        d.addCallback(self._testLock4_1)
        return maybeWait(d)

    def _testLock4_1(self, res):
        # full1a starts, then full1d starts (because they do not interfere).
        # Once both are done, full1c can run.
        self.failUnlessEqual(self.events,
                             [("start", 1), ("start", 3),
                              ("done", 1), ("done", 3),
                              ("start", 2), ("done", 2)])

