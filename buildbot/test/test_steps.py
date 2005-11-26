# -*- test-case-name: buildbot.test.test_steps -*-

# create the BuildStep with a fake .remote instance that logs the
# .callRemote invocations and compares them against the expected calls. Then
# the test harness should send statusUpdate() messages in with assorted
# data, eventually calling remote_complete(). Then we can verify that the
# Step's rc was correct, and that the status it was supposed to return
# mathces.

# sometimes, .callRemote should raise an exception because of a stale
# reference. Sometimes it should errBack with an UnknownCommand failure.
# Or other failure.

# todo: test batched updates, by invoking remote_update(updates) instead of
# statusUpdate(update). Also involves interrupted builds.

import os, sys, time

from twisted.trial import unittest
from twisted.internet import reactor
from twisted.internet.defer import Deferred

from buildbot.sourcestamp import SourceStamp
from buildbot.process import step, base, factory
from buildbot.process.step import ShellCommand #, ShellCommands
from buildbot.status import builder
from buildbot.test.runutils import RunMixin
from buildbot.twcompat import maybeWait
from buildbot.slave import commands

from twisted.python import log
#log.startLogging(sys.stdout)

class MyShellCommand(ShellCommand):
    started = False
    def runCommand(self, c):
        self.started = True
        self.rc = c
        return ShellCommand.runCommand(self, c)

class FakeBuild:
    pass
class FakeBuilder:
    statusbag = None
    name = "fakebuilder"
class FakeSlaveBuilder:
    def getSlaveCommandVersion(self, command, oldversion=None):
        return "1.10"

class FakeRemote:
    def __init__(self):
        self.events = []
        self.remoteCalls = 0
        #self.callRemoteNotifier = None
    def callRemote(self, methname, *args):
        event = ["callRemote", methname, args]
        self.events.append(event)
##         if self.callRemoteNotifier:
##             reactor.callLater(0, self.callRemoteNotifier, event)
        self.remoteCalls += 1
        self.deferred = Deferred()
        return self.deferred
    def notifyOnDisconnect(self, callback):
        pass
    def dontNotifyOnDisconnect(self, callback):
        pass


class BuildStep(unittest.TestCase):
    def setUp(self):
        self.builder = FakeBuilder()
        self.builder_status = builder.BuilderStatus("fakebuilder")
        self.builder_status.basedir = "test_steps"
        self.builder_status.nextBuildNumber = 0
        os.mkdir(self.builder_status.basedir)
        self.build_status = self.builder_status.newBuild()
        req = base.BuildRequest("reason", SourceStamp())
        self.build = base.Build([req])
        self.build.build_status = self.build_status # fake it
        self.build.builder = self.builder
        self.build.slavebuilder = FakeSlaveBuilder()
        self.remote = FakeRemote()
        self.finished = 0

    def callback(self, results):
        self.failed = 0
        self.failure = None
        self.results = results
        self.finished = 1
    def errback(self, failure):
        self.failed = 1
        self.failure = failure
        self.results = None
        self.finished = 1

    def testShellCommand1(self):
        cmd = "argle bargle"
        dir = "murkle"
        expectedEvents = []
        step.RemoteCommand.commandCounter[0] = 3
        c = MyShellCommand(workdir=dir, command=cmd, build=self.build,
                           timeout=10)
        self.assertEqual(self.remote.events, expectedEvents)
        self.build_status.addStep(c)
        d = c.startStep(self.remote)
        self.failUnless(c.started)
        rc = c.rc
        d.addCallbacks(self.callback, self.errback)
        timeout = time.time() + 10
        while self.remote.remoteCalls == 0:
            if time.time() > timeout:
                self.fail("timeout")
            reactor.iterate(0.01)
        expectedEvents.append(["callRemote", "startCommand",
                               (rc, "3",
                               "shell",
                                {'command': "argle bargle",
                                 'workdir': "murkle",
                                 'want_stdout': 1,
                                 'want_stderr': 1,
                                 'timeout': 10,
                                 'env': None}) ] )
        self.assertEqual(self.remote.events, expectedEvents)

        # we could do self.remote.deferred.errback(UnknownCommand) here. We
        # could also do .callback(), but generally the master end silently
        # ignores the slave's ack

        logs = c.step_status.getLogs()
        for log in logs:
            if log.getName() == "log":
                break

        rc.remoteUpdate({'header':
                         "command 'argle bargle' in dir 'murkle'\n\n"})
        rc.remoteUpdate({'stdout': "foo\n"})
        self.assertEqual(log.getText(), "foo\n")
        self.assertEqual(log.getTextWithHeaders(),
                         "command 'argle bargle' in dir 'murkle'\n\n"
                         "foo\n")
        rc.remoteUpdate({'stderr': "bar\n"})
        self.assertEqual(log.getText(), "foo\nbar\n")
        self.assertEqual(log.getTextWithHeaders(),
                         "command 'argle bargle' in dir 'murkle'\n\n"
                         "foo\nbar\n")
        rc.remoteUpdate({'rc': 0})
        self.assertEqual(rc.rc, 0)
        
        rc.remote_complete()
        # that should fire the Deferred
        timeout = time.time() + 10
        while not self.finished:
            if time.time() > timeout:
                self.fail("timeout")
            reactor.iterate(0.01)
        self.assertEqual(self.failed, 0)
        self.assertEqual(self.results, 0)

class Steps(unittest.TestCase):
    def testMultipleStepInstances(self):
        steps = [
            (step.CVS, {'cvsroot': "root", 'cvsmodule': "module"}),
            (step.Configure, {'command': "./configure"}),
            (step.Compile, {'command': "make"}),
            (step.Compile, {'command': "make more"}),
            (step.Compile, {'command': "make evenmore"}),
            (step.Test, {'command': "make test"}),
            (step.Test, {'command': "make testharder"}),
            ]
        f = factory.ConfigurableBuildFactory(steps)
        req = base.BuildRequest("reason", SourceStamp())
        b = f.newBuild([req])
        #for s in b.steps: print s.name

class VersionCheckingStep(step.BuildStep):
    def start(self):
        # give our test a chance to run. It is non-trivial for a buildstep to
        # claw its way back out to the test case which is currently running.
        master = self.build.builder.botmaster.parent
        checker = master._checker
        checker(self)
        # then complete
        self.finished(step.SUCCESS)

version_config = """
from buildbot.process import factory, step
from buildbot.test.test_steps import VersionCheckingStep
BuildmasterConfig = c = {}
f1 = factory.BuildFactory([
    factory.s(VersionCheckingStep),
    ])
c['bots'] = [['bot1', 'sekrit']]
c['sources'] = []
c['schedulers'] = []
c['builders'] = [{'name':'quick', 'slavename':'bot1',
                  'builddir': 'quickdir', 'factory': f1}]
c['slavePortnum'] = 0
"""

class Version(RunMixin, unittest.TestCase):
    def setUp(self):
        RunMixin.setUp(self)
        self.master.loadConfig(version_config)
        self.master.startService()
        d = self.connectSlave(["quick"])
        return maybeWait(d)

    def doBuild(self, buildername):
        br = base.BuildRequest("forced", SourceStamp())
        d = br.waitUntilFinished()
        self.control.getBuilder(buildername).requestBuild(br)
        return d


    def checkCompare(self, s):
        v = s.slaveVersion("svn", None)
        # this insures that we are getting the version correctly
        self.failUnlessEqual(s.slaveVersion("svn", None), commands.cvs_ver)
        # and that non-existent commands do not provide a version
        self.failUnlessEqual(s.slaveVersion("NOSUCHCOMMAND"), None)
        # TODO: verify that a <=0.5.0 buildslave (which does not implement
        # remote_getCommands) handles oldversion= properly. This requires a
        # mutant slave which does not offer that method.
        #self.failUnlessEqual(s.slaveVersion("NOSUCHCOMMAND", "old"), "old")

        # now check the comparison functions
        self.failIf(s.slaveVersionIsOlderThan("svn", commands.cvs_ver))
        self.failIf(s.slaveVersionIsOlderThan("svn", "1.1"))
        self.failUnless(s.slaveVersionIsOlderThan("svn",
                                                  commands.cvs_ver + ".1"))

    def testCompare(self):
        self.master._checker = self.checkCompare
        d = self.doBuild("quick")
        return maybeWait(d)

