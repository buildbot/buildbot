# -*- test-case-name: buildbot.test.test_control -*-

import os

from twisted.trial import unittest
from twisted.internet import defer

from buildbot import master, interfaces
from buildbot.sourcestamp import SourceStamp
from buildbot.slave import bot
from buildbot.status.builder import SUCCESS
from buildbot.process import base
from buildbot.test.runutils import rmtree

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

class FakeBuilder:
    name = "fake"
    def getSlaveCommandVersion(self, command, oldversion=None):
        return "1.10"


class Force(unittest.TestCase):

    def rmtree(self, d):
        rmtree(d)

    def setUp(self):
        self.master = None
        self.slave = None
        self.rmtree("control_basedir")
        os.mkdir("control_basedir")
        self.master = master.BuildMaster("control_basedir")
        self.slavebase = os.path.abspath("control_slavebase")
        self.rmtree(self.slavebase)
        os.mkdir("control_slavebase")

    def connectSlave(self):
        port = self.master.slavePort._port.getHost().port
        slave = bot.BuildSlave("localhost", port, "bot1", "sekrit",
                               self.slavebase, keepalive=0, usePTY=1)
        self.slave = slave
        slave.startService()
        d = self.master.botmaster.waitUntilBuilderAttached("force")
        return d

    def tearDown(self):
        dl = []
        if self.slave:
            dl.append(self.master.botmaster.waitUntilBuilderDetached("force"))
            dl.append(defer.maybeDeferred(self.slave.stopService))
        if self.master:
            dl.append(defer.maybeDeferred(self.master.stopService))
        return defer.DeferredList(dl)

    def testRequest(self):
        m = self.master
        m.loadConfig(config)
        m.startService()
        d = self.connectSlave()
        d.addCallback(self._testRequest_1)
        return d
    def _testRequest_1(self, res):
        c = interfaces.IControl(self.master)
        req = base.BuildRequest("I was bored", SourceStamp(), 'test_builder')
        builder_control = c.getBuilder("force")
        d = defer.Deferred()
        req.subscribe(d.callback)
        builder_control.requestBuild(req)
        d.addCallback(self._testRequest_2)
        # we use the same check-the-results code as testForce
        return d

    def _testRequest_2(self, build_control):
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
