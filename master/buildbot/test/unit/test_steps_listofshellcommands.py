from twisted.trial import unittest

from buildbot.steps import listofshellcommands
from buildbot.status.results import SUCCESS
from buildbot.status.results import WARNINGS
from buildbot.status.results import FAILURE
from buildbot.status.results import EXCEPTION
from buildbot.test.util import config as configmixin
from buildbot.test.util import steps
from buildbot.process.properties import WithProperties
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.fake.remotecommand import Expect


class TestOneShellCommand(steps.BuildStepMixin, unittest.TestCase, configmixin.ConfigErrorsMixin):
    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def testShellArgInput(self):
        self.assertRaisesConfigError(
            "the 'cmd' parameter of ShellArg must not be None",
            lambda: listofshellcommands.ShellArg(cmd=None))
        for invalidlog in ["stdio(a)", "s/b"]:
            self.assertRaisesConfigError(
                "%s is an invalid logfile, "
                "it must not contain any of ['/', '(', ')']" % (invalidlog,),
                lambda: listofshellcommands.ShellArg(cmd="make p", logfile=invalidlog))

    def testPropRendering(self):
        arg1 = listofshellcommands.ShellArg(cmd=WithProperties('make %s', 'project'),
                                            logfile=WithProperties('make %s', 'project'))
        self.setupStep(
            listofshellcommands.ListOfShellCommands(commands=[arg1],
                                                    workdir='build'))
        self.properties.setProperty("project", "BUILDBOT-TEST", "TEST")
        self.expectCommands(ExpectShell(workdir='build', command='make BUILDBOT-TEST',
                                        usePTY="slave-config")
                            + 0 + Expect.log('stdio make BUILDBOT-TEST'))
        self.expectOutcome(result=SUCCESS, status_text=["'make", "BUILDBOT-TEST'"])
        return self.runStep()

    def testSanityChecksAreDoneInRuntime(self):
        arg1 = listofshellcommands.ShellArg(cmd=WithProperties('make %s', 'project'),
                                            logfile=WithProperties('stdio(make %s)', 'project'))
        self.setupStep(
            listofshellcommands.ListOfShellCommands(commands=[arg1],
                                                    workdir='build'))
        self.properties.setProperty("project", "BUILDBOT-TEST", "TEST")
        self.expectOutcome(result=EXCEPTION, status_text=['stdio(make BUILDBOT-TEST)',
                                                          'invalid', 'logfile'])
        return self.runStep()

    def createBuggyClass(self, commandsToSet):
        class DynamicRun(listofshellcommands.ListOfShellCommands):
            def run(self):
                self.setCommands(commandsToSet)
                return self.runAllCmds()
        return DynamicRun

    def testSanityChecksAreDoneInRuntimeWithDynamicCmd(self):
        c1 = self.createBuggyClass(None)
        self.setupStep(c1())
        self.expectOutcome(result=EXCEPTION,
                           status_text=['commands == None'])
        return self.runStep()

    def testSanityChecksAreDoneInRuntimeWithDynamicCmd2(self):
        c1 = self.createBuggyClass(["one command"])
        self.setupStep(c1())
        self.expectOutcome(result=EXCEPTION,
                           status_text=['one command', 'not', 'ShellArg'])
        return self.runStep()

    def testMultipleCommandsAreRun(self):
        arg1 = listofshellcommands.ShellArg(cmd='make p1')
        arg2 = listofshellcommands.ShellArg(cmd='deploy p1', logfile='deploy')
        self.setupStep(
            listofshellcommands.ListOfShellCommands(commands=[arg1, arg2],
                                                    workdir='build'))
        self.expectCommands(ExpectShell(workdir='build', command='make p1',
                                        usePTY="slave-config") + 0,
                            ExpectShell(workdir='build', command='deploy p1',
                                        usePTY="slave-config") + 0 +
                            Expect.log('stdio deploy p1'))
        self.expectOutcome(result=SUCCESS, status_text=["'deploy", "p1'"])
        return self.runStep()

    def testSkipWorks(self):
        arg1 = listofshellcommands.ShellArg(cmd='make p1')
        arg2 = listofshellcommands.ShellArg(cmd='')
        arg3 = listofshellcommands.ShellArg(cmd='deploy p1')
        self.setupStep(
            listofshellcommands.ListOfShellCommands(commands=[arg1, arg2, arg3],
                                                    workdir='build'))
        self.expectCommands(ExpectShell(workdir='build', command='make p1',
                                        usePTY="slave-config") + 0,
                            ExpectShell(workdir='build', command='deploy p1',
                                        usePTY="slave-config") + 0)
        self.expectOutcome(result=SUCCESS, status_text=["'deploy", "p1'"])
        return self.runStep()

    def testWarningWins(self):
        class SetWarnings(listofshellcommands.ListOfShellCommands):
            def evaluateCommand(self, cmd):
                if cmd.didFail():
                    return WARNINGS
                return SUCCESS
        arg1 = listofshellcommands.ShellArg(cmd='make p1')
        arg2 = listofshellcommands.ShellArg(cmd='deploy p1')
        self.setupStep(
            SetWarnings(commands=[arg1, arg2],
                        workdir='build'))
        self.expectCommands(ExpectShell(workdir='build', command='make p1',
                                        usePTY="slave-config") + 1,
                            ExpectShell(workdir='build', command='deploy p1',
                                        usePTY="slave-config") + 0)
        self.expectOutcome(result=WARNINGS, status_text=["'deploy", "p1'"])
        return self.runStep()

    def testStopsOnFailure(self):
        arg1 = listofshellcommands.ShellArg(cmd='make p1')
        arg2 = listofshellcommands.ShellArg(cmd='deploy p1')

        self.setupStep(
            listofshellcommands.ListOfShellCommands(commands=[arg1, arg2],
                                                    workdir='build'))
        self.expectCommands(ExpectShell(workdir='build', command='make p1',
                                        usePTY="slave-config") + 1)
        self.expectOutcome(result=FAILURE, status_text=["'make", "p1'"])
        return self.runStep()


