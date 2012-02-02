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
import mock
from twisted.trial import unittest
from twisted.internet import reactor
from buildbot.process import buildstep
from buildbot.process.buildstep import regex_log_evaluator
from buildbot.status.results import FAILURE, SUCCESS, WARNINGS, EXCEPTION
from buildbot.test.fake import fakebuild
from buildbot.test.util import steps, compat

class FakeLogFile:
    def __init__(self, text):
        self.text = text

    def getText(self):
        return self.text

class FakeCmd:
    def __init__(self, stdout, stderr, rc=0):
        self.logs = {'stdout': FakeLogFile(stdout),
                     'stderr': FakeLogFile(stderr)}
        self.rc = rc

class FakeStepStatus:
    pass

class TestRegexLogEvaluator(unittest.TestCase):
    def test_find_worse_status(self):
        cmd = FakeCmd("This is log text", "")
        step_status = FakeStepStatus()
        r = [(re.compile("This is"), FAILURE)]
        new_status = regex_log_evaluator(cmd, step_status, r)
        self.assertEqual(new_status, FAILURE, "regex_log_evaluator returned %d, should've returned %d" % (new_status, FAILURE))

    def test_multiple_regexes(self):
        cmd = FakeCmd("Normal stdout text\nan error", "")
        step_status = FakeStepStatus()
        r = [(re.compile("Normal stdout"), SUCCESS),
             (re.compile("error"), FAILURE)]
        new_status = regex_log_evaluator(cmd, step_status, r)
        self.assertEqual(new_status, FAILURE, "regex_log_evaluator returned %d, should've returned %d" % (new_status, FAILURE))

    def test_exception_not_in_stdout(self):
        cmd = FakeCmd("Completely normal output", "exception output")
        step_status = FakeStepStatus()
        r = [(re.compile("exception"), EXCEPTION)]
        new_status = regex_log_evaluator(cmd, step_status, r)
        self.assertEqual(new_status, EXCEPTION, "regex_log_evaluator returned %d, should've returned %d" % (new_status, EXCEPTION))

    def test_pass_a_string(self):
        cmd = FakeCmd("Output", "Some weird stuff on stderr")
        step_status = FakeStepStatus()
        r = [("weird stuff", WARNINGS)]
        new_status = regex_log_evaluator(cmd, step_status, r)
        self.assertEqual(new_status, WARNINGS, "regex_log_evaluator returned %d, should've returned %d" % (new_status, WARNINGS))


class TestBuildStep(steps.BuildStepMixin, unittest.TestCase):

    class FakeBuildStep(buildstep.BuildStep):
        def start(self):
            reactor.callLater(0, self.finished, 0)

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    # support

    def _setupWaterfallTest(self, hideStepIf, expect):
        self.setupStep(TestBuildStep.FakeBuildStep(hideStepIf=hideStepIf))
        self.expectOutcome(result=SUCCESS, status_text=["generic"])
        self.expectHidden(expect)

    # tests

    def test_getProperty(self):
        bs = buildstep.BuildStep()
        bs.build = fakebuild.FakeBuild()
        props = bs.build.build_status.properties = mock.Mock()
        bs.getProperty("xyz", 'b')
        props.getProperty.assert_called_with("xyz", 'b')
        bs.getProperty("xyz")
        props.getProperty.assert_called_with("xyz", None)

    def test_setProperty(self):
        bs = buildstep.BuildStep()
        bs.build = fakebuild.FakeBuild()
        props = bs.build.build_status.properties = mock.Mock()
        bs.setProperty("x", "y", "t")
        props.setProperty.assert_called_with("x", "y", "t", runtime=True)
        bs.setProperty("x", "abc", "test", runtime=True)
        props.setProperty.assert_called_with("x", "abc", "test", runtime=True)

    def test_hideStepIf_False(self):
        self._setupWaterfallTest(False, False)
        return self.runStep()

    def test_hideStepIf_True(self):
        self._setupWaterfallTest(True, True)
        return self.runStep()

    def test_hideStepIf_Callable_False(self):
        called = [False]
        def shouldHide(result, step):
            called[0] = True
            self.assertTrue(step is self.step)
            self.assertEquals(result, SUCCESS)
            return False

        self._setupWaterfallTest(shouldHide, False)

        d = self.runStep()
        d.addCallback(lambda _ : self.assertTrue(called[0]))
        return d

    def test_hideStepIf_Callable_True(self):
        called = [False]
        def shouldHide(result, step):
            called[0] = True
            self.assertTrue(step is self.step)
            self.assertEquals(result, SUCCESS)
            return True

        self._setupWaterfallTest(shouldHide, True)

        d = self.runStep()
        d.addCallback(lambda _ : self.assertTrue(called[0]))
        return d

    @compat.usesFlushLoggedErrors
    def test_hideStepIf_Callable_Exception(self):
        called = [False]
        def shouldHide(result, step):
            called[0] = True
            self.assertTrue(step is self.step)
            self.assertEquals(result, EXCEPTION)
            return True

        def createException(*args, **kwargs):
            raise RuntimeError()

        self.setupStep(self.FakeBuildStep(hideStepIf=shouldHide,
                                          doStepIf=createException))
        self.expectOutcome(result=EXCEPTION,
                status_text=['generic', 'exception'])
        self.expectHidden(True)

        d = self.runStep()
        d.addCallback(lambda _ :
            self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1))
        d.addCallback(lambda _ : self.assertTrue(called[0]))
        return d


class TestLoggingBuildStep(unittest.TestCase):
    def test_evaluateCommand_success(self):
        cmd = FakeCmd("Log text", "Log text")
        lbs = buildstep.LoggingBuildStep()
        status = lbs.evaluateCommand(cmd)
        self.assertEqual(status, SUCCESS, "evaluateCommand returned %d, should've returned %d" % (status, SUCCESS))

    def test_evaluateCommand_failed(self):
        cmd = FakeCmd("Log text", "", 23)
        lbs = buildstep.LoggingBuildStep()
        status = lbs.evaluateCommand(cmd)
        self.assertEqual(status, FAILURE, "evaluateCommand returned %d, should've returned %d" % (status, FAILURE))

    def test_evaluateCommand_log_eval_func(self):
        cmd = FakeCmd("Log text", "")
        def eval(cmd, step_status):
            return WARNINGS
        lbs = buildstep.LoggingBuildStep(log_eval_func=eval)
        status = lbs.evaluateCommand(cmd)
        self.assertEqual(status, WARNINGS, "evaluateCommand didn't call log_eval_func or overrode its results")
