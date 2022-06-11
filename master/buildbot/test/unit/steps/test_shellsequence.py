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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process.properties import WithProperties
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.steps import shellsequence
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import ExpectShell
from buildbot.test.steps import TestBuildStepMixin
from buildbot.test.util import config as configmixin
from buildbot.test.util.warnings import assertProducesWarnings
from buildbot.warnings import DeprecatedApiWarning


class DynamicRun(shellsequence.ShellSequence):

    def run(self):
        return self.runShellSequence(self.dynamicCommands)


class TestOneShellCommand(TestBuildStepMixin, configmixin.ConfigErrorsMixin,
                          TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_shell_arg_warn_deprecated_logfile(self):
        with assertProducesWarnings(DeprecatedApiWarning,
                                    message_pattern="logfile is deprecated, use logname"):
            shellsequence.ShellArg(command="command", logfile="logfile")

    def test_shell_arg_error_logfile_and_logname(self):
        with assertProducesWarnings(DeprecatedApiWarning,
                                    message_pattern="logfile is deprecated, use logname"):
            with self.assertRaisesConfigError(
                    "the 'logfile' parameter must not be specified when 'logname' is set"):
                shellsequence.ShellArg(command="command", logname="logname", logfile="logfile")

    def testShellArgInput(self):
        with self.assertRaisesConfigError(
             "the 'command' parameter of ShellArg must not be None"):
            shellsequence.ShellArg(command=None)
        arg1 = shellsequence.ShellArg(command=1)
        with self.assertRaisesConfigError(
                "1 is an invalid command, it must be a string or a list"):
            arg1.validateAttributes()
        arg2 = shellsequence.ShellArg(command=["make", 1])
        with self.assertRaisesConfigError(
                "['make', 1] must only have strings in it"):
            arg2.validateAttributes()

        for goodcmd in ["make p1", ["make", "p1"]]:
            arg = shellsequence.ShellArg(command=goodcmd)
            arg.validateAttributes()

    def testShellArgsAreRendered(self):
        arg1 = shellsequence.ShellArg(command=WithProperties('make %s', 'project'))
        self.setup_step(
            shellsequence.ShellSequence(commands=[arg1],
                                        workdir='build'))
        self.properties.setProperty("project", "BUILDBOT-TEST", "TEST")
        self.expect_commands(ExpectShell(workdir='build', command='make BUILDBOT-TEST').exit(0))
        # TODO: need to factor command-summary stuff into a utility method and
        # use it here
        self.expect_outcome(result=SUCCESS, state_string="'make BUILDBOT-TEST'")
        return self.run_step()

    def createDynamicRun(self, commands):
        DynamicRun.dynamicCommands = commands
        return DynamicRun()

    def testSanityChecksAreDoneInRuntimeWhenDynamicCmdIsNone(self):
        self.setup_step(self.createDynamicRun(None))
        self.expect_outcome(result=EXCEPTION,
                           state_string="finished (exception)")
        return self.run_step()

    def testSanityChecksAreDoneInRuntimeWhenDynamicCmdIsString(self):
        self.setup_step(self.createDynamicRun(["one command"]))
        self.expect_outcome(result=EXCEPTION,
                           state_string='finished (exception)')
        return self.run_step()

    def testSanityChecksAreDoneInRuntimeWhenDynamicCmdIsInvalidShellArg(self):
        self.setup_step(
            self.createDynamicRun([shellsequence.ShellArg(command=1)]))
        self.expect_outcome(result=EXCEPTION,
                           state_string='finished (exception)')
        return self.run_step()

    def testMultipleCommandsAreRun(self):
        arg1 = shellsequence.ShellArg(command='make p1')
        arg2 = shellsequence.ShellArg(command='deploy p1')
        self.setup_step(
            shellsequence.ShellSequence(commands=[arg1, arg2],
                                        workdir='build'))
        self.expect_commands(ExpectShell(workdir='build', command='make p1').exit(0),
                            ExpectShell(workdir='build', command='deploy p1').exit(0))
        self.expect_outcome(result=SUCCESS, state_string="'deploy p1'")
        return self.run_step()

    def testSkipWorks(self):
        arg1 = shellsequence.ShellArg(command='make p1')
        arg2 = shellsequence.ShellArg(command='')
        arg3 = shellsequence.ShellArg(command='deploy p1')
        self.setup_step(
            shellsequence.ShellSequence(commands=[arg1, arg2, arg3],
                                        workdir='build'))
        self.expect_commands(ExpectShell(workdir='build', command='make p1').exit(0),
                            ExpectShell(workdir='build', command='deploy p1').exit(0))
        self.expect_outcome(result=SUCCESS, state_string="'deploy p1'")
        return self.run_step()

    def testWarningWins(self):
        arg1 = shellsequence.ShellArg(command='make p1',
                                      warnOnFailure=True,
                                      flunkOnFailure=False)
        arg2 = shellsequence.ShellArg(command='deploy p1')
        self.setup_step(
            shellsequence.ShellSequence(commands=[arg1, arg2],
                                        workdir='build'))
        self.expect_commands(ExpectShell(workdir='build', command='make p1').exit(1),
                            ExpectShell(workdir='build', command='deploy p1').exit(0))
        self.expect_outcome(result=WARNINGS, state_string="'deploy p1' (warnings)")
        return self.run_step()

    def testSequenceStopsOnHaltOnFailure(self):
        arg1 = shellsequence.ShellArg(command='make p1', haltOnFailure=True)
        arg2 = shellsequence.ShellArg(command='deploy p1')

        self.setup_step(
            shellsequence.ShellSequence(commands=[arg1, arg2],
                                        workdir='build'))
        self.expect_commands(ExpectShell(workdir='build', command='make p1').exit(1))
        self.expect_outcome(result=FAILURE, state_string="'make p1' (failure)")
        return self.run_step()

    @defer.inlineCallbacks
    def testShellArgsAreRenderedAnewAtEachBuild(self):
        """Unit test to ensure that ShellArg instances are properly re-rendered.

        This unit test makes sure that ShellArg instances are rendered anew at
        each new build.
        """
        arg = shellsequence.ShellArg(command=WithProperties('make %s', 'project'))
        step = shellsequence.ShellSequence(commands=[arg], workdir='build')

        # First "build"
        self.setup_step(step)
        self.properties.setProperty("project", "BUILDBOT-TEST-1", "TEST")
        self.expect_commands(ExpectShell(workdir='build', command='make BUILDBOT-TEST-1').exit(0))
        self.expect_outcome(result=SUCCESS,
                           state_string="'make BUILDBOT-TEST-1'")
        yield self.run_step()

        # Second "build"
        self.setup_step(step)
        self.properties.setProperty("project", "BUILDBOT-TEST-2", "TEST")
        self.expect_commands(ExpectShell(workdir='build', command='make BUILDBOT-TEST-2').exit(0))
        self.expect_outcome(result=SUCCESS,
                           state_string="'make BUILDBOT-TEST-2'")

        yield self.run_step()
