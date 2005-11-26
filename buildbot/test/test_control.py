# -*- test-case-name: buildbot.test.test_control -*-

import sys, os, signal, shutil, time, errno

from twisted.trial import unittest
from twisted.internet import defer, reactor

from buildbot import master, interfaces
from buildbot.sourcestamp import SourceStamp
from buildbot.twcompat import providedBy, maybeWait
from buildbot.slave import bot
from buildbot.status import builder
from buildbot.status.builder import SUCCESS
from buildbot.process import base

config = """
from buildbot.process import factory, step

def s(klass, **kwargs):
    return (klass, kwargs)

f1 = factory.BuildFactory([
    s(step.Dummy, timeout=1),
    ])
c = {}
c['bots'] = [['bot1', 'sekrit']]
c['sources'] = []
c['schedulers'] = []
c['builders'] = [{'name': 'force', 'slavename': 'bot1',
                  'builddir': 'force-dir', 'factory': f1}]
c['slavePortnum'] = 0
BuildmasterConfig = c
"""

class FakeBuilder:
    name = "fake"
    def getSlaveCommandVersion(self, command, oldversion=None):
        return "1.10"

class SignalMixin:
    sigchldHandler = None
    
    def setUpClass(self):
        # make sure SIGCHLD handler is installed, as it should be on
        # reactor.run(). problem is reactor may not have been run when this
        # test runs.
        if hasattr(reactor, "_handleSigchld") and hasattr(signal, "SIGCHLD"):
            self.sigchldHandler = signal.signal(signal.SIGCHLD,
                                                reactor._handleSigchld)
    
    def tearDownClass(self):
        if self.sigchldHandler:
            signal.signal(signal.SIGCHLD, self.sigchldHandler)

class Force(unittest.TestCase):

    def rmtree(self, d):
        try:
            shutil.rmtree(d, ignore_errors=1)
        except OSError, e:
            # stupid 2.2 appears to ignore ignore_errors
            if e.errno != errno.ENOENT:
                raise

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
        return maybeWait(defer.DeferredList(dl))

    def testForce(self):
        # TODO: since BuilderControl.forceBuild has been deprecated, this
        # test is scheduled to be removed soon
        m = self.master
        m.loadConfig(config)
        m.startService()
        d = self.connectSlave()
        d.addCallback(self._testForce_1)
        return maybeWait(d)

    def _testForce_1(self, res):
        c = interfaces.IControl(self.master)
        builder_control = c.getBuilder("force")
        d = builder_control.forceBuild("bob", "I was bored")
        d.addCallback(self._testForce_2)
        return d

    def _testForce_2(self, build_control):
        self.failUnless(providedBy(build_control, interfaces.IBuildControl))
        d = build_control.getStatus().waitUntilFinished()
        d.addCallback(self._testForce_3)
        return d

    def _testForce_3(self, bs):
        self.failUnless(providedBy(bs, interfaces.IBuildStatus))
        self.failUnless(bs.isFinished())
        self.failUnlessEqual(bs.getResults(), SUCCESS)
        #self.failUnlessEqual(bs.getResponsibleUsers(), ["bob"]) # TODO
        self.failUnlessEqual(bs.getChanges(), [])
        #self.failUnlessEqual(bs.getReason(), "forced") # TODO

    def testRequest(self):
        m = self.master
        m.loadConfig(config)
        m.startService()
        d = self.connectSlave()
        d.addCallback(self._testRequest_1)
        return maybeWait(d)
    def _testRequest_1(self, res):
        c = interfaces.IControl(self.master)
        req = base.BuildRequest("I was bored", SourceStamp())
        builder_control = c.getBuilder("force")
        d = defer.Deferred()
        req.subscribe(d.callback)
        builder_control.requestBuild(req)
        d.addCallback(self._testForce_2)
        # we use the same check-the-results code as testForce
        return d
