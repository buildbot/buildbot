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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot import config
from buildbot.process import properties
from buildbot.process import remotetransfer
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SKIPPED
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.steps import shell
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import ExpectRemoteRef
from buildbot.test.steps import ExpectShell
from buildbot.test.steps import ExpectUploadFile
from buildbot.test.steps import TestBuildStepMixin
from buildbot.test.util import config as configmixin


class TestShellCommandExecution(TestBuildStepMixin,
                                configmixin.ConfigErrorsMixin,
                                TestReactorMixin,
                                unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_doStepIf_False(self):
        self.setup_step(shell.ShellCommand(command="echo hello", doStepIf=False))
        self.expect_outcome(result=SKIPPED,
                           state_string="'echo hello' (skipped)")
        return self.run_step()

    def test_constructor_args_validity(self):
        # this checks that an exception is raised for invalid arguments
        with self.assertRaisesConfigError(
                "Invalid argument(s) passed to ShellCommand: "):
            shell.ShellCommand(workdir='build', command="echo Hello World",
                               wrongArg1=1, wrongArg2='two')

    def test_run_simple(self):
        self.setup_step(shell.ShellCommand(workdir='build', command="echo hello"))
        self.expect_commands(
            ExpectShell(workdir='build', command='echo hello')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="'echo hello'")
        return self.run_step()

    def test_run_list(self):
        self.setup_step(shell.ShellCommand(workdir='build',
                                          command=['trial', '-b', '-B', 'buildbot.test']))
        self.expect_commands(
            ExpectShell(workdir='build',
                        command=['trial', '-b', '-B', 'buildbot.test'])
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS,
                           state_string="'trial -b ...'")
        return self.run_step()

    def test_run_nested_description(self):
        self.setup_step(shell.ShellCommand(
            workdir='build',
            command=properties.FlattenList(['trial', ['-b', '-B'], 'buildbot.test']),
            descriptionDone=properties.FlattenList(['test', ['done']]),
            descriptionSuffix=properties.FlattenList(['suff', ['ix']])))
        self.expect_commands(
            ExpectShell(workdir='build',
                        command=['trial', '-b', '-B', 'buildbot.test'])
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS,
                           state_string='test done suff ix')
        return self.run_step()

    def test_run_nested_command(self):
        self.setup_step(shell.ShellCommand(workdir='build',
                                          command=['trial', ['-b', '-B'], 'buildbot.test']))
        self.expect_commands(
            ExpectShell(workdir='build',
                        command=['trial', '-b', '-B', 'buildbot.test'])
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS,
                           state_string="'trial -b ...'")
        return self.run_step()

    def test_run_nested_deeply_command(self):
        self.setup_step(shell.ShellCommand(workdir='build',
                                          command=[['trial', ['-b', ['-B']]], 'buildbot.test']))
        self.expect_commands(
            ExpectShell(workdir='build',
                        command=['trial', '-b', '-B', 'buildbot.test'])
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS,
                           state_string="'trial -b ...'")
        return self.run_step()

    def test_run_nested_empty_command(self):
        self.setup_step(shell.ShellCommand(workdir='build',
                                          command=['trial', [], '-b', [], 'buildbot.test']))
        self.expect_commands(
            ExpectShell(workdir='build',
                        command=['trial', '-b', 'buildbot.test'])
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS,
                           state_string="'trial -b ...'")
        return self.run_step()

    def test_run_env(self):
        self.setup_step(shell.ShellCommand(workdir='build', command="echo hello"),
                       worker_env=dict(DEF='HERE'))
        self.expect_commands(
            ExpectShell(workdir='build', command='echo hello',
                        env=dict(DEF='HERE'))
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_run_env_override(self):
        self.setup_step(shell.ShellCommand(workdir='build', env={'ABC': '123'},
                                          command="echo hello"),
                       worker_env=dict(ABC='XXX', DEF='HERE'))
        self.expect_commands(
            ExpectShell(workdir='build', command='echo hello',
                        env=dict(ABC='123', DEF='HERE'))
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_run_usePTY(self):
        self.setup_step(shell.ShellCommand(workdir='build', command="echo hello", usePTY=False))
        self.expect_commands(
            ExpectShell(workdir='build', command='echo hello', use_pty=False)
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_run_usePTY_old_worker(self):
        self.setup_step(
            shell.ShellCommand(workdir='build', command="echo hello", usePTY=True),
            worker_version=dict(shell='1.1'))
        self.expect_commands(
            ExpectShell(workdir='build', command='echo hello')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_run_decodeRC(self, rc=1, results=WARNINGS, extra_text=" (warnings)"):
        self.setup_step(shell.ShellCommand(workdir='build', command="echo hello",
                                          decodeRC={1: WARNINGS}))
        self.expect_commands(
            ExpectShell(workdir='build', command='echo hello')
            .exit(rc)
        )
        self.expect_outcome(
            result=results, state_string="'echo hello'" + extra_text)
        return self.run_step()

    def test_run_decodeRC_defaults(self):
        return self.test_run_decodeRC(2, FAILURE, extra_text=" (failure)")

    def test_run_decodeRC_defaults_0_is_failure(self):
        return self.test_run_decodeRC(0, FAILURE, extra_text=" (failure)")

    def test_missing_command_error(self):
        # this checks that an exception is raised for invalid arguments
        with self.assertRaisesConfigError(
                "ShellCommand's `command' argument is not specified"):
            shell.ShellCommand()


class TreeSize(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_run_success(self):
        self.setup_step(shell.TreeSize())
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['du', '-s', '-k', '.'])
            .stdout('9292    .\n')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS,
                           state_string="treesize 9292 KiB")
        self.expect_property('tree-size-KiB', 9292)
        return self.run_step()

    def test_run_misparsed(self):
        self.setup_step(shell.TreeSize())
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['du', '-s', '-k', '.'])
            .stdout('abcdef\n')
            .exit(0)
        )
        self.expect_outcome(result=WARNINGS,
                           state_string="treesize unknown (warnings)")
        return self.run_step()

    def test_run_failed(self):
        self.setup_step(shell.TreeSize())
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['du', '-s', '-k', '.'])
            .stderr('abcdef\n')
            .exit(1)
        )
        self.expect_outcome(result=FAILURE,
                           state_string="treesize unknown (failure)")
        return self.run_step()


class SetPropertyFromCommand(TestBuildStepMixin, TestReactorMixin,
                             unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_constructor_conflict(self):
        with self.assertRaises(config.ConfigErrors):
            shell.SetPropertyFromCommand(property='foo', extract_fn=lambda: None)

    def test_run_property(self):
        self.setup_step(
            shell.SetPropertyFromCommand(property="res", command="cmd"))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command="cmd")
            .stdout('\n\nabcdef\n')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS,
                           state_string="property 'res' set")
        self.expect_property("res", "abcdef")  # note: stripped
        self.expect_log_file('property changes', r"res: " + repr('abcdef'))
        return self.run_step()

    def test_renderable_workdir(self):
        self.setup_step(
            shell.SetPropertyFromCommand(property="res", command="cmd",
                                         workdir=properties.Interpolate('wkdir')))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command="cmd")
            .stdout('\n\nabcdef\n')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS,
                           state_string="property 'res' set")
        self.expect_property("res", "abcdef")  # note: stripped
        self.expect_log_file('property changes', r"res: " + repr('abcdef'))
        return self.run_step()

    def test_run_property_no_strip(self):
        self.setup_step(shell.SetPropertyFromCommand(property="res", command="cmd", strip=False))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command="cmd")
            .stdout('\n\nabcdef\n')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS,
                           state_string="property 'res' set")
        self.expect_property("res", "\n\nabcdef\n")
        self.expect_log_file('property changes', r"res: " + repr('\n\nabcdef\n'))
        return self.run_step()

    def test_run_failure(self):
        self.setup_step(
            shell.SetPropertyFromCommand(property="res", command="blarg"))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command="blarg")
            .stderr('cannot blarg: File not found')
            .exit(1)
        )
        self.expect_outcome(result=FAILURE,
                           state_string="'blarg' (failure)")
        self.expect_no_property("res")
        return self.run_step()

    def test_run_extract_fn(self):
        def extract_fn(rc, stdout, stderr):
            self.assertEqual(
                (rc, stdout, stderr), (0, 'startend\n', 'STARTEND\n'))
            return dict(a=1, b=2)
        self.setup_step(
            shell.SetPropertyFromCommand(extract_fn=extract_fn, command="cmd"))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command="cmd")
            .stdout('start')
            .stderr('START')
            .stdout('end')
            .stderr('END')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS,
                           state_string="2 properties set")
        self.expect_log_file('property changes', 'a: 1\nb: 2')
        self.expect_property("a", 1)
        self.expect_property("b", 2)
        return self.run_step()

    def test_run_extract_fn_cmdfail(self):
        def extract_fn(rc, stdout, stderr):
            self.assertEqual((rc, stdout, stderr), (3, '', ''))
            return dict(a=1, b=2)
        self.setup_step(
            shell.SetPropertyFromCommand(extract_fn=extract_fn, command="cmd"))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command="cmd")
            .exit(3)
        )
        # note that extract_fn *is* called anyway
        self.expect_outcome(result=FAILURE,
                           state_string="2 properties set (failure)")
        self.expect_log_file('property changes', 'a: 1\nb: 2')
        return self.run_step()

    def test_run_extract_fn_cmdfail_empty(self):
        def extract_fn(rc, stdout, stderr):
            self.assertEqual((rc, stdout, stderr), (3, '', ''))
            return {}
        self.setup_step(
            shell.SetPropertyFromCommand(extract_fn=extract_fn, command="cmd"))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command="cmd")
            .exit(3)
        )
        # note that extract_fn *is* called anyway, but returns no properties
        self.expect_outcome(result=FAILURE,
                           state_string="'cmd' (failure)")
        return self.run_step()

    @defer.inlineCallbacks
    def test_run_extract_fn_exception(self):
        def extract_fn(rc, stdout, stderr):
            raise RuntimeError("oh noes")
        self.setup_step(
            shell.SetPropertyFromCommand(extract_fn=extract_fn, command="cmd"))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command="cmd")
            .exit(0)
        )
        # note that extract_fn *is* called anyway, but returns no properties
        self.expect_outcome(result=EXCEPTION,
                           state_string="'cmd' (exception)")
        yield self.run_step()
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)

    def test_error_both_set(self):
        """
        If both ``extract_fn`` and ``property`` are defined,
        ``SetPropertyFromCommand`` reports a config error.
        """
        with self.assertRaises(config.ConfigErrors):
            shell.SetPropertyFromCommand(command=["echo", "value"], property="propname",
                                         extract_fn=lambda x: {"propname": "hello"})

    def test_error_none_set(self):
        """
        If neither ``extract_fn`` and ``property`` are defined,
        ``SetPropertyFromCommand`` reports a config error.
        """
        with self.assertRaises(config.ConfigErrors):
            shell.SetPropertyFromCommand(command=["echo", "value"])


class PerlModuleTest(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_new_version_success(self):
        self.setup_step(shell.PerlModuleTest(command="cmd"))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command="cmd")
            .stdout(textwrap.dedent("""\
                    This junk ignored
                    Test Summary Report
                    Result: PASS
                    Tests: 10 Failed: 0
                    Tests: 10 Failed: 0
                    Files=93, Tests=20"""))
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string='20 tests 20 passed')
        return self.run_step()

    def test_new_version_warnings(self):
        self.setup_step(shell.PerlModuleTest(command="cmd",
                                            warningPattern='^OHNOES'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command="cmd")
            .stdout(textwrap.dedent("""\
                    This junk ignored
                    Test Summary Report
                    -------------------
                    foo.pl (Wstat: 0 Tests: 10 Failed: 0)
                      Failed test:  0
                    OHNOES 1
                    OHNOES 2
                    Files=93, Tests=20,  0 wallclock secs ...
                    Result: PASS"""))
            .exit(0)
        )
        self.expect_outcome(
            result=WARNINGS,
            state_string='20 tests 20 passed 2 warnings (warnings)')
        return self.run_step()

    def test_new_version_failed(self):
        self.setup_step(shell.PerlModuleTest(command="cmd"))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command="cmd")
            .stdout(textwrap.dedent("""\
                    foo.pl .. 1/4"""))
            .stderr(textwrap.dedent("""\
                    # Failed test 2 in foo.pl at line 6
                    #  foo.pl line 6 is: ok(0);"""))
            .stdout(textwrap.dedent("""\
                    foo.pl .. Failed 1/4 subtests

                    Test Summary Report
                    -------------------
                    foo.pl (Wstat: 0 Tests: 4 Failed: 1)
                      Failed test:  0
                    Files=1, Tests=4,  0 wallclock secs ( 0.06 usr  0.01 sys +  0.03 cusr
                    0.01 csys =  0.11 CPU)
                    Result: FAIL"""))
            .stderr(textwrap.dedent("""\
                    Failed 1/1 test programs. 1/4 subtests failed."""))
            .exit(1)
        )
        self.expect_outcome(result=FAILURE,
                           state_string='4 tests 3 passed 1 failed (failure)')
        return self.run_step()

    def test_old_version_success(self):
        self.setup_step(shell.PerlModuleTest(command="cmd"))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command="cmd")
            .stdout(textwrap.dedent("""\
                    This junk ignored
                    All tests successful
                    Files=10, Tests=20, 100 wall blah blah"""))
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS,
                           state_string='20 tests 20 passed')
        return self.run_step()

    def test_old_version_failed(self):
        self.setup_step(shell.PerlModuleTest(command="cmd"))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command="cmd")
            .stdout(textwrap.dedent("""\
                    This junk ignored
                    Failed 1/1 test programs, 3/20 subtests failed."""))
            .exit(1)
        )
        self.expect_outcome(result=FAILURE,
                           state_string='20 tests 17 passed 3 failed (failure)')
        return self.run_step()


class SetPropertyDeprecation(unittest.TestCase):

    """
    Tests for L{shell.SetProperty}
    """

    def test_deprecated(self):
        """
        Accessing L{shell.SetProperty} reports a deprecation error.
        """
        shell.SetProperty
        warnings = self.flushWarnings([self.test_deprecated])
        self.assertEqual(len(warnings), 1)
        self.assertIdentical(warnings[0]['category'], DeprecationWarning)
        self.assertEqual(warnings[0]['message'],
                         "buildbot.steps.shell.SetProperty was deprecated in Buildbot 0.8.8: "
                         "It has been renamed to SetPropertyFromCommand"
                         )


class Configure(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_class_attrs(self):
        step = shell.Configure()
        self.assertEqual(step.command, ['./configure'])

    def test_run(self):
        self.setup_step(shell.Configure())

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=["./configure"])
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()


class WarningCountingShellCommand(TestBuildStepMixin,
                                  configmixin.ConfigErrorsMixin,
                                  TestReactorMixin,
                                  unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_no_warnings(self):
        self.setup_step(shell.WarningCountingShellCommand(workdir='w', command=['make']))
        self.expect_commands(
            ExpectShell(workdir='w',
                        command=["make"])
            .stdout('blarg success!')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property("warnings-count", 0)
        return self.run_step()

    def test_default_pattern(self):
        self.setup_step(shell.WarningCountingShellCommand(command=['make']))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=["make"])
            .stdout('normal: foo\nwarning: blarg!\n'
                    'also normal\nWARNING: blarg!\n')
            .exit(0)
        )
        self.expect_outcome(result=WARNINGS)
        self.expect_property("warnings-count", 2)
        self.expect_log_file("warnings (2)",
                           "warning: blarg!\nWARNING: blarg!\n")
        return self.run_step()

    def test_custom_pattern(self):
        self.setup_step(shell.WarningCountingShellCommand(command=['make'],
                                                         warningPattern=r"scary:.*"))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=["make"])
            .stdout('scary: foo\nwarning: bar\nscary: bar')
            .exit(0)
        )
        self.expect_outcome(result=WARNINGS)
        self.expect_property("warnings-count", 2)
        self.expect_log_file("warnings (2)", "scary: foo\nscary: bar\n")
        return self.run_step()

    def test_maxWarnCount(self):
        self.setup_step(shell.WarningCountingShellCommand(command=['make'], maxWarnCount=9))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=["make"])
            .stdout('warning: noo!\n' * 10)
            .exit(0)
        )
        self.expect_outcome(result=FAILURE)
        self.expect_property("warnings-count", 10)
        return self.run_step()

    def test_fail_with_warnings(self):
        self.setup_step(shell.WarningCountingShellCommand(command=['make']))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=["make"])
            .stdout('warning: I might fail')
            .exit(3)
        )
        self.expect_outcome(result=FAILURE)
        self.expect_property("warnings-count", 1)
        self.expect_log_file("warnings (1)", "warning: I might fail\n")
        return self.run_step()

    def test_warn_with_decoderc(self):
        self.setup_step(shell.WarningCountingShellCommand(command=['make'],
                                                         decodeRC={3: WARNINGS}))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=["make"],
                        )
            .stdout('I might fail with rc')
            .exit(3)
        )
        self.expect_outcome(result=WARNINGS)
        self.expect_property("warnings-count", 0)
        return self.run_step()

    def do_test_suppressions(self, step, supps_file='', stdout='',
                             exp_warning_count=0, exp_warning_log='',
                             exp_exception=False, props=None):
        self.setup_step(step)

        if props is not None:
            for key in props:
                self.build.setProperty(key, props[key], "")

        if supps_file is not None:
            self.expect_commands(
                # step will first get the remote suppressions file
                ExpectUploadFile(blocksize=32768, maxsize=None,
                                 workersrc='supps', workdir='wkdir',
                                 writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
                .upload_string(supps_file)
                .exit(0),
                # and then run the command
                ExpectShell(workdir='wkdir',
                            command=["make"])
                .stdout(stdout)
                .exit(0)
            )
        else:
            self.expect_commands(
                ExpectShell(workdir='wkdir',
                            command=["make"])
                .stdout(stdout)
                .exit(0)
            )
        if exp_exception:
            self.expect_outcome(result=EXCEPTION,
                               state_string="'make' (exception)")
        else:
            if exp_warning_count != 0:
                self.expect_outcome(result=WARNINGS,
                                   state_string="'make' (warnings)")
                self.expect_log_file(f"warnings ({exp_warning_count})",
                                   exp_warning_log)
            else:
                self.expect_outcome(result=SUCCESS,
                                   state_string="'make'")
            self.expect_property("warnings-count", exp_warning_count)
        return self.run_step()

    def test_suppressions(self):
        step = shell.WarningCountingShellCommand(command=['make'], suppressionFile='supps')
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
        stdout = textwrap.dedent("""\
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
        stdout = textwrap.dedent("""\
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
        stdout = textwrap.dedent("""\
            abc.c:99: warning: seen 1
            abc.c:150: warning: unseen
            def.c:22: warning: unseen
            abc.c:200: warning: seen 2
            """)
        exp_warning_log = textwrap.dedent("""\
            abc.c:99: warning: seen 1
            abc.c:200: warning: seen 2
            """)
        return self.do_test_suppressions(step, supps_file, stdout, 2,
                                         exp_warning_log)

    @defer.inlineCallbacks
    def test_suppressions_warningExtractor_exc(self):
        def warningExtractor(step, line, match):
            raise RuntimeError("oh noes")
        step = shell.WarningCountingShellCommand(command=['make'],
                                                 suppressionFile='supps',
                                                 warningExtractor=warningExtractor)
        # need at least one supp to trigger warningExtractor
        supps_file = 'x:y'
        stdout = "abc.c:99: warning: seen 1"
        yield self.do_test_suppressions(step, supps_file, stdout,
                                        exp_exception=True)
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)

    def test_suppressions_addSuppression(self):
        # call addSuppression "manually" from a subclass
        class MyWCSC(shell.WarningCountingShellCommand):

            def run(self):
                self.addSuppression([('.*', '.*unseen.*', None, None)])
                return super().run()

        def warningExtractor(step, line, match):
            return line.split(':', 2)
        step = MyWCSC(command=['make'], suppressionFile='supps',
                      warningExtractor=warningExtractor)
        stdout = textwrap.dedent("""\
            abc.c:99: warning: seen 1
            abc.c:150: warning: unseen
            abc.c:200: warning: seen 2
            """)
        exp_warning_log = textwrap.dedent("""\
            abc.c:99: warning: seen 1
            abc.c:200: warning: seen 2
            """)
        return self.do_test_suppressions(step, '', stdout, 2,
                                         exp_warning_log)

    def test_suppressions_suppressionsParameter(self):
        def warningExtractor(step, line, match):
            return line.split(':', 2)

        supps = (
                   ("abc.c", ".*", 100, 199),
                   ("def.c", ".*", 22, 22),
                )
        step = shell.WarningCountingShellCommand(command=['make'],
                                                 suppressionList=supps,
                                                 warningExtractor=warningExtractor)
        stdout = textwrap.dedent("""\
            abc.c:99: warning: seen 1
            abc.c:150: warning: unseen
            def.c:22: warning: unseen
            abc.c:200: warning: seen 2
            """)
        exp_warning_log = textwrap.dedent("""\
            abc.c:99: warning: seen 1
            abc.c:200: warning: seen 2
            """)
        return self.do_test_suppressions(step, None, stdout, 2,
                                         exp_warning_log)

    def test_suppressions_suppressionsRenderableParameter(self):
        def warningExtractor(step, line, match):
            return line.split(':', 2)

        supps = (
                   ("abc.c", ".*", 100, 199),
                   ("def.c", ".*", 22, 22),
        )

        step = shell.WarningCountingShellCommand(
            command=['make'],
            suppressionList=properties.Property("suppressionsList"),
            warningExtractor=warningExtractor)

        stdout = textwrap.dedent("""\
            abc.c:99: warning: seen 1
            abc.c:150: warning: unseen
            def.c:22: warning: unseen
            abc.c:200: warning: seen 2
            """)
        exp_warning_log = textwrap.dedent("""\
            abc.c:99: warning: seen 1
            abc.c:200: warning: seen 2
            """)
        return self.do_test_suppressions(step, None, stdout, 2,
                                         exp_warning_log, props={"suppressionsList": supps})

    def test_warnExtractFromRegexpGroups(self):
        step = shell.WarningCountingShellCommand(command=['make'])
        we = shell.WarningCountingShellCommand.warnExtractFromRegexpGroups
        line, pat, exp_file, exp_lineNo, exp_text = \
            ('foo:123:text', '(.*):(.*):(.*)', 'foo', 123, 'text')
        self.assertEqual(we(step, line, re.match(pat, line)),
                         (exp_file, exp_lineNo, exp_text))

    def test_missing_command_error(self):
        # this checks that an exception is raised for invalid arguments
        with self.assertRaisesConfigError(
                "WarningCountingShellCommand's 'command' argument is not specified"):
            shell.WarningCountingShellCommand()


class Compile(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_class_args(self):
        # since this step is just a pre-configured WarningCountingShellCommand,
        # there' not much to test!
        step = self.setup_step(shell.Compile())
        self.assertEqual(step.name, "compile")
        self.assertTrue(step.haltOnFailure)
        self.assertTrue(step.flunkOnFailure)
        self.assertEqual(step.description, ["compiling"])
        self.assertEqual(step.descriptionDone, ["compile"])
        self.assertEqual(step.command, ["make", "all"])


class Test(TestBuildStepMixin, configmixin.ConfigErrorsMixin,
           TestReactorMixin,
           unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        self.setup_test_build_step()

    def tearDown(self):
        self.tear_down_test_build_step()

    def test_setTestResults(self):
        step = self.setup_step(shell.Test())
        step.setTestResults(total=10, failed=3, passed=5, warnings=3)
        self.assertEqual(step.statistics, {
            'tests-total': 10,
            'tests-failed': 3,
            'tests-passed': 5,
            'tests-warnings': 3,
        })
        # ensure that they're additive
        step.setTestResults(total=1, failed=2, passed=3, warnings=4)
        self.assertEqual(step.statistics, {
            'tests-total': 11,
            'tests-failed': 5,
            'tests-passed': 8,
            'tests-warnings': 7,
        })

    def test_describe_not_done(self):
        step = self.setup_step(shell.Test())
        step.results = SUCCESS
        step.rendered = True
        self.assertEqual(step.getResultSummary(), {'step': 'test'})

    def test_describe_done(self):
        step = self.setup_step(shell.Test())
        step.rendered = True
        step.results = SUCCESS
        step.statistics['tests-total'] = 93
        step.statistics['tests-failed'] = 10
        step.statistics['tests-passed'] = 20
        step.statistics['tests-warnings'] = 30
        self.assertEqual(step.getResultSummary(),
                         {'step': '93 tests 20 passed 30 warnings 10 failed'})

    def test_describe_done_no_total(self):
        step = self.setup_step(shell.Test())
        step.rendered = True
        step.results = SUCCESS
        step.statistics['tests-total'] = 0
        step.statistics['tests-failed'] = 10
        step.statistics['tests-passed'] = 20
        step.statistics['tests-warnings'] = 30
        # describe calculates 60 = 10+20+30
        self.assertEqual(step.getResultSummary(),
                         {'step': '60 tests 20 passed 30 warnings 10 failed'})
