from twisted.trial import unittest
from twisted.internet import reactor, defer

from buildbot.test.runutils import RunMixin, TestFlagMixin, rmtree
from buildbot.changes import changes
from buildbot.sourcestamp import SourceStamp
from buildbot.process.base import BuildRequest

nextslave_config = """
from buildbot.process import factory
from buildbot.steps import dummy
from buildbot.buildslave import BuildSlave
from buildbot.scheduler import Scheduler
from buildbot.config import BuilderConfig

f1 = factory.BuildFactory([dummy.Dummy(timeout=0)])

def nextSlave(builder, slaves):
    for s in slaves:
        if s.slave.slavename == 'bot1':
            return s

BuildmasterConfig = c = {}
c['slaves'] = [BuildSlave('bot1', 'sekrit'), BuildSlave('bot2', 'sekrit')]
c['schedulers'] = [Scheduler('dummy', None, 0, ['dummy'])]
c['builders'] = [
    BuilderConfig(name='dummy', slavenames=['bot1', 'bot2'],
                  factory=f1, nextSlave=nextSlave),
]
c['slavePortnum'] = 0
c['mergeRequests'] = lambda builder, req1, req2: False
"""
class NextSlave(RunMixin, unittest.TestCase):
    def rmtree(self, d):
        rmtree(d)

    def testNextSlave(self):
        d = self.master.loadConfig(nextslave_config)
        self.master.readConfig = True
        d.addCallback(lambda res: self.master.startService())
        d.addCallback(lambda res: self.connectSlave(slavename='bot1'))
        d.addCallback(lambda res: self.connectSlave(slavename='bot2'))

        def check(res):
            builder = self.status.getBuilder("dummy")
            self.failUnlessEqual(len(builder.slavenames), 2)
            for i in range(5):
                build = builder.getBuild(i)
                self.failUnlessEqual(build.slavename, 'bot1')

        def _send(res):
            # send some build requests
            reqs = []
            ss = SourceStamp()
            for i in range(5):
                req = BuildRequest(str(i), ss, "dummy")
                self.master.botmaster.builders['dummy'].submitBuildRequest(req)
                reqs.append(req.waitUntilFinished())

            dl = defer.DeferredList(reqs)
            dl.addCallback(check)
            return dl

        d.addCallback(_send)

        return d

# Test nextBuild
nextbuild_config = """
from buildbot.process import factory
from buildbot.steps import dummy
from buildbot.buildslave import BuildSlave
from buildbot.scheduler import Scheduler
from buildbot.config import BuilderConfig

f1 = factory.BuildFactory([dummy.Dummy(timeout=0)])

def nextBuild(builder, requests):
    # Return the newest request first
    return requests[-1]

BuildmasterConfig = c = {}
c['slaves'] = [BuildSlave('bot1', 'sekrit')]
c['schedulers'] = [Scheduler('dummy', None, 0, ['dummy'])]
c['builders'] = [
    BuilderConfig(name='dummy', slavenames=['bot1'], factory=f1, nextBuild=nextBuild),
]
c['slavePortnum'] = 0
c['mergeRequests'] = lambda builder, req1, req2: False
"""
class NextBuild(RunMixin, unittest.TestCase):
    def rmtree(self, d):
        rmtree(d)

    def testNextBuild(self):
        d = self.master.loadConfig(nextbuild_config)
        self.master.readConfig = True
        d.addCallback(lambda res: self.master.startService())

        start_order = []
        reqs = []

        def check(res):
            builder = self.status.getBuilder("dummy")
            self.failUnlessEqual(len(builder.slavenames), 1)
            self.failUnlessEqual(start_order, [4,3,2,1,0])

        def send(res):
            # send some build requests
            ss = SourceStamp()
            for i in range(5):
                req = BuildRequest(str(i), ss, "dummy")
                self.master.botmaster.builders['dummy'].submitBuildRequest(req)
                req.submittedAt = i
                def append(build):
                    start_order.append(int(build.reason))
                req.subscribe(append)
                reqs.append(req.waitUntilFinished())

        d.addCallback(send)
        d.addCallback(lambda res: self.connectSlave(slavename='bot1'))

        def connected(res):
            return defer.DeferredList(reqs)
        d.addCallback(connected)
        d.addCallback(check)
        return d

# Test prioritizeBuilders
prioritizebuilders_config = """
from buildbot.process import factory
from buildbot.steps import dummy
from buildbot.buildslave import BuildSlave
from buildbot.scheduler import Scheduler
from buildbot.config import BuilderConfig

f1 = factory.BuildFactory([dummy.Dummy(timeout=0)])

def prioritizeBuilders(buildmaster, builders):
    for builder in builders:
        if builder.name == 'dummy1':
            return [builder]
    return []

BuildmasterConfig = c = {}
c['slaves'] = [BuildSlave('bot1', 'sekrit')]
c['schedulers'] = [Scheduler('dummy', None, 0, ['dummy1', 'dummy2'])]
c['builders'] = [
    BuilderConfig(name='dummy1', slavename='bot1', factory=f1),
    BuilderConfig(name='dummy2', slavename='bot1', factory=f1),
]
c['slavePortnum'] = 0
c['mergeRequests'] = lambda builder, req1, req2: False
c['prioritizeBuilders'] = prioritizeBuilders
"""
class PrioritizeBuilders(RunMixin, unittest.TestCase):
    def rmtree(self, d):
        rmtree(d)

    def testPrioritizeBuilders(self):
        d = self.master.loadConfig(prioritizebuilders_config)
        self.master.readConfig = True
        d.addCallback(lambda res: self.master.startService())

        builder_names = []
        reqs = []
        incomplete_reqs = []
        complete_reqs = []

        def check(res):
            builder = self.status.getBuilder("dummy1")
            self.failUnlessEqual(len(builder.slavenames), 1)
            self.failUnlessEqual(builder_names, ['dummy1'] * 5)
            for req in incomplete_reqs:
                self.failUnlessEqual(req.startCount, 0)
            for req in complete_reqs:
                self.failUnlessEqual(req.startCount, 1)

        def send(res):
            # send some build requests
            ss = SourceStamp()
            for i in range(5):
                req1 = BuildRequest(str(i), ss, "dummy")
                self.master.botmaster.builders['dummy1'].submitBuildRequest(req1)
                req2 = BuildRequest(str(i), ss, "dummy")
                self.master.botmaster.builders['dummy2'].submitBuildRequest(req2)
                def append(build):
                    builder_names.append(build.builder.name)
                req1.subscribe(append)
                req2.subscribe(append)
                reqs.append(req1.waitUntilFinished())
                complete_reqs.append(req1)
                incomplete_reqs.append(req2)

        d.addCallback(send)
        d.addCallback(lambda res: self.connectSlave(slavename='bot1', builders=['dummy1', 'dummy2']))

        def connected(res):
            return defer.DeferredList(reqs)
        d.addCallback(connected)
        d.addCallback(check)
        return d
