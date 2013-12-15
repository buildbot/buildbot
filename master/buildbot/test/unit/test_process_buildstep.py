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

import mock
import re

from buildbot.process import buildstep
from buildbot.process import properties
from buildbot.process.buildstep import regex_log_evaluator
from buildbot.status.results import EXCEPTION
from buildbot.status.results import FAILURE
from buildbot.status.results import RETRY
from buildbot.status.results import SUCCESS
from buildbot.status.results import WARNINGS
from buildbot.test.fake import fakebuild
from buildbot.test.fake import remotecommand
from buildbot.test.fake import slave
from buildbot.test.util import compat
from buildbot.test.util import config
from buildbot.test.util import steps
from buildbot.util.eventual import eventually
from twisted.internet import defer
from twisted.internet import error
from twisted.python import log
from twisted.trial import unittest


class FakeLogFile:

    def __init__(self, text):
        self.text = text

    def getText(self):
        return self.text


class FakeStepStatus:
    pass


class OldStyleStep(buildstep.BuildStep):

    def start(self):
        pass


class NewStyleStep(buildstep.BuildStep):

    def run(self):
        pass


class TestRegexLogEvaluator(unittest.TestCase):

    def makeRemoteCommand(self, rc, stdout, stderr=''):
        cmd = remotecommand.FakeRemoteCommand('cmd', {})
        cmd.fakeLogData(self, 'stdio', stdout=stdout, stderr=stderr)
        cmd.rc = rc
        return cmd

    def test_find_worse_status(self):
        cmd = self.makeRemoteCommand(0, 'This is a big step')
        step_status = FakeStepStatus()
        r = [(re.compile("This is"), WARNINGS)]
        new_status = regex_log_evaluator(cmd, step_status, r)
        self.assertEqual(new_status, WARNINGS,
                         "regex_log_evaluator returned %d, expected %d"
                         % (new_status, WARNINGS))

    def test_multiple_regexes(self):
        cmd = self.makeRemoteCommand(0, "Normal stdout text\nan error")
        step_status = FakeStepStatus()
        r = [(re.compile("Normal stdout"), SUCCESS),
             (re.compile("error"), FAILURE)]
        new_status = regex_log_evaluator(cmd, step_status, r)
        self.assertEqual(new_status, FAILURE,
                         "regex_log_evaluator returned %d, expected %d"
                         % (new_status, FAILURE))

    def test_exception_not_in_stdout(self):
        cmd = self.makeRemoteCommand(0,
                                     "Completely normal output", "exception output")
        step_status = FakeStepStatus()
        r = [(re.compile("exception"), EXCEPTION)]
        new_status = regex_log_evaluator(cmd, step_status, r)
        self.assertEqual(new_status, EXCEPTION,
                         "regex_log_evaluator returned %d, expected %d"
                         % (new_status, EXCEPTION))

    def test_pass_a_string(self):
        cmd = self.makeRemoteCommand(0, "Output", "Some weird stuff on stderr")
        step_status = FakeStepStatus()
        r = [("weird stuff", WARNINGS)]
        new_status = regex_log_evaluator(cmd, step_status, r)
        self.assertEqual(new_status, WARNINGS,
                         "regex_log_evaluator returned %d, expected %d"
                         % (new_status, WARNINGS))


class TestBuildStep(steps.BuildStepMixin, config.ConfigErrorsMixin, unittest.TestCase):

    class FakeBuildStep(buildstep.BuildStep):

        def start(self):
            eventually(self.finished, 0)

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    # support

    def _setupWaterfallTest(self, hideStepIf, expect, expectedResult=SUCCESS):
        self.setupStep(TestBuildStep.FakeBuildStep(hideStepIf=hideStepIf))
        self.expectOutcome(result=expectedResult, status_text=["generic"])
        self.expectHidden(expect)

    # tests

    def test_nameIsntString(self):
        """
        When BuildStep is passed a name that isn't a string, it reports
        a config error.
        """
        self.assertRaisesConfigError("BuildStep name must be a string",
                                     lambda: buildstep.BuildStep(name=5))

    def test_unexpectedKeywordArgument(self):
        """
        When BuildStep is passed an unknown keyword argument, it reports
        a config error.
        """
        self.assertRaisesConfigError("__init__ got unexpected keyword argument(s) ['oogaBooga']",
                                     lambda: buildstep.BuildStep(oogaBooga=5))

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

    def test_runCommand(self):
        bs = buildstep.BuildStep()
        bs.buildslave = slave.FakeSlave()
        bs.remote = 'dummy'
        cmd = buildstep.RemoteShellCommand("build", ["echo", "hello"])
        cmd.run = lambda self, remote: SUCCESS
        bs.runCommand(cmd)
        self.assertEqual(bs.cmd, cmd)

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
        d.addCallback(lambda _: self.assertTrue(called[0]))
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
        d.addCallback(lambda _: self.assertTrue(called[0]))
        return d

    def test_hideStepIf_fails(self):
        # 0/0 causes DivideByZeroError, which should be flagged as an exception
        self._setupWaterfallTest(lambda: 0 / 0, False, expectedResult=EXCEPTION)
        return self.runStep()

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
        d.addErrback(log.err)
        d.addCallback(lambda _:
                      self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1))
        d.addCallback(lambda _: self.assertTrue(called[0]))
        return d

    def test_describe(self):
        description = ['oogaBooga']
        descriptionDone = ['oogaBooga done!']
        step = buildstep.BuildStep(description=description,
                                   descriptionDone=descriptionDone)
        self.assertEqual(step.describe(), description)
        self.assertEqual(step.describe(done=True), descriptionDone)

        step2 = buildstep.BuildStep()
        self.assertEqual(step2.describe(), [step2.name])
        self.assertEqual(step2.describe(done=True), [step2.name])

    def test_describe_suffix(self):
        description = ['oogaBooga']
        descriptionDone = ['oogaBooga done!']
        descriptionSuffix = ['oogaBooga suffix']

        step = buildstep.BuildStep(description=description,
                                   descriptionDone=descriptionDone,
                                   descriptionSuffix=descriptionSuffix)
        self.assertEqual(step.describe(), description + descriptionSuffix)
        self.assertEqual(step.describe(done=True),
                         descriptionDone + descriptionSuffix)

        step2 = buildstep.BuildStep(descriptionSuffix=descriptionSuffix)
        self.assertEqual(step2.describe(), [step2.name] + descriptionSuffix)
        self.assertEqual(step2.describe(done=True),
                         [step2.name] + descriptionSuffix)

    @defer.inlineCallbacks
    def test_step_renders_flunkOnFailure(self):
        self.setupStep(TestBuildStep.FakeBuildStep(flunkOnFailure=properties.Property('fOF')))
        self.properties.setProperty('fOF', 'yes', 'test')
        self.expectOutcome(result=SUCCESS, status_text=["generic"])
        yield self.runStep()
        self.assertEqual(self.step.flunkOnFailure, 'yes')

    def test_isNewStyle(self):
        self.assertFalse(OldStyleStep().isNewStyle())
        self.assertTrue(NewStyleStep().isNewStyle())


class TestLoggingBuildStep(unittest.TestCase):

    def makeRemoteCommand(self, rc, stdout, stderr=''):
        cmd = remotecommand.FakeRemoteCommand('cmd', {})
        cmd.fakeLogData(self, 'stdio', stdout=stdout, stderr=stderr)
        cmd.rc = rc
        return cmd

    def test_evaluateCommand_success(self):
        cmd = self.makeRemoteCommand(0, "Log text", "Log text")
        lbs = buildstep.LoggingBuildStep()
        status = lbs.evaluateCommand(cmd)
        self.assertEqual(status, SUCCESS, "evaluateCommand returned %d, should've returned %d" % (status, SUCCESS))

    def test_evaluateCommand_failed(self):
        cmd = self.makeRemoteCommand(23, "Log text", "")
        lbs = buildstep.LoggingBuildStep()
        status = lbs.evaluateCommand(cmd)
        self.assertEqual(status, FAILURE, "evaluateCommand returned %d, should've returned %d" % (status, FAILURE))

    def test_evaluateCommand_log_eval_func(self):
        cmd = self.makeRemoteCommand(0, "Log text")

        def eval(cmd, step_status):
            return WARNINGS
        lbs = buildstep.LoggingBuildStep(log_eval_func=eval)
        status = lbs.evaluateCommand(cmd)
        self.assertEqual(status, WARNINGS, "evaluateCommand didn't call log_eval_func or overrode its results")


class FailingCustomStep(buildstep.LoggingBuildStep):

    def __init__(self, exception=buildstep.BuildStepFailed, *args, **kwargs):
        buildstep.LoggingBuildStep.__init__(self, *args, **kwargs)
        self.exception = exception

    @defer.inlineCallbacks
    def start(self):
        yield defer.succeed(None)
        raise self.exception()


class TestCustomStepExecution(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_step_raising_buildstepfailed_in_start(self):
        self.setupStep(FailingCustomStep())
        self.expectOutcome(result=FAILURE, status_text=["generic"])
        return self.runStep()

    def test_step_raising_exception_in_start(self):
        self.setupStep(FailingCustomStep(exception=ValueError))
        self.expectOutcome(result=EXCEPTION, status_text=["generic", "exception"])
        d = self.runStep()

        @d.addCallback
        def cb(_):
            self.assertEqual(len(self.flushLoggedErrors(ValueError)), 1)
        return d

    def test_step_raising_connectionlost_in_start(self):
        self.setupStep(FailingCustomStep(exception=error.ConnectionLost))
        self.expectOutcome(result=RETRY, status_text=["generic", "exception", "slave", "lost"])
        return self.runStep()


class TestRemoteShellCommand(unittest.TestCase):

    def test_obfuscated_arguments(self):
        command = ["echo",
                   ("obfuscated", "real", "fake"),
                   "test",
                   ("obfuscated", "real2", "fake2"),
                   ("not obfuscated", "a", "b"),
                   ("obfuscated"),  # not obfuscated
                   ("obfuscated", "test"),  # not obfuscated
                   ("obfuscated", "1", "2", "3"),  # not obfuscated)
                   ]
        cmd = buildstep.RemoteShellCommand("build", command)
        self.assertEqual(cmd.command, command)
        self.assertEqual(cmd.fake_command, ["echo",
                                            "fake",
                                            "test",
                                            "fake2",
                                            ("not obfuscated", "a", "b"),
                                            ("obfuscated"),  # not obfuscated
                                            ("obfuscated", "test"),  # not obfuscated
                                            ("obfuscated", "1", "2", "3"),  # not obfuscated)
                                            ])

        command = "echo test"
        cmd = buildstep.RemoteShellCommand("build", command)
        self.assertEqual(cmd.command, command)
        self.assertEqual(cmd.fake_command, command)
