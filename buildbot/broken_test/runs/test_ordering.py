from twisted.trial import unittest
from twisted.internet import  defer

from buildbot.broken_test.runutils import MasterMixin, rmtree
from buildbot.sourcestamp import SourceStamp

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
class NextSlave(MasterMixin, unittest.TestCase):
    def rmtree(self, d):
        rmtree(d)

    def testNextSlave(self):
        self.basedir = "ordering/NextSlave/nextslave"
        self.create_master()
        d = self.master.loadConfig(nextslave_config)
        d.addCallback(lambda res: self.connectSlave(slavename='bot1'))
        d.addCallback(lambda res: self.connectSlave(slavename='bot2'))

        def _send(res):
            # send some build requests
            reqs = []
            ss = SourceStamp()
            for i in range(5):
                bss = self.control.submitBuildSet(["dummy"], ss, reason=str(i))
                reqs.append(bss.waitUntilFinished())
            return defer.DeferredList(reqs)
        d.addCallback(_send)

        def check(res):
            builder = self.status.getBuilder("dummy")
            self.failUnlessEqual(len(builder.slavenames), 2)
            for i in range(5):
                build = builder.getBuild(i)
                self.failUnlessEqual(build.slavename, 'bot1')
        d.addCallback(check)

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
class NextBuild(MasterMixin, unittest.TestCase):
    def rmtree(self, d):
        rmtree(d)

    def testNextBuild(self):
        self.basedir = "ordering/NextBuild/NextBuild"
        self.create_master()
        d = self.master.loadConfig(nextbuild_config)

        start_order = []
        reqs = []

        def send(res):
            # send some build requests
            ss = SourceStamp()
            def append(buildstatus):
                start_order.append(int(buildstatus.reason))
            for i in range(5):
                bss = self.control.submitBuildSet(["dummy"], ss, reason=str(i))
                brs = bss.getBuildRequests()[0]
                ##d = self.requestBuild("dummy")
                #req = BuildRequest(str(i), ss, "dummy")
                #self.master.botmaster.builders['dummy'].submitBuildRequest(req)
                #req.submittedAt = i
                brs.subscribe(append)
                reqs.append(bss.waitUntilFinished())
        d.addCallback(send)
        d.addCallback(lambda res: self.connectSlave(slavename='bot1'))

        def connected(res):
            return defer.DeferredList(reqs)
        d.addCallback(connected)

        def check(res):
            builder = self.status.getBuilder("dummy")
            self.failUnlessEqual(len(builder.slavenames), 1)
            self.failUnlessEqual(start_order, [4,3,2,1,0])
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
class PrioritizeBuilders(MasterMixin, unittest.TestCase):
    def rmtree(self, d):
        rmtree(d)

    def testPrioritizeBuilders(self):
        self.basedir = "ordering/PrioritizeBuilders/PrioritizeBuilders"
        self.create_master()
        d = self.master.loadConfig(prioritizebuilders_config)

        builder_names = []
        incomplete_reqs = []
        complete_reqs = []

        def send(res):
            # send some build requests
            ss = SourceStamp()
            reqs = []
            def append(buildstatus):
                builder_names.append(buildstatus.builder.name)
            for i in range(5):
                r = str(i)
                bss1 = self.control.submitBuildSet(["dummy1"], ss, reason=r)
                brs1 = bss1.getBuildRequests()[0]
                brs1.subscribe(append)
                complete_reqs.append(brs1)

                bss2 = self.control.submitBuildSet(["dummy2"], ss, reason=r)
                brs2 = bss2.getBuildRequests()[0]
                brs2.subscribe(append)
                incomplete_reqs.append(brs2)

                reqs.append(bss1.waitUntilFinished()) # only bss1, not bss2

            # now that all the requests are queued, connect the slave
            d = self.connectSlave(slavename='bot1',
                                  builders=['dummy1', 'dummy2'])
            # after they connect, wait for the builds to finish
            d.addCallback(lambda ign: defer.DeferredList(reqs))
            return d
        d.addCallback(send)

        def check(res):
            builder = self.status.getBuilder("dummy1")
            self.failUnlessEqual(len(builder.slavenames), 1)
            self.failUnlessEqual(builder_names, ['dummy1'] * 5)
            for brs in incomplete_reqs:
                self.failUnlessEqual(len(brs.getBuilds()), 0)
            for brs in complete_reqs:
                self.failUnlessEqual(len(brs.getBuilds()), 1)

        d.addCallback(check)
        return d
