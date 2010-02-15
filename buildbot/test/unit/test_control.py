# -*- test-case-name: buildbot.test.test_control -*-

from twisted.trial import unittest

from buildbot import interfaces
from buildbot.sourcestamp import SourceStamp
from buildbot.status.builder import SUCCESS
from buildbot.test.runutils import MasterMixin

config = """
from buildbot.process import factory
from buildbot.steps import dummy
from buildbot.buildslave import BuildSlave
from buildbot.config import BuilderConfig

def s(klass, **kwargs):
    return (klass, kwargs)

f1 = factory.BuildFactory([
    s(dummy.Dummy, timeout=1),
    ])
c = {}
c['slaves'] = [BuildSlave('bot1', 'sekrit')]
c['schedulers'] = []
c['builders'] = [
    BuilderConfig(name='force', slavename='bot1', factory=f1),
]
c['slavePortnum'] = 0
BuildmasterConfig = c
"""


class Force(MasterMixin, unittest.TestCase):
    # exercise methods of master.Control, BuilderControl, and BuildControl

    def testRequest(self):
        self.basedir = "control/Force/request"
        self.create_master()
        d = self.master.loadConfig(config)
        d.addCallback(lambda ign: self.connectSlave(builders=["force"]))
        d.addCallback(self._testRequest_1)
        d.addCallback(self._testRequest_2)
        d.addCallback(self._testRequest_3)
        return d

    def _testRequest_1(self, res):
        c = interfaces.IControl(self.master)
        bss = c.submitBuildSet(["force"], SourceStamp(), "I was bored") # X
        d = bss.waitUntilFinished()
        return d

    def _testRequest_2(self, bss):
        return bss.getBuildRequests()[0].getBuilds()[0]

    def PFF_testRequest_2(self, build_control):
        self.failUnless(interfaces.IBuildControl.providedBy(build_control))
        d = build_control.getStatus().waitUntilFinished()
        d.addCallback(self._testRequest_3)
        return d

    def _testRequest_3(self, bs):
        self.failUnless(interfaces.IBuildStatus.providedBy(bs))
        self.failUnless(bs.isFinished())
        self.failUnlessEqual(bs.getResults(), SUCCESS)
        #self.failUnlessEqual(bs.getResponsibleUsers(), ["bob"]) # TODO
        self.failUnlessEqual(bs.getChanges(), ())
        #self.failUnlessEqual(bs.getReason(), "forced") # TODO
