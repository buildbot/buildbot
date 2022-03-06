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
from twisted.trial import reporter
from twisted.trial import unittest

from buildbot.test.runprocess import ExpectMasterShell
from buildbot.test.runprocess import MasterRunProcessMixin
from buildbot.util import runprocess


class TestRunprocessMixin(unittest.TestCase):

    def run_test_method(self, method):
        class TestCase(MasterRunProcessMixin, unittest.TestCase):

            def setUp(self):
                self.setup_master_run_process()

            def runTest(self):
                return method(self)

        self.testcase = TestCase()
        result = reporter.TestResult()
        self.testcase.run(result)  # This blocks
        return result

    def assert_test_failure(self, result, expected_failure):
        self.assertEqual(result.errors, [])
        self.assertEqual(len(result.failures), 1)
        self.assertTrue(result.failures[0][1].check(unittest.FailTest))
        if expected_failure:
            self.assertSubstring(expected_failure, result.failures[0][1].getErrorMessage())

    def assert_successful(self, result):
        if not result.wasSuccessful():
            output = 'expected success'
            if result.failures:
                output += (f'\ntest failed: {result.failures[0][1].getErrorMessage()}')
            if result.errors:
                output += (f'\nerrors: {[error[1].value for error in result.errors]}')
            raise self.failureException(output)

        self.assertTrue(result.wasSuccessful())

    def test_patch(self):
        original_run_process = runprocess.run_process

        def method(testcase):
            testcase.expect_commands()
            self.assertEqual(runprocess.run_process, testcase.patched_run_process)

        result = self.run_test_method(method)
        self.assert_successful(result)
        self.assertEqual(runprocess.run_process, original_run_process)

    def test_method_chaining(self):
        expect = ExpectMasterShell('command')
        self.assertEqual(expect, expect.exit(0))
        self.assertEqual(expect, expect.stdout(b"output"))
        self.assertEqual(expect, expect.stderr(b"error"))

    def test_run_process_one_command_only_rc(self):

        @defer.inlineCallbacks
        def method(testcase):
            testcase.expect_commands(
                ExpectMasterShell(["command"]).stdout(b'stdout').stderr(b'stderr'))
            res = yield runprocess.run_process(None, ["command"],
                                               collect_stdout=False, collect_stderr=False)
            self.assertEqual(res, 0)
            testcase.assert_all_commands_ran()

        result = self.run_test_method(method)
        self.assert_successful(result)

    def test_run_process_one_command_only_rc_stdout(self):

        @defer.inlineCallbacks
        def method(testcase):
            testcase.expect_commands(
                ExpectMasterShell(["command"]).stdout(b'stdout').stderr(b'stderr'))
            res = yield runprocess.run_process(None, ["command"],
                                               collect_stdout=True, collect_stderr=False)
            self.assertEqual(res, (0, b'stdout'))
            testcase.assert_all_commands_ran()

        result = self.run_test_method(method)
        self.assert_successful(result)

    def test_run_process_one_command_with_rc_stderr(self):

        @defer.inlineCallbacks
        def method(testcase):
            testcase.expect_commands(
                ExpectMasterShell(["command"]).stdout(b'stdout').stderr(b'stderr'))
            res = yield runprocess.run_process(None, ["command"],
                                               collect_stdout=False, collect_stderr=True)
            self.assertEqual(res, (0, b'stderr'))
            testcase.assert_all_commands_ran()

        result = self.run_test_method(method)
        self.assert_successful(result)

    def test_run_process_one_command_with_rc_stdout_stderr(self):

        @defer.inlineCallbacks
        def method(testcase):
            testcase.expect_commands(
                ExpectMasterShell(["command"]).stdout(b'stdout').stderr(b'stderr'))
            res = yield runprocess.run_process(None, ["command"])
            self.assertEqual(res, (0, b'stdout', b'stderr'))
            testcase.assert_all_commands_ran()

        result = self.run_test_method(method)
        self.assert_successful(result)

    def test_run_process_expect_two_run_one(self):

        @defer.inlineCallbacks
        def method(testcase):
            testcase.expect_commands(ExpectMasterShell(["command"]))
            testcase.expect_commands(ExpectMasterShell(["command2"]))
            res = yield runprocess.run_process(None, ["command"])
            self.assertEqual(res, (0, b'', b''))
            testcase.assert_all_commands_ran()

        result = self.run_test_method(method)
        self.assert_test_failure(result, "assert all expected commands were run")

    def test_run_process_wrong_command(self):

        @defer.inlineCallbacks
        def method(testcase):
            testcase.expect_commands(ExpectMasterShell(["command2"]))
            yield runprocess.run_process(None, ["command"])

        result = self.run_test_method(method)
        self.assert_test_failure(result, "unexpected command run")
        # assert we have a meaningful message
        self.assert_test_failure(result, "command2")

    def test_run_process_wrong_args(self):

        @defer.inlineCallbacks
        def method(testcase):
            testcase.expect_commands(ExpectMasterShell(["command", "arg"]))
            yield runprocess.run_process(None, ["command", "otherarg"])
            testcase.assert_all_commands_ran()

        result = self.run_test_method(method)
        self.assert_test_failure(result, "unexpected command run")

    def test_run_process_missing_path(self):

        @defer.inlineCallbacks
        def method(testcase):
            testcase.expect_commands(ExpectMasterShell(["command"]).workdir("/home"))
            yield runprocess.run_process(None, ["command"])
            testcase.assert_all_commands_ran()

        result = self.run_test_method(method)
        self.assert_test_failure(result, "unexpected command run")

    def test_run_process_wrong_path(self):

        @defer.inlineCallbacks
        def method(testcase):
            testcase.expect_commands(ExpectMasterShell(["command", "arg"]).workdir("/home"))
            yield runprocess.run_process(None, ["command"], workdir="/path")
            testcase.assert_all_commands_ran()

        result = self.run_test_method(method)
        self.assert_test_failure(result, "unexpected command run")

    def test_run_process_not_current_path(self):

        @defer.inlineCallbacks
        def method(testcase):
            testcase.expect_commands(ExpectMasterShell(["command", "arg"]))
            yield runprocess.run_process(None, ["command"], workdir="/path")
            testcase.assert_all_commands_ran()

        result = self.run_test_method(method)
        self.assert_test_failure(result, "unexpected command run")

    def test_run_process_error_output(self):

        @defer.inlineCallbacks
        def method(testcase):
            testcase.expect_commands(ExpectMasterShell(["command"]).stderr(b"some test"))
            res = yield runprocess.run_process(None, ["command"], collect_stderr=False,
                                               stderr_is_error=True)
            self.assertEqual(res, (-1, b''))
            testcase.assert_all_commands_ran()

        result = self.run_test_method(method)
        self.assert_successful(result)

    def test_run_process_nonzero_exit(self):

        @defer.inlineCallbacks
        def method(testcase):
            testcase.expect_commands(ExpectMasterShell(["command"]).exit(1))
            res = yield runprocess.run_process(None, ["command"])
            self.assertEqual(res, (1, b'', b''))
            testcase.assert_all_commands_ran()

        result = self.run_test_method(method)
        self.assert_successful(result)

    def test_run_process_environ_success(self):

        @defer.inlineCallbacks
        def method(testcase):
            testcase.expect_commands(ExpectMasterShell(["command"]))
            testcase.add_run_process_expect_env({'key': 'value'})
            res = yield runprocess.run_process(None, ["command"], env={'key': 'value'})
            self.assertEqual(res, (0, b'', b''))
            testcase.assert_all_commands_ran()

        result = self.run_test_method(method)
        self.assert_successful(result)

    def test_run_process_environ_wrong_value(self):

        @defer.inlineCallbacks
        def method(testcase):
            testcase.expect_commands(ExpectMasterShell(["command"]))
            testcase.add_run_process_expect_env({'key': 'value'})
            yield runprocess.run_process(None, ["command"], env={'key': 'wrongvalue'})
            testcase.assert_all_commands_ran()

        result = self.run_test_method(method)
        self.assert_test_failure(result, "Expected environment to have key = 'value'")

    def test_run_process_environ_missing(self):
        @defer.inlineCallbacks
        def method(testcase):
            testcase.expect_commands(ExpectMasterShell(["command"]))
            testcase.add_run_process_expect_env({'key': 'value'})
            d = runprocess.run_process(None, ["command"])
            return d
        result = self.run_test_method(method)
        self.assert_test_failure(result, "Expected environment to have key = 'value'")
