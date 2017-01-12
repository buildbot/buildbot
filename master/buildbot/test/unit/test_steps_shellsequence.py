# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

from __future__ import absolute_import
from __future__ import print_function

from twisted.trial import unittest

from buildbot.process.properties import WithProperties
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.steps import shellsequence
from buildbot.test.fake.remotecommand import Expect
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.util import config as configmixin
from buildbot.test.util import steps


class DynamicRun(shellsequence.ShellSequence):

    def run(self):
        return self.runShellSequence(self.dynamicCommands)


class TestOneShellCommand(steps.BuildStepMixin, unittest.TestCase, configmixin.ConfigErrorsMixin):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def testShellArgInput(self):
        self.assertRaisesConfigError(
            "the 'command' parameter of ShellArg must not be None",
            lambda: shellsequence.ShellArg(command=None))
        arg1 = shellsequence.ShellArg(command=1)
        self.assertRaisesConfigError(
            "1 is an invalid command, it must be a string or a list",
            lambda: arg1.validateAttributes())
        arg2 = shellsequence.ShellArg(command=["make", 1])
        self.assertRaisesConfigError(
            "['make', 1] must only have strings in it",
            lambda: arg2.validateAttributes())

        for goodcmd in ["make p1", ["make", "p1"]]:
            arg = shellsequence.ShellArg(command=goodcmd)
            arg.validateAttributes()

    def testShellArgsAreRendered(self):
        arg1 = shellsequence.ShellArg(command=WithProperties('make %s', 'project'),
                                      logfile=WithProperties('make %s', 'project'))
        self.setupStep(
            shellsequence.ShellSequence(commands=[arg1],
                                        workdir='build'))
        self.properties.setProperty("project", "BUILDBOT-TEST", "TEST")
        self.expectCommands(ExpectShell(workdir='build', command='make BUILDBOT-TEST')
                            + 0 + Expect.log('stdio make BUILDBOT-TEST'))
        # TODO: need to factor command-summary stuff into a utility method and
        # use it here
        self.expectOutcome(result=SUCCESS, state_string="'make BUILDBOT-TEST'")
        return self.runStep()

    def createDynamicRun(self, commands):
        DynamicRun.dynamicCommands = commands
        return DynamicRun()

    def testSanityChecksAreDoneInRuntimeWhenDynamicCmdIsNone(self):
        self.setupStep(self.createDynamicRun(None))
        self.expectOutcome(result=EXCEPTION,
                           state_string="finished (exception)")
        return self.runStep()

    def testSanityChecksAreDoneInRuntimeWhenDynamicCmdIsString(self):
        self.setupStep(self.createDynamicRun(["one command"]))
        self.expectOutcome(result=EXCEPTION,
                           state_string='finished (exception)')
        return self.runStep()

    def testSanityChecksAreDoneInRuntimeWhenDynamicCmdIsInvalidShellArg(self):
        self.setupStep(
            self.createDynamicRun([shellsequence.ShellArg(command=1)]))
        self.expectOutcome(result=EXCEPTION,
                           state_string='finished (exception)')
        return self.runStep()

    def testMultipleCommandsAreRun(self):
        arg1 = shellsequence.ShellArg(command='make p1')
        arg2 = shellsequence.ShellArg(command='deploy p1', logfile='deploy')
        self.setupStep(
            shellsequence.ShellSequence(commands=[arg1, arg2],
                                        workdir='build'))
        self.expectCommands(ExpectShell(workdir='build', command='make p1') + 0,
                            ExpectShell(workdir='build', command='deploy p1') + 0 +
                            Expect.log('stdio deploy p1'))
        self.expectOutcome(result=SUCCESS, state_string="'deploy p1'")
        return self.runStep()

    def testSkipWorks(self):
        arg1 = shellsequence.ShellArg(command='make p1')
        arg2 = shellsequence.ShellArg(command='')
        arg3 = shellsequence.ShellArg(command='deploy p1')
        self.setupStep(
            shellsequence.ShellSequence(commands=[arg1, arg2, arg3],
                                        workdir='build'))
        self.expectCommands(ExpectShell(workdir='build', command='make p1') + 0,
                            ExpectShell(workdir='build', command='deploy p1') + 0)
        self.expectOutcome(result=SUCCESS, state_string="'deploy p1'")
        return self.runStep()

    def testWarningWins(self):
        arg1 = shellsequence.ShellArg(command='make p1',
                                      warnOnFailure=True,
                                      flunkOnFailure=False)
        arg2 = shellsequence.ShellArg(command='deploy p1')
        self.setupStep(
            shellsequence.ShellSequence(commands=[arg1, arg2],
                                        workdir='build'))
        self.expectCommands(ExpectShell(workdir='build', command='make p1') + 1,
                            ExpectShell(workdir='build', command='deploy p1') + 0)
        self.expectOutcome(result=WARNINGS, state_string="'deploy p1'")
        return self.runStep()

    def testSequenceStopsOnHaltOnFailure(self):
        arg1 = shellsequence.ShellArg(command='make p1', haltOnFailure=True)
        arg2 = shellsequence.ShellArg(command='deploy p1')

        self.setupStep(
            shellsequence.ShellSequence(commands=[arg1, arg2],
                                        workdir='build'))
        self.expectCommands(ExpectShell(workdir='build', command='make p1') + 1)
        self.expectOutcome(result=FAILURE, state_string="'make p1'")
        return self.runStep()
