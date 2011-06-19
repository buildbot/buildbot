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

from twisted.trial import unittest
from buildbot.steps import shell
from buildbot.status.results import SKIPPED, SUCCESS
from buildbot.test.util import steps, compat
from buildbot.test.fake.remotecommand import ExpectShell


class TestShellCommandExeceution(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_doStepIf_False(self):
        self.setupStep(
                shell.ShellCommand(command="echo hello", doStepIf=False))
        self.expectOutcome(result=SKIPPED,
                status_text=["'echo", "hello'", "skipped"])
        return self.runStep()

    def test_constructor_args_strings(self):
        step = shell.ShellCommand(workdir='build', command="echo hello",
                usePTY=False, description="echoing",
                descriptionDone="echoed")
        self.assertEqual(step.description, ['echoing'])
        self.assertEqual(step.descriptionDone, ['echoed'])

    def test_constructor_args_lists(self):
        step = shell.ShellCommand(workdir='build', command="echo hello",
                usePTY=False, description=["echoing"],
                descriptionDone=["echoed"])
        self.assertEqual(step.description, ['echoing'])
        self.assertEqual(step.descriptionDone, ['echoed'])

    def test_constructor_args_kwargs(self):
        # this is an ugly way to define an API, but for now check that
        # the RemoteCommand arguments are properly passed on
        step = shell.ShellCommand(workdir='build', command="echo hello",
                abc=1, xyz=2)
        self.assertEqual(step.remote_kwargs, dict(abc=1, xyz=2,
                                workdir='build', usePTY='slave-config'))

    def test_describe_no_command(self):
        step = shell.ShellCommand(workdir='build')
        self.assertEqual((step.describe(), step.describe(done=True)),
                         (['???'],)*2)

    def test_describe_from_empty_command(self):
        # this is more of a regression test for a potential failure, really
        step = shell.ShellCommand(workdir='build', command=' ')
        self.assertEqual((step.describe(), step.describe(done=True)),
                         (['???'],)*2)

    def test_describe_from_short_command(self):
        step = shell.ShellCommand(workdir='build', command="true")
        self.assertEqual((step.describe(), step.describe(done=True)),
                         (["'true'"],)*2)

    def test_describe_from_short_command_list(self):
        step = shell.ShellCommand(workdir='build', command=["true"])
        self.assertEqual((step.describe(), step.describe(done=True)),
                         (["'true'"],)*2)

    def test_describe_from_med_command(self):
        step = shell.ShellCommand(command="echo hello")
        self.assertEqual((step.describe(), step.describe(done=True)),
                         (["'echo", "hello'"],)*2)

    def test_describe_from_med_command_list(self):
        step = shell.ShellCommand(command=["echo", "hello"])
        self.assertEqual((step.describe(), step.describe(done=True)),
                         (["'echo", "hello'"],)*2)

    def test_describe_from_long_command(self):
        step = shell.ShellCommand(command="this is a long command")
        self.assertEqual((step.describe(), step.describe(done=True)),
                         (["'this", "is", "...'"],)*2)

    def test_describe_from_long_command_list(self):
        step = shell.ShellCommand(command="this is a long command".split())
        self.assertEqual((step.describe(), step.describe(done=True)),
                         (["'this", "is", "...'"],)*2)

    def test_describe_custom(self):
        step = shell.ShellCommand(command="echo hello",
                        description=["echoing"], descriptionDone=["echoed"])
        self.assertEqual((step.describe(), step.describe(done=True)),
                         (['echoing'], ['echoed']))

    @compat.usesFlushLoggedErrors
    def test_describe_fail(self):
        step = shell.ShellCommand(command=object())
        self.assertEqual((step.describe(), step.describe(done=True)),
                         (['???'],)*2)
        # (describe is called twice, so two exceptions)
        self.assertEqual(len(self.flushLoggedErrors(TypeError)), 2)

    def test_run_simple(self):
        self.setupStep(
                shell.ShellCommand(workdir='build', command="echo hello"))
        self.expectCommands(
            ExpectShell(workdir='build', command='echo hello',
                         usePTY="slave-config")
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=["'echo", "hello'"])
        return self.runStep()

    def test_run_env(self):
        self.setupStep(
                shell.ShellCommand(workdir='build', command="echo hello"),
                slave_env=dict(DEF='HERE'))
        self.expectCommands(
            ExpectShell(workdir='build', command='echo hello',
                         usePTY="slave-config",
                         env=dict(DEF='HERE'))
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=["'echo", "hello'"])
        return self.runStep()

    def test_run_env_override(self):
        self.setupStep(
                shell.ShellCommand(workdir='build', env={'ABC':'123'},
                                   command="echo hello"),
                slave_env=dict(ABC='XXX', DEF='HERE'))
        self.expectCommands(
            ExpectShell(workdir='build', command='echo hello',
                         usePTY="slave-config",
                         env=dict(ABC='123', DEF='HERE'))
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=["'echo", "hello'"])
        return self.runStep()

    def test_run_usePTY(self):
        self.setupStep(
                shell.ShellCommand(workdir='build', command="echo hello",
                                   usePTY=False))
        self.expectCommands(
            ExpectShell(workdir='build', command='echo hello',
                         usePTY=False)
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=["'echo", "hello'"])
        return self.runStep()

    def test_run_usePTY_old_slave(self):
        self.setupStep(
                shell.ShellCommand(workdir='build', command="echo hello",
                                   usePTY=True),
                slave_version='1.1')
        self.expectCommands(
            ExpectShell(workdir='build', command='echo hello')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=["'echo", "hello'"])
        return self.runStep()

