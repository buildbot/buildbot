# -*- test-case-name: buildbot.test.test_steps -*-

# create the BuildStep with a fake .remote instance that logs the
# .callRemote invocations and compares them against the expected calls. Then
# the test harness should send statusUpdate() messages in with assorted
# data, eventually calling remote_complete(). Then we can verify that the
# Step's rc was correct, and that the status it was supposed to return
# matches.

# sometimes, .callRemote should raise an exception because of a stale
# reference. Sometimes it should errBack with an UnknownCommand failure.
# Or other failure.

# todo: test batched updates, by invoking remote_update(updates) instead of
# statusUpdate(update). Also involves interrupted builds.

import sys
import os

from twisted.trial import unittest
from twisted.internet import reactor, defer

from buildbot.sourcestamp import SourceStamp
from buildbot.process import buildstep, base, factory
from buildbot.process.properties import Properties, WithProperties
from buildbot.buildslave import BuildSlave
from buildbot.steps import shell, source, python, master
from buildbot.status import builder
from buildbot.status.builder import SUCCESS, WARNINGS, FAILURE, SKIPPED
from buildbot.test.runutils import RunMixin, rmtree
from buildbot.test.runutils import makeBuildStep, StepTester
from buildbot.slave import commands, registry


class MyShellCommand(shell.ShellCommand):
    started = False
    def runCommand(self, c):
        self.started = True
        self.rc = c
        return shell.ShellCommand.runCommand(self, c)

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
        self.deferred = defer.Deferred()
        return self.deferred
    def notifyOnDisconnect(self, callback):
        pass
    def dontNotifyOnDisconnect(self, callback):
        pass


class BuildStep(unittest.TestCase):

    def setUp(self):
        rmtree("test_steps")
        self.builder = FakeBuilder()
        self.builder_status = builder.BuilderStatus("fakebuilder")
        self.builder_status.basedir = "test_steps"
        self.builder_status.nextBuildNumber = 0
        os.mkdir(self.builder_status.basedir)
        self.build_status = self.builder_status.newBuild()
        req = base.BuildRequest("reason", SourceStamp(), 'test_builder')
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
        self.expectedEvents = []
        buildstep.RemoteCommand.commandCounter[0] = 3
        c = MyShellCommand(workdir=dir, command=cmd, timeout=10)
        c.setBuild(self.build)
        c.setBuildSlave(BuildSlave("name", "password"))
        self.assertEqual(self.remote.events, self.expectedEvents)
        c.step_status = self.build_status.addStepWithName("myshellcommand")
        d = c.startStep(self.remote)
        self.failUnless(c.started)
        d.addCallbacks(self.callback, self.errback)
        d2 = self.poll()
        d2.addCallback(self._testShellCommand1_2, c)
        return d2
    testShellCommand1.timeout = 10

    def poll(self, ignored=None):
        # TODO: This is gross, but at least it's no longer using
        # reactor.iterate() . Still, get rid of this some day soon.
        if self.remote.remoteCalls == 0:
            d = defer.Deferred()
            d.addCallback(self.poll)
            reactor.callLater(0.1, d.callback, None)
            return d
        return defer.succeed(None)

    def _testShellCommand1_2(self, res, c):
        rc = c.rc
        self.expectedEvents.append(["callRemote", "startCommand",
                               (rc, "3",
                               "shell",
                                {'command': "argle bargle",
                                 'workdir': "murkle",
                                 'logEnviron' : True,
                                 'want_stdout': 1,
                                 'want_stderr': 1,
                                 'logfiles': {},
                                 'timeout': 10,
                                 'maxTime': None,
                                 'usePTY': 'slave-config',
                                 'env': None}) ] )
        self.assertEqual(self.remote.events, self.expectedEvents)

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
        d = self.poll2()
        d.addCallback(self._testShellCommand1_3)
        return d

    def poll2(self, ignored=None):
        if not self.finished:
            d = defer.Deferred()
            d.addCallback(self.poll2)
            reactor.callLater(0.1, d.callback, None)
            return d
        return defer.succeed(None)

    def _testShellCommand1_3(self, res):
        self.assertEqual(self.failed, 0)
        self.assertEqual(self.results, 0)


class MyObserver(buildstep.LogObserver):
    out = ""
    def outReceived(self, data):
        self.out = self.out + data

class Steps(unittest.TestCase):
    def testMultipleStepInstances(self):
        steps = [
            (source.CVS, {'cvsroot': "root", 'cvsmodule': "module"}),
            (shell.Configure, {'command': "./configure"}),
            (shell.Compile, {'command': "make"}),
            (shell.Compile, {'command': "make more"}),
            (shell.Compile, {'command': "make evenmore"}),
            (shell.Test, {'command': "make test"}),
            (shell.Test, {'command': "make testharder"}),
            ]
        f = factory.ConfigurableBuildFactory(steps)
        req = base.BuildRequest("reason", SourceStamp(), 'test_builder')
        b = f.newBuild([req])
        #for s in b.steps: print s.name

    def failUnlessClones(self, s1, attrnames):
        f1 = s1.getStepFactory()
        f,args = f1
        s2 = f(**args)
        for name in attrnames:
            self.failUnlessEqual(getattr(s1, name), getattr(s2, name))

    def clone(self, s1):
        f1 = s1.getStepFactory()
        f,args = f1
        s2 = f(**args)
        return s2

    def testClone(self):
        s1 = shell.ShellCommand(command=["make", "test"],
                                timeout=1234,
                                workdir="here",
                                description="yo",
                                descriptionDone="yoyo",
                                env={'key': 'value'},
                                want_stdout=False,
                                want_stderr=False,
                                logfiles={"name": "filename"},
                               )
        shellparms = (buildstep.BuildStep.parms +
                      ("remote_kwargs description descriptionDone "
                       "command logfiles").split() )
        self.failUnlessClones(s1, shellparms)


    # test the various methods available to buildsteps

    def test_getProperty(self):
        s = makeBuildStep("test_steps.Steps.test_getProperty")
        bs = s.step_status.getBuild()

        s.setProperty("prop1", "value1", "test")
        s.setProperty("prop2", "value2", "test")
        self.failUnlessEqual(s.getProperty("prop1"), "value1")
        self.failUnlessEqual(bs.getProperty("prop1"), "value1")
        self.failUnlessEqual(s.getProperty("prop2"), "value2")
        self.failUnlessEqual(bs.getProperty("prop2"), "value2")
        s.setProperty("prop1", "value1a", "test")
        self.failUnlessEqual(s.getProperty("prop1"), "value1a")
        self.failUnlessEqual(bs.getProperty("prop1"), "value1a")


    def test_addURL(self):
        s = makeBuildStep("test_steps.Steps.test_addURL")
        s.addURL("coverage", "http://coverage.example.org/target")
        s.addURL("icon", "http://coverage.example.org/icon.png")
        bs = s.step_status
        links = bs.getURLs()
        expected = {"coverage": "http://coverage.example.org/target",
                    "icon": "http://coverage.example.org/icon.png",
                    }
        self.failUnlessEqual(links, expected)

    def test_addLog(self):
        s = makeBuildStep("test_steps.Steps.test_addLog")
        l = s.addLog("newlog")
        l.addStdout("some stdout here")
        l.finish()
        bs = s.step_status
        logs = bs.getLogs()
        self.failUnlessEqual(len(logs), 1)
        l1 = logs[0]
        self.failUnlessEqual(l1.getText(), "some stdout here")
        l1a = s.getLog("newlog")
        self.failUnlessEqual(l1a.getText(), "some stdout here")

    def test_addHTMLLog(self):
        s = makeBuildStep("test_steps.Steps.test_addHTMLLog")
        l = s.addHTMLLog("newlog", "some html here")
        bs = s.step_status
        logs = bs.getLogs()
        self.failUnlessEqual(len(logs), 1)
        l1 = logs[0]
        self.failUnless(isinstance(l1, builder.HTMLLogFile))
        self.failUnlessEqual(l1.getText(), "some html here")

    def test_addCompleteLog(self):
        s = makeBuildStep("test_steps.Steps.test_addCompleteLog")
        l = s.addCompleteLog("newlog", "some stdout here")
        bs = s.step_status
        logs = bs.getLogs()
        self.failUnlessEqual(len(logs), 1)
        l1 = logs[0]
        self.failUnlessEqual(l1.getText(), "some stdout here")
        l1a = s.getLog("newlog")
        self.failUnlessEqual(l1a.getText(), "some stdout here")

    def test_addLogObserver(self):
        s = makeBuildStep("test_steps.Steps.test_addLogObserver")
        bss = s.step_status
        o1,o2,o3 = MyObserver(), MyObserver(), MyObserver()

        # add the log before the observer
        l1 = s.addLog("one")
        l1.addStdout("onestuff")
        s.addLogObserver("one", o1)
        self.failUnlessEqual(o1.out, "onestuff")
        l1.addStdout(" morestuff")
        self.failUnlessEqual(o1.out, "onestuff morestuff")

        # add the observer before the log
        s.addLogObserver("two", o2)
        l2 = s.addLog("two")
        l2.addStdout("twostuff")
        self.failUnlessEqual(o2.out, "twostuff")

    # test more stuff about ShellCommands

    def test_description(self):
        s = makeBuildStep("test_steps.Steps.test_description.1",
                          step_class=shell.ShellCommand,
                          workdir="dummy",
                          description=["list", "of", "strings"],
                          descriptionDone=["another", "list"])
        self.failUnlessEqual(s.description, ["list", "of", "strings"])
        self.failUnlessEqual(s.descriptionDone, ["another", "list"])

        s = makeBuildStep("test_steps.Steps.test_description.2",
                          step_class=shell.ShellCommand,
                          workdir="dummy",
                          description="single string",
                          descriptionDone="another string")
        self.failUnlessEqual(s.description, ["single string"])
        self.failUnlessEqual(s.descriptionDone, ["another string"])

class VersionCheckingStep(buildstep.BuildStep):
    def start(self):
        # give our test a chance to run. It is non-trivial for a buildstep to
        # claw its way back out to the test case which is currently running.
        master = self.build.builder.botmaster.parent
        checker = master._checker
        checker(self)
        # then complete
        self.finished(buildstep.SUCCESS)

version_config = """
from buildbot.process import factory
from buildbot.test.test_steps import VersionCheckingStep
from buildbot.buildslave import BuildSlave
from buildbot.config import BuilderConfig
BuildmasterConfig = c = {}
f1 = factory.BuildFactory([
    factory.s(VersionCheckingStep),
    ])
c['slaves'] = [BuildSlave('bot1', 'sekrit')]
c['schedulers'] = []
c['builders'] = [
    BuilderConfig(name='quick', slavename='bot1', factory=f1,
            builddir='quickdir', slavebuilddir='quickslavedir'),
]
c['slavePortnum'] = 0
"""

class SlaveVersion(RunMixin, unittest.TestCase):
    def setUp(self):
        RunMixin.setUp(self)
        self.master.loadConfig(version_config)
        self.master.startService()
        d = self.connectSlave(["quick"])
        return d

    def doBuild(self, buildername):
        br = base.BuildRequest("forced", SourceStamp(), 'test_builder')
        d = br.waitUntilFinished()
        self.control.getBuilder(buildername).requestBuild(br)
        return d


    def checkCompare(self, s):
        cver = commands.command_version
        v = s.slaveVersion("svn", None)
        # this insures that we are getting the version correctly
        self.failUnlessEqual(s.slaveVersion("svn", None), cver)
        # and that non-existent commands do not provide a version
        self.failUnlessEqual(s.slaveVersion("NOSUCHCOMMAND"), None)
        # TODO: verify that a <=0.5.0 buildslave (which does not implement
        # remote_getCommands) handles oldversion= properly. This requires a
        # mutant slave which does not offer that method.
        #self.failUnlessEqual(s.slaveVersion("NOSUCHCOMMAND", "old"), "old")

        # now check the comparison functions
        self.failIf(s.slaveVersionIsOlderThan("svn", cver))
        self.failIf(s.slaveVersionIsOlderThan("svn", "1.1"))
        self.failUnless(s.slaveVersionIsOlderThan("svn", cver + ".1"))

        self.failUnlessEqual(s.getSlaveName(), "bot1")

    def testCompare(self):
        self.master._checker = self.checkCompare
        d = self.doBuild("quick")
        return d


class _SimpleBuildStep(buildstep.BuildStep):
    def start(self):
        args = {"arg1": "value"}
        cmd = buildstep.RemoteCommand("simple", args)
        d = self.runCommand(cmd)
        d.addCallback(lambda res: self.finished(SUCCESS))

class _SimpleCommand(commands.Command):
    def start(self):
        self.builder.flag = True
        self.builder.flag_args = self.args
        return defer.succeed(None)

class CheckStepTester(StepTester, unittest.TestCase):
    def testSimple(self):
        self.slavebase = "testSimple.slave"
        self.masterbase = "testSimple.master"
        sb = self.makeSlaveBuilder()
        sb.flag = False
        registry.registerSlaveCommand("simple", _SimpleCommand, "1")
        step = self.makeStep(_SimpleBuildStep)
        d = self.runStep(step)
        def _checkSimple(results):
            self.failUnless(sb.flag)
            self.failUnlessEqual(sb.flag_args, {"arg1": "value"})
        d.addCallback(_checkSimple)
        return d

class Python(StepTester, unittest.TestCase):
    def testPyFlakes1(self):
        self.masterbase = "Python.testPyFlakes1"
        step = self.makeStep(python.PyFlakes)
        output = \
"""pyflakes buildbot
buildbot/changes/freshcvsmail.py:5: 'FCMaildirSource' imported but unused
buildbot/clients/debug.py:9: redefinition of unused 'gtk' from line 9
buildbot/clients/debug.py:9: 'gnome' imported but unused
buildbot/scripts/runner.py:323: redefinition of unused 'run' from line 321
buildbot/scripts/runner.py:325: redefinition of unused 'run' from line 323
buildbot/scripts/imaginary.py:12: undefined name 'size'
buildbot/scripts/imaginary.py:18: 'from buildbot import *' used; unable to detect undefined names
"""
        log = step.addLog("stdio")
        log.addStdout(output)
        log.finish()
        step.createSummary(log)
        desc = step.descriptionDone
        self.failUnless("unused=2" in desc)
        self.failUnless("undefined=1" in desc)
        self.failUnless("redefs=3" in desc)
        self.failUnless("import*=1" in desc)
        self.failIf("misc=" in desc)

        self.failUnlessEqual(step.getProperty("pyflakes-unused"), 2)
        self.failUnlessEqual(step.getProperty("pyflakes-undefined"), 1)
        self.failUnlessEqual(step.getProperty("pyflakes-redefs"), 3)
        self.failUnlessEqual(step.getProperty("pyflakes-import*"), 1)
        self.failUnlessEqual(step.getProperty("pyflakes-misc"), 0)
        self.failUnlessEqual(step.getProperty("pyflakes-total"), 7)

        logs = {}
        for log in step.step_status.getLogs():
            logs[log.getName()] = log

        for name in ["unused", "undefined", "redefs", "import*"]:
            self.failUnless(name in logs)
        self.failIf("misc" in logs)
        lines = logs["unused"].readlines()
        self.failUnlessEqual(len(lines), 2)
        self.failUnlessEqual(lines[0], "buildbot/changes/freshcvsmail.py:5: 'FCMaildirSource' imported but unused\n")

        cmd = buildstep.RemoteCommand(None, {})
        cmd.rc = 0
        results = step.evaluateCommand(cmd)
        self.failUnlessEqual(results, FAILURE) # because of the 'undefined'

    def testPyFlakes2(self):
        self.masterbase = "Python.testPyFlakes2"
        step = self.makeStep(python.PyFlakes)
        output = \
"""pyflakes buildbot
some more text here that should be ignored
buildbot/changes/freshcvsmail.py:5: 'FCMaildirSource' imported but unused
buildbot/clients/debug.py:9: redefinition of unused 'gtk' from line 9
buildbot/clients/debug.py:9: 'gnome' imported but unused
buildbot/scripts/runner.py:323: redefinition of unused 'run' from line 321
buildbot/scripts/runner.py:325: redefinition of unused 'run' from line 323
buildbot/scripts/imaginary.py:12: undefined name 'size'
could not compile 'blah/blah.py':3:
pretend there was an invalid line here
buildbot/scripts/imaginary.py:18: 'from buildbot import *' used; unable to detect undefined names
"""
        log = step.addLog("stdio")
        log.addStdout(output)
        log.finish()
        step.createSummary(log)
        desc = step.descriptionDone
        self.failUnless("unused=2" in desc)
        self.failUnless("undefined=1" in desc)
        self.failUnless("redefs=3" in desc)
        self.failUnless("import*=1" in desc)
        self.failUnless("misc=2" in desc)


    def testPyFlakes3(self):
        self.masterbase = "Python.testPyFlakes3"
        step = self.makeStep(python.PyFlakes)
        output = \
"""buildbot/changes/freshcvsmail.py:5: 'FCMaildirSource' imported but unused
buildbot/clients/debug.py:9: redefinition of unused 'gtk' from line 9
buildbot/clients/debug.py:9: 'gnome' imported but unused
buildbot/scripts/runner.py:323: redefinition of unused 'run' from line 321
buildbot/scripts/runner.py:325: redefinition of unused 'run' from line 323
buildbot/scripts/imaginary.py:12: undefined name 'size'
buildbot/scripts/imaginary.py:18: 'from buildbot import *' used; unable to detect undefined names
"""
        log = step.addLog("stdio")
        log.addStdout(output)
        log.finish()
        step.createSummary(log)
        desc = step.descriptionDone
        self.failUnless("unused=2" in desc)
        self.failUnless("undefined=1" in desc)
        self.failUnless("redefs=3" in desc)
        self.failUnless("import*=1" in desc)
        self.failIf("misc" in desc)


class OrdinaryCompile(shell.Compile):
    warningPattern = "ordinary line"

class Warnings(StepTester, unittest.TestCase):
    def testCompile1(self):
        self.masterbase = "Warnings.testCompile1"
        step = self.makeStep(shell.Compile)
        output = \
"""Compile started
normal line
warning: oh noes!
ordinary line
error (but we aren't looking for errors now, are we)
line 23: warning: we are now on line 23
ending line
"""
        log = step.addLog("stdio")
        log.addStdout(output)
        log.finish()
        step.createSummary(log)
        self.failUnlessEqual(step.getProperty("warnings-count"), 2)
        logs = {}
        for log in step.step_status.getLogs():
            logs[log.getName()] = log
        self.failUnless("warnings" in logs)
        lines = logs["warnings"].readlines()
        self.failUnlessEqual(len(lines), 2)
        self.failUnlessEqual(lines[0], "warning: oh noes!\n")
        self.failUnlessEqual(lines[1],
                             "line 23: warning: we are now on line 23\n")

        cmd = buildstep.RemoteCommand(None, {})
        cmd.rc = 0
        results = step.evaluateCommand(cmd)
        self.failUnlessEqual(results, WARNINGS)

    def testCompile2(self):
        self.masterbase = "Warnings.testCompile2"
        step = self.makeStep(shell.Compile, warningPattern="ordinary line")
        output = \
"""Compile started
normal line
warning: oh noes!
ordinary line
error (but we aren't looking for errors now, are we)
line 23: warning: we are now on line 23
ending line
"""
        log = step.addLog("stdio")
        log.addStdout(output)
        log.finish()
        step.createSummary(log)
        self.failUnlessEqual(step.getProperty("warnings-count"), 1)
        logs = {}
        for log in step.step_status.getLogs():
            logs[log.getName()] = log
        self.failUnless("warnings" in logs)
        lines = logs["warnings"].readlines()
        self.failUnlessEqual(len(lines), 1)
        self.failUnlessEqual(lines[0], "ordinary line\n")

        cmd = buildstep.RemoteCommand(None, {})
        cmd.rc = 0
        results = step.evaluateCommand(cmd)
        self.failUnlessEqual(results, WARNINGS)

    def testCompile3(self):
        self.masterbase = "Warnings.testCompile3"
        step = self.makeStep(OrdinaryCompile)
        output = \
"""Compile started
normal line
warning: oh noes!
ordinary line
error (but we aren't looking for errors now, are we)
line 23: warning: we are now on line 23
ending line
"""
        step.setProperty("warnings-count", 10, "test")
        log = step.addLog("stdio")
        log.addStdout(output)
        log.finish()
        step.createSummary(log)
        self.failUnlessEqual(step.getProperty("warnings-count"), 11)
        logs = {}
        for log in step.step_status.getLogs():
            logs[log.getName()] = log
        self.failUnless("warnings" in logs)
        lines = logs["warnings"].readlines()
        self.failUnlessEqual(len(lines), 1)
        self.failUnlessEqual(lines[0], "ordinary line\n")

        cmd = buildstep.RemoteCommand(None, {})
        cmd.rc = 0
        results = step.evaluateCommand(cmd)
        self.failUnlessEqual(results, WARNINGS)

    def testCompile4(self):
        # Test suppression of warnings.
        self.masterbase = "Warnings.testCompile4"
        step = self.makeStep(shell.Compile,
                             warningPattern="^(.*?):([0-9]+): [Ww]arning: (.*)$",
                             warningExtractor=shell.Compile.warnExtractFromRegexpGroups,
                             directoryEnterPattern="make.*: Entering directory [\"`'](.*)['`\"]",
                             directoryLeavePattern="make.*: Leaving directory")
        step.addSuppression([(r"/subdir/", r"xyzzy", None, None),
                             (r"foo.c", r".*", None, 20),
                             (r"foo.c", r".*", 200, None),
                             (r"foo.c", r".*", 50, 50),
                             (r"xxx", r".*", None, None),
                             ])
        log = step.addLog("stdio")
        output = \
"""Making all in .
make[1]: Entering directory `/abs/path/build'
foo.c:10: warning: `bar' defined but not used
foo.c:50: warning: `bar' defined but not used
make[2]: Entering directory `/abs/path/build/subdir'
baz.c:33: warning: `xyzzy' defined but not used
baz.c:34: warning: `magic' defined but not used
make[2]: Leaving directory `/abs/path/build/subdir'
foo.c:100: warning: `xyzzy' defined but not used
foo.c:200: warning: `bar' defined but not used
make[2]: Leaving directory `/abs/path/build'
"""
        log.addStdout(output)
        log.finish()
        step.createSummary(log)
        self.failUnlessEqual(step.getProperty("warnings-count"), 2)
        logs = {}
        for log in step.step_status.getLogs():
            logs[log.getName()] = log
        self.failUnless("warnings" in logs)
        lines = logs["warnings"].readlines()
        self.failUnlessEqual(len(lines), 2)
        self.failUnlessEqual(lines[0], "baz.c:34: warning: `magic' defined but not used\n")
        self.failUnlessEqual(lines[1], "foo.c:100: warning: `xyzzy' defined but not used\n")

        cmd = buildstep.RemoteCommand(None, {})
        cmd.rc = 0
        results = step.evaluateCommand(cmd)
        self.failUnlessEqual(results, WARNINGS)

    def filterArgs(self, args):
        if "writer" in args:
            args["writer"] = self.wrap(args["writer"])
        return args

    suppressionFileData = """
# Sample suppressions file for testing

/subdir/ : xyzzy
foo.c: .* : 0-20
foo.c: .*: 200-10000
foo.c :.*: 50
xxx : .*
"""
    def testCompile5(self):
        # Test downloading warning suppression file from slave.
        self.slavebase = "Warnings.testCompile5.slave"
        self.masterbase = "Warnings.testCompile5.master"
        sb = self.makeSlaveBuilder()
        os.mkdir(os.path.join(self.slavebase, self.slavebuilderbase,
                              "build"))
        output = \
"""Making all in .
make[1]: Entering directory `/abs/path/build'
foo.c:10: warning: `bar' defined but not used
foo.c:50: warning: `bar' defined but not used
make[2]: Entering directory `/abs/path/build/subdir'
baz.c:33: warning: `xyzzy' defined but not used
baz.c:34: warning: `magic' defined but not used
make[2]: Leaving directory `/abs/path/build/subdir'
foo.c:100: warning: `xyzzy' defined but not used
foo.c:200: warning: `bar' defined but not used
make[2]: Leaving directory `/abs/path/build'
"""
        printStatement = ('print """%s"""' % output)
        step = self.makeStep(shell.Compile,
                             warningPattern="^(.*?):([0-9]+): [Ww]arning: (.*)$",
                             warningExtractor=shell.Compile.warnExtractFromRegexpGroups,
                             suppressionFile="warnings.supp",
                             command=[sys.executable, "-c", printStatement])
        slavesrc = os.path.join(self.slavebase,
                                self.slavebuilderbase,
                                "build",
                                "warnings.supp")
        open(slavesrc, "w").write(self.suppressionFileData)

        d = self.runStep(step)
        def _checkResult(result):
            self.failUnlessEqual(step.getProperty("warnings-count"), 2)
            logs = {}
            for log in step.step_status.getLogs():
                logs[log.getName()] = log
            self.failUnless("warnings" in logs)
            lines = logs["warnings"].readlines()
            self.failUnlessEqual(len(lines), 2)
            self.failUnlessEqual(lines[0], "baz.c:34: warning: `magic' defined but not used\n")
            self.failUnlessEqual(lines[1], "foo.c:100: warning: `xyzzy' defined but not used\n")

        d.addCallback(_checkResult)
        return d

class TreeSize(StepTester, unittest.TestCase):
    def testTreeSize(self):
        self.slavebase = "TreeSize.testTreeSize.slave"
        self.masterbase = "TreeSize.testTreeSize.master"

        sb = self.makeSlaveBuilder()
        step = self.makeStep(shell.TreeSize)
        d = self.runStep(step)
        def _check(results):
            self.failUnlessEqual(results, SUCCESS)
            kib = step.getProperty("tree-size-KiB")
            self.failUnless(isinstance(kib, int))
            self.failUnless(kib < 100) # should be empty, I get '4'
            s = step.step_status
            self.failUnlessEqual(" ".join(s.getText()),
                                 "treesize %d KiB" % kib)
        d.addCallback(_check)
        return d

class FakeCommand:
    def __init__(self, rc):
        self.rc = rc

class PerlModuleTest(StepTester, unittest.TestCase):
    def testAllTestsPassed(self):
        self.masterbase = "PMT.testAllTestsPassed"
        step = self.makeStep(shell.PerlModuleTest)
        output = \
"""ok 1
ok 2
All tests successful
Files=1, Tests=123, other stuff
"""
        log = step.addLog("stdio")
        log.addStdout(output)
        log.finish()
        rc = step.evaluateCommand(FakeCommand(rc=241))
        self.failUnlessEqual(rc, SUCCESS)
        ss = step.step_status
        self.failUnlessEqual(ss.getStatistic('tests-failed'), 0)
        self.failUnlessEqual(ss.getStatistic('tests-total'), 123)
        self.failUnlessEqual(ss.getStatistic('tests-passed'), 123)

    def testFailures_OldTestHarness(self):
        self.masterbase = "PMT.testFailures_OldTestHarness"
        step = self.makeStep(shell.PerlModuleTest)
        output = \
"""
ok 1
ok 2
3/7 subtests failed
"""
        log = step.addLog("stdio")
        log.addStdout(output)
        log.finish()
        rc = step.evaluateCommand(FakeCommand(rc = 123))
        self.failUnlessEqual(rc, FAILURE)
        ss = step.step_status
        self.failUnlessEqual(ss.getStatistic('tests-failed'), 3)
        self.failUnlessEqual(ss.getStatistic('tests-total'), 7)
        self.failUnlessEqual(ss.getStatistic('tests-passed'), 4)

    def testFailures_UnparseableStdio(self):
        self.masterbase = "PMT.testFailures_UnparseableStdio"
        step = self.makeStep(shell.PerlModuleTest)
        output = \
"""
just some random stuff, you know
"""
        log = step.addLog("stdio")
        log.addStdout(output)
        log.finish()
        rc = step.evaluateCommand(FakeCommand(rc = 243))
        self.failUnlessEqual(rc, 243)
        ss = step.step_status
        self.failUnlessEqual(ss.getStatistic('tests-failed'), None)
        self.failUnlessEqual(ss.getStatistic('tests-total'), None)
        self.failUnlessEqual(ss.getStatistic('tests-passed'), None)

    def testFailures_NewTestHarness(self):
        self.masterbase = "PMT.testFailures_NewTestHarness"
        step = self.makeStep(shell.PerlModuleTest)
        output = \
"""
# Looks like you failed 15 tests of 18.
tests/services.......................... Failed 265/30904 subtests
        (less 16 skipped subtests: 30623 okay)
tests/simple_query_backend..............ok
tests/simple_query_middleware...........ok
tests/soap_globalcollect................ok
tests/three_d_me........................ok
tests/three_d_me_callback...............ok
tests/transaction_create................ok
tests/unique_txid.......................ok

Test Summary Report
-------------------
tests/000policies                   (Wstat: 5632 Tests: 9078 Failed: 22)
  Failed tests:  2409, 2896-2897, 2900-2901, 2940-2941, 2944-2945
                2961-2962, 2965-2966, 2969-2970, 2997-2998
                3262, 3281-3282, 3288-3289
  Non-zero exit status: 22
tests/services                      (Wstat: 0 Tests: 30904 Failed: 265)
  Failed tests:  14, 16-21, 64-69, 71-96, 98, 30157, 30159
                30310, 30316, 30439-30543, 30564, 30566-30577
                30602, 30604-30607, 30609-30612, 30655
                30657-30668, 30675, 30697-30716, 30718-30720
                30722-30736, 30773-30774, 30776-30777, 30786
                30791, 30795, 30797, 30801, 30822-30827
                30830-30831, 30848-30855, 30858-30859, 30888-30899
                30901, 30903-30904
Files=68, Tests=264809, 1944 wallclock secs (17.59 usr  0.63 sys + 470.04 cusr 131.40 csys = 619.66 CPU)
Result: FAIL
"""
        log = step.addLog("stdio")
        log.addStdout(output)
        log.finish()
        rc = step.evaluateCommand(FakeCommand(rc=87))
        self.failUnlessEqual(rc, FAILURE)
        ss = step.step_status
        self.failUnlessEqual(ss.getStatistic('tests-failed'), 287)
        self.failUnlessEqual(ss.getStatistic('tests-total'), 264809)
        self.failUnlessEqual(ss.getStatistic('tests-passed'), 264522)

class MasterShellCommand(StepTester, unittest.TestCase):
    def testMasterShellCommand(self):
        self.slavebase = "testMasterShellCommand.slave"
        self.masterbase = "testMasterShellCommand.master"
        sb = self.makeSlaveBuilder()
        step = self.makeStep(master.MasterShellCommand, command=['echo',
                                   WithProperties("hi build-%(other)s.tar.gz")])
        step.build.setProperty("other", "foo", "test")

        # we can't invoke runStep until the reactor is started .. hence this
        # little dance
        d = defer.Deferred()
        def _dotest(_):
            return self.runStep(step)
        d.addCallback(_dotest)

        def _check(results):
            self.failUnlessEqual(results, SUCCESS)
            logtxt = step.getLog("stdio").getText()
            self.failUnlessEqual(logtxt.strip(), "hi build-foo.tar.gz")
        d.addCallback(_check)
        reactor.callLater(0, d.callback, None)
        return d

    def testMasterShellCommand_badexit(self):
        self.slavebase = "testMasterShellCommand_badexit.slave"
        self.masterbase = "testMasterShellCommand_badexit.master"
        sb = self.makeSlaveBuilder()
        step = self.makeStep(master.MasterShellCommand, command="exit 1")

        # we can't invoke runStep until the reactor is started .. hence this
        # little dance
        d = defer.Deferred()
        def _dotest(_):
            return self.runStep(step)
        d.addCallback(_dotest)

        def _check(results):
            self.failUnlessEqual(results, FAILURE)
        d.addCallback(_check)
        reactor.callLater(0, d.callback, None)
        return d

class SuccessStep(buildstep.BuildStep):
    def start(self):
        self.finished(buildstep.SUCCESS)

class ConditionalStepTest(StepTester, unittest.TestCase):
    def testNotSkipped(self):
        self.slavebase = "testNotSkipped.slave"
        self.masterbase = "testNotSkipped.master"
        sb = self.makeSlaveBuilder()
        step = self.makeStep(SuccessStep)
        d = self.runStep(step)
        def _checkResults(results):
            self.failUnlessEqual(SUCCESS, results)
        d.addCallback(_checkResults)
        return d

    def testSkipped(self):
        self.slavebase = "testSkipped.slave"
        self.masterbase = "testSkipped.master"
        sb = self.makeSlaveBuilder()
        step = self.makeStep(SuccessStep, doStepIf=False)
        d = self.runStep(step)
        def _checkResults(results):
            self.failUnlessEqual(SKIPPED, results)
        d.addCallback(_checkResults)
        return d

    def testNotSkippedFunc(self):
        self.slavebase = "testNotSkippedFunc.slave"
        self.masterbase = "testNotSkippedFunc.master"
        sb = self.makeSlaveBuilder()
        step = self.makeStep(SuccessStep, doStepIf=lambda s: True)
        d = self.runStep(step)
        def _checkResults(results):
            self.failUnlessEqual(SUCCESS, results)
        d.addCallback(_checkResults)
        return d

    def testSkippedFunc(self):
        self.slavebase = "testSkippedFunc.slave"
        self.masterbase = "testSkippedFunc.master"
        sb = self.makeSlaveBuilder()
        step = self.makeStep(SuccessStep, doStepIf=lambda s: False)
        d = self.runStep(step)
        def _checkResults(results):
            self.failUnlessEqual(SKIPPED, results)
        d.addCallback(_checkResults)
        return d
