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
from future.utils import itervalues

import mock

from buildbot import locks
from buildbot.interfaces import BuildSlaveTooOldError
from buildbot.process import buildstep
from buildbot.process import properties
from buildbot.process import remotecommand
from buildbot.process.properties import renderer
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SKIPPED
from buildbot.process.results import SUCCESS
from buildbot.test.fake import fakebuild
from buildbot.test.fake import fakemaster
from buildbot.test.fake import remotecommand as fakeremotecommand
from buildbot.test.fake import slave
from buildbot.test.fake.remotecommand import Expect
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.util import config
from buildbot.test.util import interfaces
from buildbot.test.util import steps
from buildbot.util.eventual import eventually
from twisted.internet import defer
from twisted.internet import task
from twisted.python import log
from twisted.trial import unittest


class OldStyleStep(buildstep.BuildStep):

    def start(self):
        pass


class NewStyleStep(buildstep.BuildStep):

    def run(self):
        pass


class TestBuildStep(steps.BuildStepMixin, config.ConfigErrorsMixin, unittest.TestCase):

    class FakeBuildStep(buildstep.BuildStep):

        def start(self):
            eventually(self.finished, 0)

    class SkippingBuildStep(buildstep.BuildStep):

        def start(self):
            return SKIPPED

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    # support

    def _setupWaterfallTest(self, hideStepIf, expect, expectedResult=SUCCESS):
        self.setupStep(TestBuildStep.FakeBuildStep(hideStepIf=hideStepIf))
        self.expectOutcome(result=expectedResult)
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
        self.assertRaisesConfigError(
            "__init__ got unexpected keyword argument(s) ['oogaBooga']",
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

    @defer.inlineCallbacks
    def test_renderableLocks(self):
        lock1 = mock.Mock(spec=locks.MasterLock)
        lock1.name = "masterlock"

        lock2 = mock.Mock(spec=locks.SlaveLock)
        lock2.name = "slavelock"

        renderedLocks = [False]

        @renderer
        def rendered_locks(props):
            renderedLocks[0] = True
            access1 = locks.LockAccess(lock1, 'counting')
            access2 = locks.LockAccess(lock2, 'exclusive')
            return [access1, access2]

        self.setupStep(self.FakeBuildStep(locks=rendered_locks))
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()

        self.assertTrue(renderedLocks[0])

    @defer.inlineCallbacks
    def test_regularLocks(self):
        lock1 = mock.Mock(spec=locks.MasterLock)
        lock1.name = "masterlock"

        lock2 = mock.Mock(spec=locks.SlaveLock)
        lock2.name = "slavelock"

        self.setupStep(self.FakeBuildStep(locks=[locks.LockAccess(lock1, 'counting'), locks.LockAccess(lock2, 'exclusive')]))
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()

    @defer.inlineCallbacks
    def test_runCommand(self):
        bs = buildstep.BuildStep()
        bs.buildslave = slave.FakeSlave(master=None)  # master is not used here
        bs.remote = 'dummy'
        bs.build = fakebuild.FakeBuild()
        bs.build.builder.name = 'fake'
        cmd = remotecommand.RemoteShellCommand("build", ["echo", "hello"])

        def run(*args, **kwargs):
            # check that runCommand sets step.cmd
            self.assertIdentical(bs.cmd, cmd)
            return SUCCESS
        cmd.run = run
        yield bs.runCommand(cmd)
        # check that step.cmd is cleared after the command runs
        self.assertEqual(bs.cmd, None)

    @defer.inlineCallbacks
    def test_start_returns_SKIPPED(self):
        self.setupStep(self.SkippingBuildStep())
        self.step.finished = mock.Mock()
        self.expectOutcome(result=SKIPPED, state_string=u'finished (skipped)')
        yield self.runStep()
        # 837: we want to specifically avoid calling finished() if skipping
        self.step.finished.assert_not_called()

    @defer.inlineCallbacks
    def test_doStepIf_false(self):
        self.setupStep(self.FakeBuildStep(doStepIf=False))
        self.step.finished = mock.Mock()
        self.expectOutcome(result=SKIPPED, state_string=u'finished (skipped)')
        yield self.runStep()
        # 837: we want to specifically avoid calling finished() if skipping
        self.step.finished.assert_not_called()

    @defer.inlineCallbacks
    def test_doStepIf_returns_false(self):
        self.setupStep(self.FakeBuildStep(doStepIf=lambda step: False))
        self.step.finished = mock.Mock()
        self.expectOutcome(result=SKIPPED, state_string=u'finished (skipped)')
        yield self.runStep()
        # 837: we want to specifically avoid calling finished() if skipping
        self.step.finished.assert_not_called()

    @defer.inlineCallbacks
    def test_doStepIf_returns_deferred_false(self):
        self.setupStep(self.FakeBuildStep(
            doStepIf=lambda step: defer.succeed(False)))
        self.step.finished = mock.Mock()
        self.expectOutcome(result=SKIPPED, state_string=u'finished (skipped)')
        yield self.runStep()
        # 837: we want to specifically avoid calling finished() if skipping
        self.step.finished.assert_not_called()

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

    @defer.inlineCallbacks
    def test_hideStepIf_fails(self):
        # 0/0 causes DivideByZeroError, which should be flagged as an exception

        self._setupWaterfallTest(
            lambda x, y: 0 / 0, False, expectedResult=EXCEPTION)
        self.step.addLogWithFailure = mock.Mock()
        yield self.runStep()
        self.assertEqual(len(self.flushLoggedErrors(ZeroDivisionError)), 1)

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
                           state_string='finished (exception)')
        self.expectHidden(True)

        d = self.runStep()
        d.addErrback(log.err)
        d.addCallback(lambda _:
                      self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1))
        d.addCallback(lambda _: self.assertTrue(called[0]))
        return d

    @defer.inlineCallbacks
    def test_step_getLog(self):
        testcase = self

        class TestGetLogStep(buildstep.BuildStep):

            @defer.inlineCallbacks
            def run(self):
                testcase.assertRaises(KeyError, lambda:
                                      self.getLog('testy'))
                log1 = yield self.addLog('testy')
                log2 = self.getLog('testy')
                testcase.assertIdentical(log1, log2)
                defer.returnValue(SUCCESS)
        self.setupStep(TestGetLogStep())
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()

    @defer.inlineCallbacks
    def test_step_renders_flunkOnFailure(self):
        self.setupStep(
            TestBuildStep.FakeBuildStep(flunkOnFailure=properties.Property('fOF')))
        self.properties.setProperty('fOF', 'yes', 'test')
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()
        self.assertEqual(self.step.flunkOnFailure, 'yes')

    def test_hasStatistic(self):
        step = buildstep.BuildStep()
        self.assertFalse(step.hasStatistic('rbi'))
        step.setStatistic('rbi', 13)
        self.assertTrue(step.hasStatistic('rbi'))

    def test_setStatistic(self):
        step = buildstep.BuildStep()
        step.setStatistic('rbi', 13)
        self.assertEqual(step.getStatistic('rbi'), 13)

    def test_getStatistic(self):
        step = buildstep.BuildStep()
        self.assertEqual(step.getStatistic('rbi', 99), 99)
        self.assertEqual(step.getStatistic('rbi'), None)
        step.setStatistic('rbi', 13)
        self.assertEqual(step.getStatistic('rbi'), 13)

    def test_getStatistics(self):
        step = buildstep.BuildStep()
        step.setStatistic('rbi', 13)
        step.setStatistic('ba', 0.298)
        self.assertEqual(step.getStatistics(), {'rbi': 13, 'ba': 0.298})

    def test_isNewStyle(self):
        self.assertFalse(OldStyleStep().isNewStyle())
        self.assertTrue(NewStyleStep().isNewStyle())

    def setup_summary_test(self):
        self.clock = task.Clock()
        self.patch(NewStyleStep, 'getCurrentSummary',
                   lambda self: defer.succeed({'step': u'C'}))
        self.patch(NewStyleStep, 'getResultSummary',
                   lambda self: defer.succeed({'step': u'CS', 'build': u'CB'}))
        step = NewStyleStep()
        step.updateSummary._reactor = self.clock
        step.master = fakemaster.make_master(testcase=self,
                                             wantData=True, wantDb=True)
        step.stepid = 13
        step.step_status = mock.Mock()
        return step

    def test_updateSummary_running(self):
        step = self.setup_summary_test()
        step._running = True
        step.updateSummary()
        self.clock.advance(1)
        self.assertEqual(step.master.data.updates.stepStateString[13], u'C')

    def test_updateSummary_running_empty_dict(self):
        step = self.setup_summary_test()
        step.getCurrentSummary = lambda: {}
        step._running = True
        step.updateSummary()
        self.clock.advance(1)
        self.assertEqual(step.master.data.updates.stepStateString[13],
                         u'finished')

    def test_updateSummary_running_not_unicode(self):
        step = self.setup_summary_test()
        step.getCurrentSummary = lambda: {'step': 'bytestring'}
        step._running = True
        step.updateSummary()
        self.clock.advance(1)
        self.assertEqual(len(self.flushLoggedErrors(TypeError)), 1)

    def test_updateSummary_running_not_dict(self):
        step = self.setup_summary_test()
        step.getCurrentSummary = lambda: 'foo!'
        step._running = True
        step.updateSummary()
        self.clock.advance(1)
        self.assertEqual(len(self.flushLoggedErrors(TypeError)), 1)

    def test_updateSummary_finished(self):
        step = self.setup_summary_test()
        step._running = False
        step.updateSummary()
        self.clock.advance(1)
        self.assertEqual(step.master.data.updates.stepStateString[13], u'CS')

    def test_updateSummary_finished_empty_dict(self):
        step = self.setup_summary_test()
        step.getResultSummary = lambda: {}
        step._running = False
        step.updateSummary()
        self.clock.advance(1)
        self.assertEqual(step.master.data.updates.stepStateString[13],
                         u'finished')

    def test_updateSummary_finished_not_dict(self):
        step = self.setup_summary_test()
        step.getResultSummary = lambda: 'foo!'
        step._running = False
        step.updateSummary()
        self.clock.advance(1)
        self.assertEqual(len(self.flushLoggedErrors(TypeError)), 1)

    @defer.inlineCallbacks
    def test_updateSummary_old_style(self):
        self.setupStep(OldStyleStep())
        self.step.start = lambda: self.step.updateSummary()
        self.expectOutcome(result=EXCEPTION)
        yield self.runStep()
        self.assertEqual(len(self.flushLoggedErrors(AssertionError)), 1)

    def checkSummary(self, got, step, build=None):
        self.failUnless(all(isinstance(k, unicode) for k in got))
        self.failUnless(all(isinstance(k, unicode) for k in itervalues(got)))
        exp = {u'step': step}
        if build:
            exp[u'build'] = build
        self.assertEqual(got, exp)

    def test_getCurrentSummary(self):
        st = buildstep.BuildStep()
        st.description = None
        self.checkSummary(st.getCurrentSummary(), u'running')

    def test_getCurrentSummary_description(self):
        st = buildstep.BuildStep()
        st.description = 'fooing'
        self.checkSummary(st.getCurrentSummary(), u'fooing')

    def test_getCurrentSummary_descriptionSuffix(self):
        st = buildstep.BuildStep()
        st.description = 'fooing'
        st.descriptionSuffix = 'bar'
        self.checkSummary(st.getCurrentSummary(), u'fooing bar')

    def test_getCurrentSummary_description_list(self):
        st = buildstep.BuildStep()
        st.description = ['foo', 'ing']
        self.checkSummary(st.getCurrentSummary(), u'foo ing')

    def test_getCurrentSummary_descriptionSuffix_list(self):
        st = buildstep.BuildStep()
        st.results = SUCCESS
        st.description = ['foo', 'ing']
        st.descriptionSuffix = ['bar', 'bar2']
        self.checkSummary(st.getCurrentSummary(), u'foo ing bar bar2')

    def test_getResultSummary(self):
        st = buildstep.BuildStep()
        st.results = SUCCESS
        st.description = None
        self.checkSummary(st.getResultSummary(), u'finished')

    def test_getResultSummary_description(self):
        st = buildstep.BuildStep()
        st.results = SUCCESS
        st.description = 'fooing'
        self.checkSummary(st.getResultSummary(), u'fooing')

    def test_getResultSummary_descriptionDone(self):
        st = buildstep.BuildStep()
        st.results = SUCCESS
        st.description = 'fooing'
        st.descriptionDone = 'fooed'
        self.checkSummary(st.getResultSummary(), u'fooed')

    def test_getResultSummary_descriptionSuffix(self):
        st = buildstep.BuildStep()
        st.results = SUCCESS
        st.description = 'fooing'
        st.descriptionSuffix = 'bar'
        self.checkSummary(st.getResultSummary(), u'fooing bar')

    def test_getResultSummary_descriptionDone_and_Suffix(self):
        st = buildstep.BuildStep()
        st.results = SUCCESS
        st.descriptionDone = 'fooed'
        st.descriptionSuffix = 'bar'
        self.checkSummary(st.getResultSummary(), u'fooed bar')

    def test_getResultSummary_description_list(self):
        st = buildstep.BuildStep()
        st.results = SUCCESS
        st.description = ['foo', 'ing']
        self.checkSummary(st.getResultSummary(), u'foo ing')

    def test_getResultSummary_descriptionSuffix_list(self):
        st = buildstep.BuildStep()
        st.results = SUCCESS
        st.description = ['foo', 'ing']
        st.descriptionSuffix = ['bar', 'bar2']
        self.checkSummary(st.getResultSummary(), u'foo ing bar bar2')

    def test_getResultSummary_descriptionSuffix_failure(self):
        st = buildstep.BuildStep()
        st.results = FAILURE
        st.description = 'fooing'
        self.checkSummary(st.getResultSummary(), u'fooing (failure)')

    # Test calling checkSlaveHasCommand() when buildslave have support for
    # requested remote command.
    def testcheckSlaveHasCommandGood(self):
        # patch BuildStep.slaveVersion() to return success
        mockedSlaveVersion = mock.Mock()
        self.patch(buildstep.BuildStep, "slaveVersion", mockedSlaveVersion)

        # check that no exceptions are raised
        buildstep.BuildStep().checkSlaveHasCommand("foo")

        # make sure slaveVersion() was called with correct arguments
        mockedSlaveVersion.assert_called_once_with("foo")

    # Test calling checkSlaveHasCommand() when buildslave is to old to support
    # requested remote command.
    def testcheckSlaveHasCommandTooOld(self):
        # patch BuildStep.slaveVersion() to return error
        self.patch(buildstep.BuildStep,
                   "slaveVersion",
                   mock.Mock(return_value=None))

        # make sure appropriate exception is raised
        step = buildstep.BuildStep()
        self.assertRaisesRegexp(BuildSlaveTooOldError,
                                "slave is too old, does not know about foo",
                                step.checkSlaveHasCommand, "foo")


class TestLoggingBuildStep(unittest.TestCase):

    def makeRemoteCommand(self, rc, stdout, stderr=''):
        cmd = fakeremotecommand.FakeRemoteCommand('cmd', {})
        cmd.fakeLogData(self, 'stdio', stdout=stdout, stderr=stderr)
        cmd.rc = rc
        return cmd

    def test_evaluateCommand_success(self):
        cmd = self.makeRemoteCommand(0, "Log text", "Log text")
        lbs = buildstep.LoggingBuildStep()
        status = lbs.evaluateCommand(cmd)
        self.assertEqual(
            status, SUCCESS, "evaluateCommand returned %d, should've returned %d" %
            (status, SUCCESS))

    def test_evaluateCommand_failed(self):
        cmd = self.makeRemoteCommand(23, "Log text", "")
        lbs = buildstep.LoggingBuildStep()
        status = lbs.evaluateCommand(cmd)
        self.assertEqual(
            status, FAILURE, "evaluateCommand returned %d, should've returned %d" %
            (status, FAILURE))


class InterfaceTests(interfaces.InterfaceTests):

    # ensure that steps.BuildStepMixin creates a convincing facsimile of the
    # real BuildStep

    def test_signature_attributes(self):
        for attr in [
            'name',
            'description',
            'descriptionDone',
            'descriptionSuffix',
            'locks',
            'progressMetrics',
            'useProgress',
            'doStepIf',
            'hideStepIf',
            'haltOnFailure',
            'flunkOnWarnings',
            'flunkOnFailure',
            'warnOnWarnings',
            'warnOnFailure',
            'alwaysRun',
            'build',
            'buildslave',
            'step_status',
            'progress',
            'stopped',
        ]:
            self.failUnless(hasattr(self.step, attr))

    def test_signature_setBuild(self):
        @self.assertArgSpecMatches(self.step.setBuild)
        def setBuild(self, build):
            pass

    def test_signature_setBuildSlave(self):
        @self.assertArgSpecMatches(self.step.setBuildSlave)
        def setBuildSlave(self, buildslave):
            pass

    def test_signature_setupProgress(self):
        @self.assertArgSpecMatches(self.step.setupProgress)
        def setupProgress(self):
            pass

    def test_signature_startStep(self):
        @self.assertArgSpecMatches(self.step.startStep)
        def startStep(self, remote):
            pass

    def test_signature_run(self):
        @self.assertArgSpecMatches(self.step.run)
        def run(self):
            pass

    def test_signature_start(self):
        @self.assertArgSpecMatches(self.step.start)
        def start(self):
            pass

    def test_signature_finished(self):
        @self.assertArgSpecMatches(self.step.finished)
        def finished(self, results):
            pass

    def test_signature_failed(self):
        @self.assertArgSpecMatches(self.step.failed)
        def failed(self, why):
            pass

    def test_signature_interrupt(self):
        @self.assertArgSpecMatches(self.step.interrupt)
        def interrupt(self, reason):
            pass

    def test_signature_describe(self):
        @self.assertArgSpecMatches(self.step.describe)
        def describe(self, done=False):
            pass

    def test_signature_setProgress(self):
        @self.assertArgSpecMatches(self.step.setProgress)
        def setProgress(self, metric, value):
            pass

    def test_signature_slaveVersion(self):
        @self.assertArgSpecMatches(self.step.slaveVersion)
        def slaveVersion(self, command, oldversion=None):
            pass

    def test_signature_slaveVersionIsOlderThan(self):
        @self.assertArgSpecMatches(self.step.slaveVersionIsOlderThan)
        def slaveVersionIsOlderThan(self, command, minversion):
            pass

    def test_signature_getSlaveName(self):
        @self.assertArgSpecMatches(self.step.getSlaveName)
        def getSlaveName(self):
            pass

    def test_signature_runCommand(self):
        @self.assertArgSpecMatches(self.step.runCommand)
        def runCommand(self, command):
            pass

    def test_signature_addURL(self):
        @self.assertArgSpecMatches(self.step.addURL)
        def addURL(self, name, url):
            pass

    def test_signature_addLog(self):
        @self.assertArgSpecMatches(self.step.addLog)
        def addLog(self, name, type='s', logEncoding=None):
            pass

    def test_signature_getLog(self):
        @self.assertArgSpecMatches(self.step.getLog)
        def getLog(self, name):
            pass

    def test_signature_addCompleteLog(self):
        @self.assertArgSpecMatches(self.step.addCompleteLog)
        def addCompleteLog(self, name, text):
            pass

    def test_signature_addHTMLLog(self):
        @self.assertArgSpecMatches(self.step.addHTMLLog)
        def addHTMLLog(self, name, html):
            pass

    def test_signature_addLogObserver(self):
        @self.assertArgSpecMatches(self.step.addLogObserver)
        def addLogObserver(self, logname, observer):
            pass


class TestFakeItfc(unittest.TestCase,
                   steps.BuildStepMixin, InterfaceTests):

    def setUp(self):
        self.setupStep(buildstep.BuildStep())


class TestRealItfc(unittest.TestCase,
                   InterfaceTests):

    def setUp(self):
        self.step = buildstep.BuildStep()


class CommandMixinExample(buildstep.CommandMixin, buildstep.BuildStep):

    @defer.inlineCallbacks
    def run(self):
        rv = yield self.testMethod()
        self.method_return_value = rv
        defer.returnValue(SUCCESS)


class TestCommandMixin(steps.BuildStepMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        yield self.setUpBuildStep()
        self.step = CommandMixinExample()
        self.setupStep(self.step)

    def tearDown(self):
        return self.tearDownBuildStep()

    @defer.inlineCallbacks
    def test_runRmdir(self):
        self.step.testMethod = lambda: self.step.runRmdir('/some/path')
        self.expectCommands(
            Expect('rmdir', {'dir': '/some/path', 'logEnviron': False})
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()
        self.assertTrue(self.step.method_return_value)

    @defer.inlineCallbacks
    def test_runMkdir(self):
        self.step.testMethod = lambda: self.step.runMkdir('/some/path')
        self.expectCommands(
            Expect('mkdir', {'dir': '/some/path', 'logEnviron': False})
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()
        self.assertTrue(self.step.method_return_value)

    @defer.inlineCallbacks
    def test_runMkdir_fails(self):
        self.step.testMethod = lambda: self.step.runMkdir('/some/path')
        self.expectCommands(
            Expect('mkdir', {'dir': '/some/path', 'logEnviron': False})
            + 1,
        )
        self.expectOutcome(result=FAILURE)
        yield self.runStep()

    @defer.inlineCallbacks
    def test_runMkdir_fails_no_abandon(self):
        self.step.testMethod = lambda: self.step.runMkdir(
            '/some/path', abandonOnFailure=False)
        self.expectCommands(
            Expect('mkdir', {'dir': '/some/path', 'logEnviron': False})
            + 1,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()
        self.assertFalse(self.step.method_return_value)

    @defer.inlineCallbacks
    def test_pathExists(self):
        self.step.testMethod = lambda: self.step.pathExists('/some/path')
        self.expectCommands(
            Expect('stat', {'file': '/some/path', 'logEnviron': False})
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()
        self.assertTrue(self.step.method_return_value)

    @defer.inlineCallbacks
    def test_pathExists_doesnt(self):
        self.step.testMethod = lambda: self.step.pathExists('/some/path')
        self.expectCommands(
            Expect('stat', {'file': '/some/path', 'logEnviron': False})
            + 1,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()
        self.assertFalse(self.step.method_return_value)

    @defer.inlineCallbacks
    def test_pathExists_logging(self):
        self.step.testMethod = lambda: self.step.pathExists('/some/path')
        self.expectCommands(
            Expect('stat', {'file': '/some/path', 'logEnviron': False})
            + Expect.log('stdio', header='NOTE: never mind\n')
            + 1,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()
        self.assertFalse(self.step.method_return_value)
        self.assertEqual(self.step.getLog('stdio').header,
                         'NOTE: never mind\n')

    def test_glob(self):
        @defer.inlineCallbacks
        def testFunc():
            res = yield self.step.glob("*.pyc")
            self.assertEqual(res, ["one.pyc", "two.pyc"])
        self.step.testMethod = testFunc
        self.expectCommands(
            Expect('glob', {'glob': '*.pyc', 'logEnviron': False})
            + Expect.update('files', ["one.pyc", "two.pyc"])
            + 0
        )
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_glob_empty(self):
        self.step.testMethod = lambda: self.step.glob("*.pyc")
        self.expectCommands(
            Expect('glob', {'glob': '*.pyc', 'logEnviron': False})
            + Expect.update('files', [])
            + 0
        )
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_glob_fail(self):
        self.step.testMethod = lambda: self.step.glob("*.pyc")
        self.expectCommands(
            Expect('glob', {'glob': '*.pyc', 'logEnviron': False})
            + 1
        )
        self.expectOutcome(result=FAILURE)
        return self.runStep()


class ShellMixinExample(buildstep.ShellMixin, buildstep.BuildStep):
    # note that this is straight out of cls-buildsteps.rst

    def __init__(self, cleanupScript='./cleanup.sh', **kwargs):
        self.cleanupScript = cleanupScript
        kwargs = self.setupShellMixin(kwargs, prohibitArgs=['command'])
        buildstep.BuildStep.__init__(self, **kwargs)

    @defer.inlineCallbacks
    def run(self):
        cmd = yield self.makeRemoteShellCommand(
            command=[self.cleanupScript])
        yield self.runCommand(cmd)
        if cmd.didFail():
            cmd = yield self.makeRemoteShellCommand(
                command=[self.cleanupScript, '--force'],
                logEnviron=False)
            yield self.runCommand(cmd)
        defer.returnValue(cmd.results())


class SimpleShellCommand(buildstep.ShellMixin, buildstep.BuildStep):

    def __init__(self, makeRemoteShellCommandKwargs=None, **kwargs):
        self.makeRemoteShellCommandKwargs = makeRemoteShellCommandKwargs or {}

        kwargs = self.setupShellMixin(kwargs)
        buildstep.BuildStep.__init__(self, **kwargs)

    @defer.inlineCallbacks
    def run(self):
        cmd = yield self.makeRemoteShellCommand(**self.makeRemoteShellCommandKwargs)
        yield self.runCommand(cmd)
        defer.returnValue(cmd.results())


class TestShellMixin(steps.BuildStepMixin,
                     config.ConfigErrorsMixin,
                     unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        yield self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_setupShellMixin_bad_arg(self):
        mixin = ShellMixinExample()
        self.assertRaisesConfigError(
            "invalid ShellMixinExample argument invarg",
            lambda: mixin.setupShellMixin({'invarg': 13}))

    def test_setupShellMixin_prohibited_arg(self):
        mixin = ShellMixinExample()
        self.assertRaisesConfigError(
            "invalid ShellMixinExample argument logfiles",
            lambda: mixin.setupShellMixin({'logfiles': None},
                                          prohibitArgs=['logfiles']))

    def test_setupShellMixin_not_new_style(self):
        self.patch(ShellMixinExample, 'isNewStyle', lambda self: False)
        self.assertRaises(AssertionError, lambda: ShellMixinExample())

    def test_constructor_defaults(self):
        class MySubclass(ShellMixinExample):
            timeout = 9999
        # ShellMixin arg
        self.assertEqual(MySubclass().timeout, 9999)
        self.assertEqual(MySubclass(timeout=88).timeout, 88)
        # BuildStep arg
        self.assertEqual(MySubclass().logEncoding, None)
        self.assertEqual(MySubclass(logEncoding='latin-1').logEncoding,
                         'latin-1')
        self.assertEqual(MySubclass().description, None)
        self.assertEqual(MySubclass(description='charming').description,
                         ['charming'])

    @defer.inlineCallbacks
    def test_example(self):
        self.setupStep(ShellMixinExample(), wantDefaultWorkdir=False)
        self.expectCommands(
            ExpectShell(workdir='build', command=['./cleanup.sh'])
            + Expect.log('stdio', stderr="didn't go so well\n")
            + 1,
            ExpectShell(workdir='build', command=['./cleanup.sh', '--force'],
                        logEnviron=False)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()

    @defer.inlineCallbacks
    def test_example_extra_logfile(self):
        self.setupStep(ShellMixinExample(logfiles={'cleanup': 'cleanup.log'}), wantDefaultWorkdir=False)
        self.expectCommands(
            ExpectShell(workdir='build', command=['./cleanup.sh'],
                        logfiles={'cleanup': 'cleanup.log'})
            + Expect.log('cleanup', stdout='cleaning\ncleaned\n')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()
        self.assertEqual(self.step.getLog('cleanup').stdout,
                         u'cleaning\ncleaned\n')

    @defer.inlineCallbacks
    def test_example_build_workdir(self):
        self.setupStep(ShellMixinExample(), wantDefaultWorkdir=False)
        self.build.workdir = '/alternate'
        self.expectCommands(
            ExpectShell(workdir='/alternate', command=['./cleanup.sh'])
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()

    @defer.inlineCallbacks
    def test_example_step_workdir(self):
        self.setupStep(ShellMixinExample(workdir='/alternate'))
        self.build.workdir = '/overridden'
        self.expectCommands(
            ExpectShell(workdir='/alternate', command=['./cleanup.sh'])
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()

    @defer.inlineCallbacks
    def test_example_step_renderable_workdir(self):
        @renderer
        def rendered_workdir(_):
            return '/alternate'

        self.setupStep(ShellMixinExample(workdir=rendered_workdir))
        self.build.workdir = '/overridden'
        self.expectCommands(
            ExpectShell(workdir='/alternate', command=['./cleanup.sh'])
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()

    @defer.inlineCallbacks
    def test_example_override_workdir(self):
        # Test that makeRemoteShellCommand(workdir=X) works.
        self.setupStep(SimpleShellCommand(
            makeRemoteShellCommandKwargs={'workdir': '/alternate'},
            command=['foo', properties.Property('bar', 'BAR')]))
        self.expectCommands(
            ExpectShell(workdir='/alternate', command=['foo', 'BAR'])
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()

    @defer.inlineCallbacks
    def test_example_env(self):
        self.setupStep(ShellMixinExample(env={'BAR': 'BAR'}), wantDefaultWorkdir=False)
        self.build.builder.config.env = {'FOO': 'FOO'}
        self.expectCommands(
            ExpectShell(workdir='build', command=['./cleanup.sh'],
                        env={'FOO': 'FOO', 'BAR': 'BAR'})
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()

    @defer.inlineCallbacks
    def test_example_old_slave(self):
        self.setupStep(ShellMixinExample(usePTY=False, interruptSignal='DIE'),
                       slave_version={'*': "1.1"}, wantDefaultWorkdir=False)
        self.expectCommands(
            ExpectShell(workdir='build', command=['./cleanup.sh'])
            # note missing parameters
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()
        self.assertEqual(self.step.getLog('stdio').header,
                         u'NOTE: slave does not allow master to override usePTY\n'
                         'NOTE: slave does not allow master to specify interruptSignal\n')

    @defer.inlineCallbacks
    def test_description(self):
        self.setupStep(SimpleShellCommand(
            command=['foo', properties.Property('bar', 'BAR')]), wantDefaultWorkdir=False)
        self.expectCommands(
            ExpectShell(workdir='build', command=['foo', 'BAR'])
            + 0,
        )
        self.expectOutcome(result=SUCCESS, state_string=u"'foo BAR'")
        yield self.runStep()

    def test_getResultSummary(self):
        self.setupStep(SimpleShellCommand(command=['a', ['b', 'c']]))
        self.assertEqual(self.step.getResultSummary(), {u'step': u"'a b ...'"})
