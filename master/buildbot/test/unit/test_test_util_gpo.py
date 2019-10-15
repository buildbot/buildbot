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

import sys

import twisted
from twisted.internet import defer
from twisted.internet import utils
from twisted.trial import reporter
from twisted.trial import unittest

from buildbot.test.util.gpo import Expect
from buildbot.test.util.gpo import GetProcessOutputMixin


class TestGPOMixin(unittest.TestCase):

    # these tests use self.patch, but the SkipTest exception gets eaten, so
    # explicitly skip things here.
    if twisted.version.major <= 9 and sys.version_info[:2] == (2, 7):
        skip = "unittest.TestCase.patch is not available"

    def runTestMethod(self, method):
        class TestCase(GetProcessOutputMixin, unittest.TestCase):

            def setUp(self):
                self.setUpGetProcessOutput()

            def runTest(self):
                return method(self)
        self.testcase = TestCase()
        result = reporter.TestResult()
        self.testcase.run(result)  # This blocks
        return result

    def assertTestFailure(self, result, expectedFailure):
        self.assertEqual(result.errors, [])
        self.assertEqual(len(result.failures), 1)
        self.assertTrue(result.failures[0][1].check(unittest.FailTest))
        if expectedFailure:
            self.assertSubstring(
                expectedFailure, result.failures[0][1].getErrorMessage())

    def assertSuccessful(self, result):
        if not result.wasSuccessful():
            output = 'expected success'
            if result.failures:
                output += ('\ntest failed: %s' %
                           result.failures[0][1].getErrorMessage())
            if result.errors:
                output += ('\nerrors: %s' %
                           [error[1].value for error in result.errors])
            raise self.failureException(output)

        self.assertTrue(result.wasSuccessful())

    def test_patch(self):
        original_getProcessOutput = utils.getProcessOutput
        original_getProcessOutputAndValue = utils.getProcessOutputAndValue

        def method(testcase):
            testcase.expectCommands()
            self.assertEqual(utils.getProcessOutput,
                             testcase.patched_getProcessOutput)
            self.assertEqual(utils.getProcessOutputAndValue,
                             testcase.patched_getProcessOutputAndValue)
        result = self.runTestMethod(method)
        self.assertSuccessful(result)
        self.assertEqual(utils.getProcessOutput,
                         original_getProcessOutput)
        self.assertEqual(utils.getProcessOutputAndValue,
                         original_getProcessOutputAndValue)

    def test_methodChaining(self):
        expect = Expect('command')
        self.assertEqual(expect, expect.exit(0))
        self.assertEqual(expect, expect.stdout(b"output"))
        self.assertEqual(expect, expect.stderr(b"error"))

    def test_gpo_oneCommand(self):
        @defer.inlineCallbacks
        def method(testcase):
            testcase.expectCommands(Expect("command"))
            res = yield utils.getProcessOutput("command", ())
            self.assertEqual(res, b'')
            testcase.assertAllCommandsRan()
        result = self.runTestMethod(method)
        self.assertSuccessful(result)

    def test_gpo_expectTwo_runOne(self):
        @defer.inlineCallbacks
        def method(testcase):
            testcase.expectCommands(Expect("command"))
            testcase.expectCommands(Expect("command2"))
            res = yield utils.getProcessOutput("command", ())
            self.assertEqual(res, b'')
            testcase.assertAllCommandsRan()
        result = self.runTestMethod(method)
        self.assertTestFailure(result, "assert all expected commands were run")

    def test_gpo_wrongCommand(self):
        def method(testcase):
            testcase.expectCommands(Expect("command2"))
            d = utils.getProcessOutput("command", ())
            return d
        result = self.runTestMethod(method)
        self.assertTestFailure(result, "unexpected command run")
        # assert we have a meaningful message
        self.assertTestFailure(result, "command2")

    def test_gpo_wrongArgs(self):
        @defer.inlineCallbacks
        def method(testcase):
            testcase.expectCommands(Expect("command", "arg"))
            yield utils.getProcessOutput("command", ("otherarg",))
            testcase.assertAllCommandsRan()
        result = self.runTestMethod(method)
        self.assertTestFailure(result, "unexpected command run")

    def test_gpo_missingPath(self):
        @defer.inlineCallbacks
        def method(testcase):
            testcase.expectCommands(Expect("command", "arg").path("/home"))
            yield utils.getProcessOutput("command", ("otherarg",))
            testcase.assertAllCommandsRan()
        result = self.runTestMethod(method)
        self.assertTestFailure(result, "unexpected command run")

    def test_gpo_wrongPath(self):
        @defer.inlineCallbacks
        def method(testcase):
            testcase.expectCommands(Expect("command", "arg").path("/home"))
            yield utils.getProcessOutput("command", ("otherarg",), path="/work")
            testcase.assertAllCommandsRan()
        result = self.runTestMethod(method)
        self.assertTestFailure(result, "unexpected command run")

    def test_gpo_notCurrentPath(self):
        @defer.inlineCallbacks
        def method(testcase):
            testcase.expectCommands(Expect("command", "arg"))
            yield utils.getProcessOutput("command", ("otherarg",), path="/work")
            testcase.assertAllCommandsRan()
        result = self.runTestMethod(method)
        self.assertTestFailure(result, "unexpected command run")

    def test_gpo_errorOutput(self):
        def method(testcase):
            testcase.expectCommands(Expect("command").stderr(b"some test"))
            d = testcase.assertFailure(
                utils.getProcessOutput("command", ()), [IOError])
            return d
        result = self.runTestMethod(method)
        self.assertTestFailure(result, "got stderr: " + repr(b'some test'))

    def test_gpo_errorOutput_errtoo(self):
        @defer.inlineCallbacks
        def method(testcase):
            testcase.expectCommands(Expect("command").stderr(b"some test"))
            res = yield utils.getProcessOutput("command", (), errortoo=True)
            testcase.assertEqual(res, b"some test")
        result = self.runTestMethod(method)
        self.assertSuccessful(result)

    def test_gpo_exitIgnored(self):
        @defer.inlineCallbacks
        def method(testcase):
            testcase.expectCommands(Expect("command").exit(1))
            res = yield utils.getProcessOutput("command", ())
            self.assertEqual(res, b'')
        result = self.runTestMethod(method)
        self.assertSuccessful(result)

    def test_gpo_output(self):
        @defer.inlineCallbacks
        def method(testcase):
            testcase.expectCommands(Expect("command").stdout(b"stdout"))
            res = yield utils.getProcessOutput("command", ())
            testcase.assertEqual(res, b"stdout")
        result = self.runTestMethod(method)
        self.assertSuccessful(result)

    def test_gpo_outputAndError(self):
        @defer.inlineCallbacks
        def method(testcase):
            testcase.expectCommands(
                Expect("command").stdout(b"stdout").stderr(b"stderr"))
            res = yield utils.getProcessOutput("command", (), errortoo=True)

            testcase.assertSubstring(b"stdout", res)
            testcase.assertSubstring(b"stderr", res)
        result = self.runTestMethod(method)
        self.assertSuccessful(result)

    def test_gpo_environ_success(self):
        @defer.inlineCallbacks
        def method(testcase):
            testcase.expectCommands(Expect("command"))
            testcase.addGetProcessOutputExpectEnv({'key': 'value'})
            res = yield utils.getProcessOutput("command", (), env={'key': 'value'})
            self.assertEqual(res, b'')
            testcase.assertAllCommandsRan()
        result = self.runTestMethod(method)
        self.assertSuccessful(result)

    def test_gpo_environ_wrongValue(self):
        def method(testcase):
            testcase.expectCommands(Expect("command"))
            testcase.addGetProcessOutputExpectEnv({'key': 'value'})
            d = utils.getProcessOutput(
                "command", (), env={'key': 'wrongvalue'})
            return d
        result = self.runTestMethod(method)
        self.assertTestFailure(
            result, "Expected environment to have key = 'value'")

    def test_gpo_environ_missing(self):
        def method(testcase):
            testcase.expectCommands(Expect("command"))
            testcase.addGetProcessOutputExpectEnv({'key': 'value'})
            d = utils.getProcessOutput("command", ())
            return d
        result = self.runTestMethod(method)
        self.assertTestFailure(
            result, "Expected environment to have key = 'value'")

    def test_gpoav_oneCommand(self):
        @defer.inlineCallbacks
        def method(testcase):
            testcase.expectCommands(Expect("command"))
            res = yield utils.getProcessOutputAndValue("command", ())
            self.assertEqual(res, (b'', b'', 0))
            testcase.assertAllCommandsRan()
        result = self.runTestMethod(method)
        self.assertSuccessful(result)

    def test_gpoav_expectTwo_runOne(self):
        @defer.inlineCallbacks
        def method(testcase):
            testcase.expectCommands(Expect("command"))
            testcase.expectCommands(Expect("command2"))
            res = yield utils.getProcessOutputAndValue("command", ())
            self.assertEqual(res, (b'', b'', 0))
            testcase.assertAllCommandsRan()
        result = self.runTestMethod(method)
        self.assertTestFailure(result, "assert all expected commands were run")

    def test_gpoav_wrongCommand(self):
        @defer.inlineCallbacks
        def method(testcase):
            testcase.expectCommands(Expect("command2"))
            yield utils.getProcessOutputAndValue("command", ())
            testcase.assertAllCommandsRan()
        result = self.runTestMethod(method)
        self.assertTestFailure(result, "unexpected command run")

    def test_gpoav_wrongArgs(self):
        @defer.inlineCallbacks
        def method(testcase):
            testcase.expectCommands(Expect("command", "arg"))
            yield utils.getProcessOutputAndValue("command", ("otherarg",))
            testcase.assertAllCommandsRan()
        result = self.runTestMethod(method)
        self.assertTestFailure(result, "unexpected command run")

    def test_gpoav_missingPath(self):
        @defer.inlineCallbacks
        def method(testcase):
            testcase.expectCommands(Expect("command", "arg").path("/home"))
            yield utils.getProcessOutputAndValue("command", ("otherarg",))
            testcase.assertAllCommandsRan()
        result = self.runTestMethod(method)
        self.assertTestFailure(result, "unexpected command run")

    def test_gpoav_wrongPath(self):
        @defer.inlineCallbacks
        def method(testcase):
            testcase.expectCommands(Expect("command", "arg").path("/home"))
            yield utils.getProcessOutputAndValue(
                    "command", ("otherarg",), path="/work")
            testcase.assertAllCommandsRan()
        result = self.runTestMethod(method)
        self.assertTestFailure(result, "unexpected command run")

    def test_gpoav_notCurrentPath(self):
        @defer.inlineCallbacks
        def method(testcase):
            testcase.expectCommands(Expect("command", "arg"))
            yield utils.getProcessOutputAndValue(
                    "command", ("otherarg",), path="/work")
            testcase.assertAllCommandsRan()
        result = self.runTestMethod(method)
        self.assertTestFailure(result, "unexpected command run")

    def test_gpoav_errorOutput(self):
        @defer.inlineCallbacks
        def method(testcase):
            testcase.expectCommands(Expect("command").stderr(b"some test"))
            res = yield utils.getProcessOutputAndValue("command", ())
            self.assertEqual(res, (b'', b'some test', 0))
        result = self.runTestMethod(method)
        self.assertSuccessful(result)

    def test_gpoav_exit(self):
        @defer.inlineCallbacks
        def method(testcase):
            testcase.expectCommands(Expect("command").exit(1))
            res = yield utils.getProcessOutputAndValue("command", ())
            self.assertEqual(res, (b'', b'', 1))
        result = self.runTestMethod(method)
        self.assertSuccessful(result)

    def test_gpoav_output(self):
        @defer.inlineCallbacks
        def method(testcase):
            testcase.expectCommands(Expect("command").stdout(b"stdout"))
            res = yield utils.getProcessOutputAndValue("command", ())
            testcase.assertEqual(res, (b"stdout", b'', 0))
        result = self.runTestMethod(method)
        self.assertSuccessful(result)

    def test_gpoav_outputAndError(self):
        @defer.inlineCallbacks
        def method(testcase):
            testcase.expectCommands(
                Expect("command").stdout(b"stdout").stderr(b"stderr"))
            res = yield utils.getProcessOutputAndValue("command", ())
            testcase.assertEqual(res, (b"stdout", b'stderr', 0))

        result = self.runTestMethod(method)
        self.assertSuccessful(result)
