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
from buildbot.status.results import SKIPPED, SUCCESS, WARNINGS, FAILURE
from buildbot.status.results import EXCEPTION
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

class TreeSize(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_run_success(self):
        self.setupStep(shell.TreeSize())
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command=['du', '-s', '-k', '.'])
            + ExpectShell.log('stdio', stdout='9292    .\n')
            + 0
        )
        self.expectOutcome(result=SUCCESS,
                status_text=["treesize", "9292 KiB"])
        self.expectProperty('tree-size-KiB', 9292)
        return self.runStep()

    def test_run_misparsed(self):
        self.setupStep(shell.TreeSize())
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command=['du', '-s', '-k', '.'])
            + ExpectShell.log('stdio', stdio='abcdef\n')
            + 0
        )
        self.expectOutcome(result=WARNINGS,
                status_text=["treesize", "unknown"])
        return self.runStep()

    def test_run_failed(self):
        self.setupStep(shell.TreeSize())
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command=['du', '-s', '-k', '.'])
            + ExpectShell.log('stdio', stderr='abcdef\n')
            + 1
        )
        self.expectOutcome(result=FAILURE,
                status_text=["treesize", "unknown"])
        return self.runStep()

class SetProperty(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_constructor_conflict(self):
        self.assertRaises(AssertionError, lambda :
                shell.SetProperty(property='foo', extract_fn=lambda : None))

    def test_run_property(self):
        self.setupStep(shell.SetProperty(property="res", command="cmd"))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command="cmd")
            + ExpectShell.log('stdio', stdout='\n\nabcdef\n')
            + 0
        )
        self.expectOutcome(result=SUCCESS,
                status_text=["set props:", "res"])
        self.expectProperty("res", "abcdef") # note: stripped
        self.expectLogfile('property changes', r"res: 'abcdef'")
        return self.runStep()

    def test_run_property_no_strip(self):
        self.setupStep(shell.SetProperty(property="res", command="cmd",
                                         strip=False))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command="cmd")
            + ExpectShell.log('stdio', stdout='\n\nabcdef\n')
            + 0
        )
        self.expectOutcome(result=SUCCESS,
                status_text=["set props:", "res"])
        self.expectProperty("res", "\n\nabcdef\n")
        self.expectLogfile('property changes', r"res: '\n\nabcdef\n'")
        return self.runStep()

    def test_run_failure(self):
        self.setupStep(shell.SetProperty(property="res", command="blarg"))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command="blarg")
            + ExpectShell.log('stdio', stderr='cannot blarg: File not found')
            + 1
        )
        self.expectOutcome(result=FAILURE,
                status_text=["'blarg'", "failed"])
        self.expectNoProperty("res")
        return self.runStep()

    def test_run_extract_fn(self):
        def extract_fn(rc, stdout, stderr):
            self.assertEqual((rc, stdout, stderr), (0, 'startend', 'STARTEND'))
            return dict(a=1, b=2)
        self.setupStep(shell.SetProperty(extract_fn=extract_fn, command="cmd"))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command="cmd")
            + ExpectShell.log('stdio', stdout='start', stderr='START')
            + ExpectShell.log('stdio', stdout='end')
            + ExpectShell.log('stdio', stderr='END')
            + 0
        )
        self.expectOutcome(result=SUCCESS,
                status_text=["set props:", "a", "b"])
        self.expectLogfile('property changes', 'a: 1\nb: 2')
        self.expectProperty("a", 1)
        self.expectProperty("b", 2)
        return self.runStep()

    def test_run_extract_fn_cmdfail(self):
        def extract_fn(rc, stdout, stderr):
            self.assertEqual((rc, stdout, stderr), (3, '', ''))
            return dict(a=1, b=2)
        self.setupStep(shell.SetProperty(extract_fn=extract_fn, command="cmd"))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command="cmd")
            + 3
        )
        # note that extract_fn *is* called anyway
        self.expectOutcome(result=FAILURE,
                status_text=["set props:", "a", "b"])
        self.expectLogfile('property changes', 'a: 1\nb: 2')
        return self.runStep()

    def test_run_extract_fn_cmdfail_empty(self):
        def extract_fn(rc, stdout, stderr):
            self.assertEqual((rc, stdout, stderr), (3, '', ''))
            return dict()
        self.setupStep(shell.SetProperty(extract_fn=extract_fn, command="cmd"))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command="cmd")
            + 3
        )
        # note that extract_fn *is* called anyway, but returns no properties
        self.expectOutcome(result=FAILURE,
                status_text=["'cmd'", "failed"])
        return self.runStep()

    @compat.usesFlushLoggedErrors
    def test_run_extract_fn_exception(self):
        def extract_fn(rc, stdout, stderr):
            raise RuntimeError("oh noes")
        self.setupStep(shell.SetProperty(extract_fn=extract_fn, command="cmd"))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command="cmd")
            + 0
        )
        # note that extract_fn *is* called anyway, but returns no properties
        self.expectOutcome(result=EXCEPTION,
                status_text=["setproperty", "exception"])
        d = self.runStep()
        d.addCallback(lambda _ :
            self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1))
        return d

class Configure(unittest.TestCase):

    def test_class_attrs(self):
        # nothing too exciting here, but at least make sure the class is present
        step = shell.Configure()
        self.assertEqual(step.command, ['./configure'])
