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

import re
import textwrap
from twisted.trial import unittest
from buildbot.steps import shell
from buildbot.status.results import SKIPPED, SUCCESS, WARNINGS, FAILURE
from buildbot.status.results import EXCEPTION
from buildbot.test.util import steps, compat
from buildbot.test.fake.remotecommand import ExpectShell, Expect
from buildbot.test.fake.remotecommand import ExpectRemoteRef


class TestShellCommandExecution(steps.BuildStepMixin, unittest.TestCase):

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
                status_text=["property 'res' set"])
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
                status_text=["property 'res' set"])
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
                status_text=["2 properties set"])
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
                status_text=["2 properties set"])
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

class WarningCountingShellCommand(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_no_warnings(self):
        self.setupStep(shell.WarningCountingShellCommand(workdir='w',
                                    command=['make']))
        self.expectCommands(
            ExpectShell(workdir='w', usePTY='slave-config',
                        command=["make"])
            + ExpectShell.log('stdio', stdout='blarg success!')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=["'make'"])
        self.expectProperty("warnings-count", 0)
        return self.runStep()

    def test_default_pattern(self):
        self.setupStep(shell.WarningCountingShellCommand(command=['make']))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command=["make"])
            + ExpectShell.log('stdio',
                    stdout='normal: foo\nwarning: blarg!\nalso normal')
            + 0
        )
        self.expectOutcome(result=WARNINGS, status_text=["'make'", "warnings"])
        self.expectProperty("warnings-count", 1)
        self.expectLogfile("warnings (1)", "warning: blarg!\n")
        return self.runStep()

    def test_custom_pattern(self):
        self.setupStep(shell.WarningCountingShellCommand(command=['make'],
                            warningPattern=r"scary:.*"))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command=["make"])
            + ExpectShell.log('stdio',
                stdout='scary: foo\nwarning: bar\nscary: bar')
            + 0
        )
        self.expectOutcome(result=WARNINGS, status_text=["'make'", "warnings"])
        self.expectProperty("warnings-count", 2)
        self.expectLogfile("warnings (2)", "scary: foo\nscary: bar\n")
        return self.runStep()

    def test_maxWarnCount(self):
        self.setupStep(shell.WarningCountingShellCommand(command=['make'],
            maxWarnCount=9))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command=["make"])
            + ExpectShell.log('stdio', stdout='warning: noo!\n' * 10)
            + 0
        )
        self.expectOutcome(result=FAILURE, status_text=["'make'", "failed"])
        self.expectProperty("warnings-count", 10)
        return self.runStep()

    def test_fail_with_warnings(self):
        self.setupStep(shell.WarningCountingShellCommand(command=['make']))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command=["make"])
            + ExpectShell.log('stdio', stdout='warning: I might fail')
            + 3
        )
        self.expectOutcome(result=FAILURE, status_text=["'make'", "failed"])
        self.expectProperty("warnings-count", 1)
        self.expectLogfile("warnings (1)", "warning: I might fail\n")
        return self.runStep()

    def do_test_suppressions(self, step, supps_file='', stdout='',
                                exp_warning_count=0, exp_warning_log='',
                                exp_exception=False):
        self.setupStep(step)

        # Invoke the expected callbacks for the suppression file upload.  Note
        # that this assumes all of the remote_* are synchronous, but can be
        # easily adapted to suit if that changes (using deferredGenerator)
        def upload_behavior(command):
            writer = command.args['writer']
            writer.remote_write(supps_file)
            writer.remote_close()

        self.expectCommands(
            # step will first get the remote suppressions file
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                            slavesrc='supps', workdir='wkdir',
                            writer=ExpectRemoteRef(shell.StringFileWriter)))
            + Expect.behavior(upload_behavior),

            # and then run the command
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command=["make"])
            + ExpectShell.log('stdio', stdout=stdout)
            + 0
        )
        if exp_exception:
            self.expectOutcome(result=EXCEPTION,
                                status_text=["shell", "exception"])
        else:
            if exp_warning_count != 0:
                self.expectOutcome(result=WARNINGS,
                                status_text=["'make'", "warnings"])
                self.expectLogfile("warnings (%d)" % exp_warning_count,
                                exp_warning_log)
            else:
                self.expectOutcome(result=SUCCESS,
                                status_text=["'make'"])
            self.expectProperty("warnings-count", exp_warning_count)
        return self.runStep()

    def test_suppressions(self):
        step = shell.WarningCountingShellCommand(command=['make'],
                                suppressionFile='supps')
        supps_file = textwrap.dedent("""\
            # example suppressions file

            amar.c : .*unused variable.*
            holding.c : .*invalid access to non-static.*
            """).strip()
        stdout = textwrap.dedent("""\
            /bin/sh ../libtool --tag=CC  --silent --mode=link gcc blah
            /bin/sh ../libtool --tag=CC  --silent --mode=link gcc blah
            amar.c: In function 'write_record':
            amar.c:164: warning: unused variable 'x'
            amar.c:164: warning: this should show up
            /bin/sh ../libtool --tag=CC  --silent --mode=link gcc blah
            /bin/sh ../libtool --tag=CC  --silent --mode=link gcc blah
            holding.c: In function 'holding_thing':
            holding.c:984: warning: invalid access to non-static 'y'
            """)
        exp_warning_log = textwrap.dedent("""\
            amar.c:164: warning: this should show up
        """)
        return self.do_test_suppressions(step, supps_file, stdout, 1,
                                         exp_warning_log)

    def test_suppressions_directories(self):
        def warningExtractor(step, line, match):
            return line.split(':', 2)
        step = shell.WarningCountingShellCommand(command=['make'],
                                suppressionFile='supps',
                                warningExtractor=warningExtractor)
        supps_file = textwrap.dedent("""\
            # these should be suppressed:
            amar-src/amar.c : XXX
            .*/server-src/.* : AAA
            # these should not, as the dirs do not match:
            amar.c : YYY
            server-src.* : BBB
            """).strip()
        # note that this uses the unicode smart-quotes that gcc loves so much
        stdout = textwrap.dedent(u"""\
            make: Entering directory \u2019amar-src\u2019
            amar.c:164: warning: XXX
            amar.c:165: warning: YYY
            make: Leaving directory 'amar-src'
            make: Entering directory "subdir"
            make: Entering directory 'server-src'
            make: Entering directory `one-more-dir`
            holding.c:999: warning: BBB
            holding.c:1000: warning: AAA
            """)
        exp_warning_log = textwrap.dedent("""\
            amar.c:165: warning: YYY
            holding.c:999: warning: BBB
        """)
        return self.do_test_suppressions(step, supps_file, stdout, 2,
                                         exp_warning_log)

    def test_suppressions_directories_custom(self):
        def warningExtractor(step, line, match):
            return line.split(':', 2)
        step = shell.WarningCountingShellCommand(command=['make'],
                                suppressionFile='supps',
                                warningExtractor=warningExtractor,
                                directoryEnterPattern="^IN: (.*)",
                                directoryLeavePattern="^OUT:")
        supps_file = "dir1/dir2/abc.c : .*"
        stdout = textwrap.dedent(u"""\
            IN: dir1
            IN: decoy
            OUT: decoy
            IN: dir2
            abc.c:123: warning: hello
            """)
        return self.do_test_suppressions(step, supps_file, stdout, 0, '')

    def test_suppressions_linenos(self):
        def warningExtractor(step, line, match):
            return line.split(':', 2)
        step = shell.WarningCountingShellCommand(command=['make'],
                                suppressionFile='supps',
                                warningExtractor=warningExtractor)
        supps_file = "abc.c:.*:100-199\ndef.c:.*:22"
        stdout = textwrap.dedent(u"""\
            abc.c:99: warning: seen 1
            abc.c:150: warning: unseen
            def.c:22: warning: unseen
            abc.c:200: warning: seen 2
            """)
        exp_warning_log = textwrap.dedent(u"""\
            abc.c:99: warning: seen 1
            abc.c:200: warning: seen 2
            """)
        return self.do_test_suppressions(step, supps_file, stdout, 2,
                                         exp_warning_log)

    @compat.usesFlushLoggedErrors
    def test_suppressions_warningExtractor_exc(self):
        def warningExtractor(step, line, match):
            raise RuntimeError("oh noes")
        step = shell.WarningCountingShellCommand(command=['make'],
                                suppressionFile='supps',
                                warningExtractor=warningExtractor)
        supps_file = 'x:y' # need at least one supp to trigger warningExtractor
        stdout = "abc.c:99: warning: seen 1"
        d = self.do_test_suppressions(step, supps_file, stdout,
                                         exp_exception=True)
        d.addCallback(lambda _ :
            self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1))
        return d

    def test_suppressions_addSuppression(self):
        # call addSuppression "manually" from a subclass
        class MyWCSC(shell.WarningCountingShellCommand):
            def start(self):
                self.addSuppression([('.*', '.*unseen.*', None, None)])
                return shell.WarningCountingShellCommand.start(self)

        def warningExtractor(step, line, match):
            return line.split(':', 2)
        step = MyWCSC(command=['make'], suppressionFile='supps',
                        warningExtractor=warningExtractor)
        stdout = textwrap.dedent(u"""\
            abc.c:99: warning: seen 1
            abc.c:150: warning: unseen
            abc.c:200: warning: seen 2
            """)
        exp_warning_log = textwrap.dedent(u"""\
            abc.c:99: warning: seen 1
            abc.c:200: warning: seen 2
            """)
        return self.do_test_suppressions(step, '', stdout, 2,
                                         exp_warning_log)

    def test_warnExtractFromRegexpGroups(self):
        step = shell.WarningCountingShellCommand(command=['make'])
        we = shell.WarningCountingShellCommand.warnExtractFromRegexpGroups
        line, pat, exp_file, exp_lineNo, exp_text = \
            ('foo:123:text', '(.*):(.*):(.*)', 'foo', 123, 'text')
        self.assertEqual(we(step, line, re.match(pat, line)),
                (exp_file, exp_lineNo, exp_text))

class Compile(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_class_args(self):
        # since this step is just a pre-configured WarningCountingShellCommand,
        # there' not much to test!
        step = self.setupStep(shell.Compile())
        self.assertEqual(step.name, "compile")
        self.assertTrue(step.haltOnFailure)
        self.assertTrue(step.flunkOnFailure)
        self.assertEqual(step.description, ["compiling"])
        self.assertEqual(step.descriptionDone, ["compile"])
        self.assertEqual(step.command, ["make", "all"])

class Test(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        self.setUpBuildStep()

    def tearDown(self):
        self.tearDownBuildStep()

    def test_setTestResults(self):
        step = self.setupStep(shell.Test())
        step.setTestResults(total=10, failed=3, passed=5, warnings=3)
        self.assertEqual(self.step_statistics, {
            'tests-total' : 10,
            'tests-failed' : 3,
            'tests-passed' : 5,
            'tests-warnings' : 3,
        })
        # ensure that they're additive
        step.setTestResults(total=1, failed=2, passed=3, warnings=4)
        self.assertEqual(self.step_statistics, {
            'tests-total' : 11,
            'tests-failed' : 5,
            'tests-passed' : 8,
            'tests-warnings' : 7,
        })

    def test_describe_not_done(self):
        step = self.setupStep(shell.Test())
        self.assertEqual(step.describe(), ['testing'])

    def test_describe_done(self):
        step = self.setupStep(shell.Test())
        self.step_statistics['tests-total'] = 93
        self.step_statistics['tests-failed'] = 10
        self.step_statistics['tests-passed'] = 20
        self.step_statistics['tests-warnings'] = 30
        self.assertEqual(step.describe(done=True), [ 'test', '93 tests',
                '20 passed', '30 warnings', '10 failed'])

    def test_describe_done_no_total(self):
        step = self.setupStep(shell.Test())
        self.step_statistics['tests-total'] = 0
        self.step_statistics['tests-failed'] = 10
        self.step_statistics['tests-passed'] = 20
        self.step_statistics['tests-warnings'] = 30
        # describe calculates 60 = 10+20+30
        self.assertEqual(step.describe(done=True), [ 'test', '60 tests',
                '20 passed', '30 warnings', '10 failed'])

from buildbot.steps.python import Sphinx

class FakeFile(Mock):
    def __init__(self, text):
        self.text = text

    def readlines(self):
        for line in self.text.split('\n'):
            yield line+'\n'

class FakeLog(Mock):
    chunkSize = 100
    def __init__(self, name):
        self.name = name
        self.text = ''

    def addStdout(self, text):
        self.text += text

    def getText(self):
        return self.text

    def finish(self):pass
    
    def getName(self):
        return self.name

class StepStatus(Mock):
    def addLog(self, name):
        self.log = FakeLog(name)
        return self.log
    
    def getLogs(self, name = None):
        if name:
            return self.log
        return [self.log]

class TestSphinx(unittest.TestCase):
    def testBasic(self):
        s = Sphinx(builddir='_build')
        
        self.failUnlessEqual(['sphinx-build', '.', '_build'], s.command)

        s.step_status = StepStatus()

        s.createSummary(FakeFile('''Running Sphinx v1.0.7
loading pickled environment... done
building [html]: targets for 1 source files that are out of date
updating environment: 0 added, 1 changed, 0 removed
reading sources... [100%] file

file.rst:18: (WARNING/2) Literal block expected; none found.

looking for now-outdated files... none found
pickling environment... done
checking consistency... done
preparing documents... done
writing output... [ 50%] index
writing output... [100%] file

index.rst:: WARNING: toctree contains reference to document 'preamble' that doesn't have a title: no link will be generated
writing additional files... search
copying static files... done
dumping search index... done
dumping object inventory... done
build succeeded, 2 warnings.'''))

        self.failUnlessEqual(True, s.success)
        self.failUnlessEqual(2, s.warnings)
        # Here an additionnal \n is added a the end, to make the test complies to the testMock
        self.failUnlessEqual('''file.rst:18: (WARNING/2) Literal block expected; none found.
index.rst:: WARNING: toctree contains reference to document 'preamble' that doesn't have a title: no link will be generated
''', s.step_status.getLogs('warnings').getText())

        self.failUnlessEqual(WARNINGS, s.evaluateCommand(None))
