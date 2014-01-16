from twisted.trial import unittest

from buildbot.steps import shellsequence
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
            lambda: shellsequence.ShellArg(cmd=None))
        arg1 = shellsequence.ShellArg(cmd=1)
        self.assertRaisesConfigError(
            "1 is an invalid command, it must be a string or a list",
            lambda: arg1.validateAttributes())
        arg2 = shellsequence.ShellArg(cmd=["make", 1])
        self.assertRaisesConfigError(
            "['make', 1] must only have strings in it",
            lambda: arg2.validateAttributes())

        for goodcmd in ["make p1", ["make", "p1"]]:
            arg = shellsequence.ShellArg(cmd=goodcmd)
            arg.validateAttributes()

    def testShellArgsAreRendered(self):
        arg1 = shellsequence.ShellArg(cmd=WithProperties('make %s', 'project'),
                                      logfile=WithProperties('make %s', 'project'))
        self.setupStep(
            shellsequence.ShellSequence(commands=[arg1],
                                        workdir='build'))
        self.properties.setProperty("project", "BUILDBOT-TEST", "TEST")
        self.expectCommands(ExpectShell(workdir='build', command='make BUILDBOT-TEST',
                                        usePTY="slave-config")
                            + 0 + Expect.log('stdio make BUILDBOT-TEST'))
        self.expectOutcome(result=SUCCESS, status_text=["'make", "BUILDBOT-TEST'"])
        return self.runStep()

    def createBuggyClass(self, commandsToSet):
        class DynamicRun(shellsequence.ShellSequence):
            def run(self):
                self.setCommands(commandsToSet)
                return self.runAllCmds()
        return DynamicRun

    def testSanityChecksAreDoneInRuntimeWhenDynamicCmdIsNone(self):
        c1 = self.createBuggyClass(None)
        self.setupStep(c1())
        self.expectOutcome(result=EXCEPTION,
                           status_text=['commands == None'])
        return self.runStep()

    def testSanityChecksAreDoneInRuntimeWhenDynamicCmdIsString(self):
        c1 = self.createBuggyClass(["one command"])
        self.setupStep(c1())
        self.expectOutcome(result=EXCEPTION,
                           status_text=['one command', 'not', 'ShellArg'])
        return self.runStep()

    def testSanityChecksAreDoneInRuntimeWhenDynamicCmdIsInvalidShellArg(self):
        c1 = self.createBuggyClass([shellsequence.ShellArg(cmd=1)])
        self.setupStep(c1())
        self.expectOutcome(result=EXCEPTION,
                           status_text=[1, 'invalid', 'params'])
        return self.runStep()

    def testMultipleCommandsAreRun(self):
        arg1 = shellsequence.ShellArg(cmd='make p1')
        arg2 = shellsequence.ShellArg(cmd='deploy p1', logfile='deploy')
        self.setupStep(
            shellsequence.ShellSequence(commands=[arg1, arg2],
                                        workdir='build'))
        self.expectCommands(ExpectShell(workdir='build', command='make p1',
                                        usePTY="slave-config") + 0,
                            ExpectShell(workdir='build', command='deploy p1',
                                        usePTY="slave-config") + 0 +
                            Expect.log('stdio deploy p1'))
        self.expectOutcome(result=SUCCESS, status_text=["'deploy", "p1'"])
        return self.runStep()

    def testSkipWorks(self):
        arg1 = shellsequence.ShellArg(cmd='make p1')
        arg2 = shellsequence.ShellArg(cmd='')
        arg3 = shellsequence.ShellArg(cmd='deploy p1')
        self.setupStep(
            shellsequence.ShellSequence(commands=[arg1, arg2, arg3],
                                        workdir='build'))
        self.expectCommands(ExpectShell(workdir='build', command='make p1',
                                        usePTY="slave-config") + 0,
                            ExpectShell(workdir='build', command='deploy p1',
                                        usePTY="slave-config") + 0)
        self.expectOutcome(result=SUCCESS, status_text=["'deploy", "p1'"])
        return self.runStep()

    def testWarningWins(self):
        arg1 = shellsequence.ShellArg(cmd='make p1',
                                      warnOnFailure=True,
                                      flunkOnFailure=False)
        arg2 = shellsequence.ShellArg(cmd='deploy p1')
        self.setupStep(
            shellsequence.ShellSequence(commands=[arg1, arg2],
                                        workdir='build'))
        self.expectCommands(ExpectShell(workdir='build', command='make p1',
                                        usePTY="slave-config") + 1,
                            ExpectShell(workdir='build', command='deploy p1',
                                        usePTY="slave-config") + 0)
        self.expectOutcome(result=WARNINGS, status_text=["'deploy", "p1'"])
        return self.runStep()

    def testSequenceStopsOnHaltOnFailure(self):
        arg1 = shellsequence.ShellArg(cmd='make p1', haltOnFailure=True)
        arg2 = shellsequence.ShellArg(cmd='deploy p1')

        self.setupStep(
            shellsequence.ShellSequence(commands=[arg1, arg2],
                                        workdir='build'))
        self.expectCommands(ExpectShell(workdir='build', command='make p1',
                                        usePTY="slave-config") + 1)
        self.expectOutcome(result=FAILURE, status_text=["'make", "p1'"])
        return self.runStep()
