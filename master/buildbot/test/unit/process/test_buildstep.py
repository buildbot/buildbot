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

from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet.task import deferLater
from twisted.python import log
from twisted.trial import unittest

from buildbot import locks
from buildbot.interfaces import WorkerSetupError
from buildbot.plugins import util
from buildbot.process import buildstep
from buildbot.process import properties
from buildbot.process import remotecommand
from buildbot.process.properties import renderer
from buildbot.process.results import ALL_RESULTS
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SKIPPED
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.test.fake import fakebuild
from buildbot.test.fake import fakemaster
from buildbot.test.fake import worker
from buildbot.test.fake.remotecommand import Expect
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.util import config
from buildbot.test.util import interfaces
from buildbot.test.util import steps
from buildbot.test.util.misc import TestReactorMixin
from buildbot.util.eventual import eventually


class NewStyleStep(buildstep.BuildStep):

    def run(self):
        pass


class CustomActionBuildStep(buildstep.BuildStep):
    # The caller is expected to set the action attribute on the step
    def run(self):
        return self.action()


class TestBuildStep(steps.BuildStepMixin, config.ConfigErrorsMixin,
                    TestReactorMixin,
                    unittest.TestCase):

    class FakeBuildStep(buildstep.BuildStep):

        def run(self):
            d = defer.Deferred()
            eventually(d.callback, 0)  # FIXME: this uses real reactor instead of fake one
            return d

    class SkippingBuildStep(buildstep.BuildStep):

        def run(self):
            return SKIPPED

    def setUp(self):
        self.setUpTestReactor()
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
        with self.assertRaisesConfigError("BuildStep name must be a string"):
            buildstep.BuildStep(name=5)

    def test_unexpectedKeywordArgument(self):
        """
        When BuildStep is passed an unknown keyword argument, it reports
        a config error.
        """
        with self.assertRaisesConfigError(
                "__init__ got unexpected keyword argument(s) ['oogaBooga']"):
            buildstep.BuildStep(oogaBooga=5)

    def test_updateBuildSummaryPolicyDefaults(self):
        """
        updateBuildSummaryPolicy builds default value according to resultsMixin
        parameters (flunkOnFailure..)
        """
        step = buildstep.BuildStep()
        self.assertEqual(sorted(step.updateBuildSummaryPolicy), sorted([
            EXCEPTION, RETRY, CANCELLED, FAILURE]))

        step = buildstep.BuildStep(warnOnWarnings=True)
        self.assertEqual(sorted(step.updateBuildSummaryPolicy), sorted([
            EXCEPTION, RETRY, CANCELLED, FAILURE, WARNINGS]))

        step = buildstep.BuildStep(flunkOnFailure=False)
        self.assertEqual(sorted(step.updateBuildSummaryPolicy), sorted([
            EXCEPTION, RETRY, CANCELLED]))

        step = buildstep.BuildStep(updateBuildSummaryPolicy=False)
        self.assertEqual(sorted(step.updateBuildSummaryPolicy), [])

        step = buildstep.BuildStep(updateBuildSummaryPolicy=True)
        self.assertEqual(sorted(step.updateBuildSummaryPolicy),
                         sorted(ALL_RESULTS))

    def test_updateBuildSummaryPolicyBadType(self):
        """
        updateBuildSummaryPolicy raise ConfigError in case of bad type
        """
        with self.assertRaisesConfigError("BuildStep updateBuildSummaryPolicy must be "
                                          "a list of result ids or boolean but it is 2"):
            buildstep.BuildStep(updateBuildSummaryPolicy=FAILURE)

    def test_getProperty(self):
        bs = buildstep.BuildStep()
        bs.build = fakebuild.FakeBuild()
        props = bs.build.properties = mock.Mock()
        bs.getProperty("xyz", 'b')
        props.getProperty.assert_called_with("xyz", 'b')
        bs.getProperty("xyz")
        props.getProperty.assert_called_with("xyz", None)

    def test_setProperty(self):
        bs = buildstep.BuildStep()
        bs.build = fakebuild.FakeBuild()
        props = bs.build.properties = mock.Mock()
        bs.setProperty("x", "y", "t")
        props.setProperty.assert_called_with("x", "y", "t", runtime=True)
        bs.setProperty("x", "abc", "test", runtime=True)
        props.setProperty.assert_called_with("x", "abc", "test", runtime=True)

    @defer.inlineCallbacks
    def test_renderableLocks(self):
        lock1 = locks.MasterLock("masterlock")
        lock2 = locks.WorkerLock("workerlock")

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

    def test_compare(self):
        lbs1 = buildstep.BuildStep(name="me")
        lbs2 = buildstep.BuildStep(name="me")
        lbs3 = buildstep.BuildStep(name="me2")
        self.assertEqual(lbs1, lbs2)
        self.assertNotEqual(lbs1, lbs3)

    def test_repr(self):
        self.assertEqual(
            repr(buildstep.BuildStep(name="me")),
            'BuildStep(name=' + repr("me") + ')')
        self.assertEqual(
            repr(NewStyleStep(name="me")),
            'NewStyleStep(name=' + repr("me") + ')')

    @defer.inlineCallbacks
    def test_regularLocks(self):
        lock1 = locks.MasterLock("masterlock")
        lock2 = locks.WorkerLock("workerlock")

        self.setupStep(self.FakeBuildStep(
            locks=[locks.LockAccess(lock1, 'counting'), locks.LockAccess(lock2, 'exclusive')]))
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()

    @defer.inlineCallbacks
    def test_cancelWhileLocksAvailable(self):

        def _owns_lock(step, lock):
            access = [step_access for step_lock, step_access in step.locks if step_lock == lock][0]
            return lock.isOwner(step, access)

        def _lock_available(step, lock):
            access = [step_access for step_lock, step_access in step.locks if step_lock == lock][0]
            return lock.isAvailable(step, access)

        lock1 = locks.MasterLock("masterlock1")
        real_lock1 = locks.RealMasterLock(lock1)
        lock2 = locks.MasterLock("masterlock2")
        real_lock2 = locks.RealMasterLock(lock2)

        stepa = self.setupStep(self.FakeBuildStep(locks=[
            (real_lock1, locks.LockAccess(lock1, 'exclusive'))
        ]))
        stepb = self.setupStep(self.FakeBuildStep(locks=[
            (real_lock2, locks.LockAccess(lock2, 'exclusive'))
        ]))

        stepc = self.setupStep(self.FakeBuildStep(locks=[
            (real_lock1, locks.LockAccess(lock1, 'exclusive')),
            (real_lock2, locks.LockAccess(lock2, 'exclusive'))
        ]))
        stepd = self.setupStep(self.FakeBuildStep(locks=[
            (real_lock1, locks.LockAccess(lock1, 'exclusive')),
            (real_lock2, locks.LockAccess(lock2, 'exclusive'))
        ]))

        # Start all the steps
        yield stepa.acquireLocks()
        yield stepb.acquireLocks()
        c_d = stepc.acquireLocks()
        d_d = stepd.acquireLocks()

        # Check that step a and step b have the locks
        self.assertTrue(_owns_lock(stepa, real_lock1))
        self.assertTrue(_owns_lock(stepb, real_lock2))

        # Check that step c does not have a lock
        self.assertFalse(_owns_lock(stepc, real_lock1))
        self.assertFalse(_owns_lock(stepc, real_lock2))

        # Check that step d does not have a lock
        self.assertFalse(_owns_lock(stepd, real_lock1))
        self.assertFalse(_owns_lock(stepd, real_lock2))

        # Release lock 1
        stepa.releaseLocks()
        yield deferLater(reactor, 0, lambda: None)

        # lock1 should be available for step c
        self.assertTrue(_lock_available(stepc, real_lock1))
        self.assertFalse(_lock_available(stepc, real_lock2))
        self.assertFalse(_lock_available(stepd, real_lock1))
        self.assertFalse(_lock_available(stepd, real_lock2))

        # Cancel step c
        stepc.interrupt("cancelling")
        yield c_d

        # Check that step c does not have a lock
        self.assertFalse(_owns_lock(stepc, real_lock1))
        self.assertFalse(_owns_lock(stepc, real_lock2))

        # No lock should be available for step c
        self.assertFalse(_lock_available(stepc, real_lock1))
        self.assertFalse(_lock_available(stepc, real_lock2))

        # lock 1 should be available for step d
        self.assertTrue(_lock_available(stepd, real_lock1))
        self.assertFalse(_lock_available(stepd, real_lock2))

        # Release lock 2
        stepb.releaseLocks()

        # Both locks should be available for step d
        self.assertTrue(_lock_available(stepd, real_lock1))
        self.assertTrue(_lock_available(stepd, real_lock2))

        # So it should run
        yield d_d

        # Check that step d owns the locks
        self.assertTrue(_owns_lock(stepd, real_lock1))
        self.assertTrue(_owns_lock(stepd, real_lock2))

    @defer.inlineCallbacks
    def test_multiple_cancel(self):
        step = self.setupStep(CustomActionBuildStep())

        def double_interrupt():
            step.interrupt('reason1')
            step.interrupt('reason2')
            return CANCELLED

        step.action = double_interrupt

        self.expectOutcome(result=CANCELLED)
        yield self.runStep()

    @defer.inlineCallbacks
    def test_runCommand(self):
        bs = buildstep.BuildStep()
        bs.worker = worker.FakeWorker(master=None)  # master is not used here
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
    def test_run_command_after_interrupt(self):
        step = self.setupStep(CustomActionBuildStep())

        cmd = remotecommand.RemoteShellCommand("build", ["echo", "hello"])

        def run(*args, **kwargs):
            raise RuntimeError("Command must not be run when step is interrupted")
        cmd.run = run

        @defer.inlineCallbacks
        def interrupt_and_run_command():
            step.interrupt('reason1')
            res = yield step.runCommand(cmd)
            return res

        step.action = interrupt_and_run_command

        self.expectOutcome(result=CANCELLED)
        yield self.runStep()

    @defer.inlineCallbacks
    def test_start_returns_SKIPPED(self):
        self.setupStep(self.SkippingBuildStep())
        self.step.finished = mock.Mock()
        self.expectOutcome(result=SKIPPED, state_string='finished (skipped)')
        yield self.runStep()
        # 837: we want to specifically avoid calling finished() if skipping
        self.step.finished.assert_not_called()

    @defer.inlineCallbacks
    def test_doStepIf_false(self):
        self.setupStep(self.FakeBuildStep(doStepIf=False))
        self.step.finished = mock.Mock()
        self.expectOutcome(result=SKIPPED, state_string='finished (skipped)')
        yield self.runStep()
        # 837: we want to specifically avoid calling finished() if skipping
        self.step.finished.assert_not_called()

    @defer.inlineCallbacks
    def test_doStepIf_renderable_false(self):
        @util.renderer
        def dostepif(props):
            return False
        self.setupStep(self.FakeBuildStep(doStepIf=dostepif))
        self.step.finished = mock.Mock()
        self.expectOutcome(result=SKIPPED, state_string='finished (skipped)')
        yield self.runStep()
        # 837: we want to specifically avoid calling finished() if skipping
        self.step.finished.assert_not_called()

    @defer.inlineCallbacks
    def test_doStepIf_returns_false(self):
        self.setupStep(self.FakeBuildStep(doStepIf=lambda step: False))
        self.step.finished = mock.Mock()
        self.expectOutcome(result=SKIPPED, state_string='finished (skipped)')
        yield self.runStep()
        # 837: we want to specifically avoid calling finished() if skipping
        self.step.finished.assert_not_called()

    @defer.inlineCallbacks
    def test_doStepIf_returns_deferred_false(self):
        self.setupStep(self.FakeBuildStep(
            doStepIf=lambda step: defer.succeed(False)))
        self.step.finished = mock.Mock()
        self.expectOutcome(result=SKIPPED, state_string='finished (skipped)')
        yield self.runStep()
        # 837: we want to specifically avoid calling finished() if skipping
        self.step.finished.assert_not_called()

    def test_hideStepIf_False(self):
        self._setupWaterfallTest(False, False)
        return self.runStep()

    def test_hideStepIf_True(self):
        self._setupWaterfallTest(True, True)
        return self.runStep()

    @defer.inlineCallbacks
    def test_hideStepIf_Callable_False(self):
        called = [False]

        def shouldHide(result, step):
            called[0] = True
            self.assertTrue(step is self.step)
            self.assertEqual(result, SUCCESS)
            return False

        self._setupWaterfallTest(shouldHide, False)

        yield self.runStep()
        self.assertTrue(called[0])

    @defer.inlineCallbacks
    def test_hideStepIf_Callable_True(self):
        called = [False]

        def shouldHide(result, step):
            called[0] = True
            self.assertTrue(step is self.step)
            self.assertEqual(result, SUCCESS)
            return True

        self._setupWaterfallTest(shouldHide, True)

        yield self.runStep()
        self.assertTrue(called[0])

    @defer.inlineCallbacks
    def test_hideStepIf_fails(self):
        # 0/0 causes DivideByZeroError, which should be flagged as an exception

        self._setupWaterfallTest(
            lambda x, y: 0 / 0, False, expectedResult=EXCEPTION)
        self.step.addLogWithFailure = mock.Mock()
        yield self.runStep()
        self.assertEqual(len(self.flushLoggedErrors(ZeroDivisionError)), 1)

    @defer.inlineCallbacks
    def test_hideStepIf_Callable_Exception(self):
        called = [False]

        def shouldHide(result, step):
            called[0] = True
            self.assertTrue(step is self.step)
            self.assertEqual(result, EXCEPTION)
            return True

        def createException(*args, **kwargs):
            raise RuntimeError()

        self.setupStep(self.FakeBuildStep(hideStepIf=shouldHide,
                                          doStepIf=createException))
        self.expectOutcome(result=EXCEPTION,
                           state_string='finished (exception)')
        self.expectHidden(True)

        try:
            yield self.runStep()
        except Exception as e:
            log.err(e)
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)
        self.assertTrue(called[0])

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
                return SUCCESS
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

    def setup_summary_test(self):
        self.patch(NewStyleStep, 'getCurrentSummary',
                   lambda self: defer.succeed({'step': 'C'}))
        self.patch(NewStyleStep, 'getResultSummary',
                   lambda self: defer.succeed({'step': 'CS', 'build': 'CB'}))
        step = NewStyleStep()
        step.master = fakemaster.make_master(self, wantData=True, wantDb=True)
        step.stepid = 13
        step.build = fakebuild.FakeBuild()
        return step

    def test_updateSummary_running(self):
        step = self.setup_summary_test()
        step._running = True
        step.updateSummary()
        self.reactor.advance(1)
        self.assertEqual(step.master.data.updates.stepStateString[13], 'C')

    def test_updateSummary_running_empty_dict(self):
        step = self.setup_summary_test()
        step.getCurrentSummary = lambda: {}
        step._running = True
        step.updateSummary()
        self.reactor.advance(1)
        self.assertEqual(step.master.data.updates.stepStateString[13],
                         'finished')

    def test_updateSummary_running_not_unicode(self):
        step = self.setup_summary_test()
        step.getCurrentSummary = lambda: {'step': b'bytestring'}
        step._running = True
        step.updateSummary()
        self.reactor.advance(1)
        self.assertEqual(len(self.flushLoggedErrors(TypeError)), 1)

    def test_updateSummary_running_not_dict(self):
        step = self.setup_summary_test()
        step.getCurrentSummary = lambda: 'foo!'
        step._running = True
        step.updateSummary()
        self.reactor.advance(1)
        self.assertEqual(len(self.flushLoggedErrors(TypeError)), 1)

    def test_updateSummary_finished(self):
        step = self.setup_summary_test()
        step._running = False
        step.updateSummary()
        self.reactor.advance(1)
        self.assertEqual(step.master.data.updates.stepStateString[13], 'CS')

    def test_updateSummary_finished_empty_dict(self):
        step = self.setup_summary_test()
        step.getResultSummary = lambda: {}
        step._running = False
        step.updateSummary()
        self.reactor.advance(1)
        self.assertEqual(step.master.data.updates.stepStateString[13],
                         'finished')

    def test_updateSummary_finished_not_dict(self):
        step = self.setup_summary_test()
        step.getResultSummary = lambda: 'foo!'
        step._running = False
        step.updateSummary()
        self.reactor.advance(1)
        self.assertEqual(len(self.flushLoggedErrors(TypeError)), 1)

    def checkSummary(self, got, step, build=None):
        self.assertTrue(all(isinstance(k, str) for k in got))
        self.assertTrue(all(isinstance(k, str) for k in got.values()))
        exp = {'step': step}
        if build:
            exp['build'] = build
        self.assertEqual(got, exp)

    def test_getCurrentSummary(self):
        st = buildstep.BuildStep()
        st.description = None
        self.checkSummary(st.getCurrentSummary(), 'running')

    def test_getCurrentSummary_description(self):
        st = buildstep.BuildStep()
        st.description = 'fooing'
        self.checkSummary(st.getCurrentSummary(), 'fooing')

    def test_getCurrentSummary_descriptionSuffix(self):
        st = buildstep.BuildStep()
        st.description = 'fooing'
        st.descriptionSuffix = 'bar'
        self.checkSummary(st.getCurrentSummary(), 'fooing bar')

    def test_getCurrentSummary_description_list(self):
        st = buildstep.BuildStep()
        st.description = ['foo', 'ing']
        self.checkSummary(st.getCurrentSummary(), 'foo ing')

    def test_getCurrentSummary_descriptionSuffix_list(self):
        st = buildstep.BuildStep()
        st.results = SUCCESS
        st.description = ['foo', 'ing']
        st.descriptionSuffix = ['bar', 'bar2']
        self.checkSummary(st.getCurrentSummary(), 'foo ing bar bar2')

    def test_getResultSummary(self):
        st = buildstep.BuildStep()
        st.results = SUCCESS
        st.description = None
        self.checkSummary(st.getResultSummary(), 'finished')

    def test_getResultSummary_description(self):
        st = buildstep.BuildStep()
        st.results = SUCCESS
        st.description = 'fooing'
        self.checkSummary(st.getResultSummary(), 'fooing')

    def test_getResultSummary_descriptionDone(self):
        st = buildstep.BuildStep()
        st.results = SUCCESS
        st.description = 'fooing'
        st.descriptionDone = 'fooed'
        self.checkSummary(st.getResultSummary(), 'fooed')

    def test_getResultSummary_descriptionSuffix(self):
        st = buildstep.BuildStep()
        st.results = SUCCESS
        st.description = 'fooing'
        st.descriptionSuffix = 'bar'
        self.checkSummary(st.getResultSummary(), 'fooing bar')

    def test_getResultSummary_descriptionDone_and_Suffix(self):
        st = buildstep.BuildStep()
        st.results = SUCCESS
        st.descriptionDone = 'fooed'
        st.descriptionSuffix = 'bar'
        self.checkSummary(st.getResultSummary(), 'fooed bar')

    def test_getResultSummary_description_list(self):
        st = buildstep.BuildStep()
        st.results = SUCCESS
        st.description = ['foo', 'ing']
        self.checkSummary(st.getResultSummary(), 'foo ing')

    def test_getResultSummary_descriptionSuffix_list(self):
        st = buildstep.BuildStep()
        st.results = SUCCESS
        st.description = ['foo', 'ing']
        st.descriptionSuffix = ['bar', 'bar2']
        self.checkSummary(st.getResultSummary(), 'foo ing bar bar2')

    @defer.inlineCallbacks
    def test_getResultSummary_descriptionSuffix_failure(self):
        st = buildstep.BuildStep()
        st.results = FAILURE
        st.description = 'fooing'
        self.checkSummary((yield st.getBuildResultSummary()), 'fooing (failure)',
                          'fooing (failure)')
        self.checkSummary(st.getResultSummary(), 'fooing (failure)')

    @defer.inlineCallbacks
    def test_getResultSummary_descriptionSuffix_skipped(self):
        st = buildstep.BuildStep()
        st.results = SKIPPED
        st.description = 'fooing'
        self.checkSummary((yield st.getBuildResultSummary()), 'fooing (skipped)')
        self.checkSummary(st.getResultSummary(), 'fooing (skipped)')

    # Test calling checkWorkerHasCommand() when worker have support for
    # requested remote command.
    def testcheckWorkerHasCommandGood(self):
        # patch BuildStep.workerVersion() to return success
        mockedWorkerVersion = mock.Mock()
        self.patch(buildstep.BuildStep, "workerVersion", mockedWorkerVersion)

        # check that no exceptions are raised
        buildstep.BuildStep().checkWorkerHasCommand("foo")

        # make sure workerVersion() was called with correct arguments
        mockedWorkerVersion.assert_called_once_with("foo")

    # Test calling checkWorkerHasCommand() when worker is to old to support
    # requested remote command.
    def testcheckWorkerHasCommandTooOld(self):
        # patch BuildStep.workerVersion() to return error
        self.patch(buildstep.BuildStep,
                   "workerVersion",
                   mock.Mock(return_value=None))

        # make sure appropriate exception is raised
        step = buildstep.BuildStep()
        with self.assertRaisesRegex(WorkerSetupError,
                                    "worker is too old, does not know about foo"):
            step.checkWorkerHasCommand("foo")

    @defer.inlineCallbacks
    def testRunRaisesException(self):
        step = NewStyleStep()
        step.master = mock.Mock()
        step.build = mock.Mock()
        step.build.builder.botmaster.getLockFromLockAccesses = mock.Mock(return_value=[])
        step.locks = []
        step.renderables = []
        step.build.render = defer.succeed
        step.master.data.updates.addStep = lambda **kwargs: defer.succeed(
            (0, 0, 0))
        step.addLogWithFailure = lambda x: defer.succeed(None)
        step.run = lambda: defer.fail(RuntimeError('got exception'))
        res = yield step.startStep(mock.Mock())
        self.assertFalse(step._running)
        errors = self.flushLoggedErrors()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].getErrorMessage(), 'got exception')
        self.assertEqual(res, EXCEPTION)


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
            'worker',
            'progress',
            'stopped',
        ]:
            self.assertTrue(hasattr(self.step, attr))

    def test_signature_setBuild(self):
        @self.assertArgSpecMatches(self.step.setBuild)
        def setBuild(self, build):
            pass

    def test_signature_setWorker(self):
        @self.assertArgSpecMatches(self.step.setWorker)
        def setWorker(self, worker):
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

    def test_signature_interrupt(self):
        @self.assertArgSpecMatches(self.step.interrupt)
        def interrupt(self, reason):
            pass

    def test_signature_setProgress(self):
        @self.assertArgSpecMatches(self.step.setProgress)
        def setProgress(self, metric, value):
            pass

    def test_signature_workerVersion(self):
        @self.assertArgSpecMatches(self.step.workerVersion)
        def workerVersion(self, command, oldversion=None):
            pass

    def test_signature_workerVersionIsOlderThan(self):
        @self.assertArgSpecMatches(self.step.workerVersionIsOlderThan)
        def workerVersionIsOlderThan(self, command, minversion):
            pass

    def test_signature_getWorkerName(self):
        @self.assertArgSpecMatches(self.step.getWorkerName)
        def getWorkerName(self):
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
                   steps.BuildStepMixin, TestReactorMixin,
                   InterfaceTests):

    def setUp(self):
        self.setUpTestReactor()
        self.setUpBuildStep()
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
        return SUCCESS


class TestCommandMixin(steps.BuildStepMixin, TestReactorMixin,
                       unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self.setUpTestReactor()
        yield self.setUpBuildStep()
        self.step = CommandMixinExample()
        self.setupStep(self.step)

    def tearDown(self):
        return self.tearDownBuildStep()

    @defer.inlineCallbacks
    def test_runRmdir(self):
        self.step.testMethod = lambda: self.step.runRmdir('/some/path')
        self.expectCommands(
            Expect('rmdir', {'dir': '/some/path', 'logEnviron': False}) + 0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()
        self.assertTrue(self.step.method_return_value)

    @defer.inlineCallbacks
    def test_runMkdir(self):
        self.step.testMethod = lambda: self.step.runMkdir('/some/path')
        self.expectCommands(
            Expect('mkdir', {'dir': '/some/path', 'logEnviron': False}) + 0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()
        self.assertTrue(self.step.method_return_value)

    @defer.inlineCallbacks
    def test_runMkdir_fails(self):
        self.step.testMethod = lambda: self.step.runMkdir('/some/path')
        self.expectCommands(
            Expect('mkdir', {'dir': '/some/path', 'logEnviron': False}) + 1,
        )
        self.expectOutcome(result=FAILURE)
        yield self.runStep()

    @defer.inlineCallbacks
    def test_runMkdir_fails_no_abandon(self):
        self.step.testMethod = lambda: self.step.runMkdir(
            '/some/path', abandonOnFailure=False)
        self.expectCommands(
            Expect('mkdir', {'dir': '/some/path', 'logEnviron': False}) + 1,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()
        self.assertFalse(self.step.method_return_value)

    @defer.inlineCallbacks
    def test_pathExists(self):
        self.step.testMethod = lambda: self.step.pathExists('/some/path')
        self.expectCommands(
            Expect('stat', {'file': '/some/path', 'logEnviron': False}) +
            0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()
        self.assertTrue(self.step.method_return_value)

    @defer.inlineCallbacks
    def test_pathExists_doesnt(self):
        self.step.testMethod = lambda: self.step.pathExists('/some/path')
        self.expectCommands(
            Expect('stat', {'file': '/some/path', 'logEnviron': False}) + 1,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()
        self.assertFalse(self.step.method_return_value)

    @defer.inlineCallbacks
    def test_pathExists_logging(self):
        self.step.testMethod = lambda: self.step.pathExists('/some/path')
        self.expectCommands(
            Expect('stat', {'file': '/some/path', 'logEnviron': False}) +
            Expect.log('stdio', header='NOTE: never mind\n') +
            1,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()
        self.assertFalse(self.step.method_return_value)
        self.assertEqual(self.step.getLog('stdio').header,
                         'NOTE: never mind\n')

    def test_glob(self):
        @defer.inlineCallbacks
        def testFunc():
            res = yield self.step.runGlob("*.pyc")
            self.assertEqual(res, ["one.pyc", "two.pyc"])
        self.step.testMethod = testFunc
        self.expectCommands(
            Expect('glob', {'path': '*.pyc', 'logEnviron': False}) +
            Expect.update('files', ["one.pyc", "two.pyc"]) +
            0
        )
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_glob_empty(self):
        self.step.testMethod = lambda: self.step.runGlob("*.pyc")
        self.expectCommands(
            Expect('glob', {'path': '*.pyc', 'logEnviron': False}) +
            Expect.update('files', []) +
            0
        )
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_glob_fail(self):
        self.step.testMethod = lambda: self.step.runGlob("*.pyc")
        self.expectCommands(
            Expect('glob', {'path': '*.pyc', 'logEnviron': False}) +
            1
        )
        self.expectOutcome(result=FAILURE)
        return self.runStep()


class SimpleShellCommand(buildstep.ShellMixin, buildstep.BuildStep):

    def __init__(self, make_cmd_kwargs=None, prohibit_args=None, **kwargs):
        self.make_cmd_kwargs = make_cmd_kwargs or {}

        kwargs = self.setupShellMixin(kwargs, prohibitArgs=prohibit_args)
        super().__init__(**kwargs)

    @defer.inlineCallbacks
    def run(self):
        cmd = yield self.makeRemoteShellCommand(**self.make_cmd_kwargs)
        yield self.runCommand(cmd)
        return cmd.results()


class TestShellMixin(steps.BuildStepMixin,
                     config.ConfigErrorsMixin,
                     TestReactorMixin,
                     unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self.setUpTestReactor()
        yield self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_setupShellMixin_bad_arg(self):
        mixin = SimpleShellCommand()
        with self.assertRaisesConfigError("invalid SimpleShellCommand argument invarg"):
            mixin.setupShellMixin({'invarg': 13})

    def test_setupShellMixin_prohibited_arg(self):
        mixin = SimpleShellCommand()
        with self.assertRaisesConfigError("invalid SimpleShellCommand argument logfiles"):
            mixin.setupShellMixin({'logfiles': None},
                                  prohibitArgs=['logfiles'])

    def test_constructor_defaults(self):
        class MySubclass(SimpleShellCommand):
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
    def test_prohibit_args(self):
        self.setupStep(SimpleShellCommand(prohibit_args=['command'],
                                          make_cmd_kwargs={'command': ['cmd', 'arg']}))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['cmd', 'arg']) +
            0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()

    @defer.inlineCallbacks
    def test_no_default_workdir(self):
        self.setupStep(SimpleShellCommand(command=['cmd', 'arg']), wantDefaultWorkdir=False)
        self.expectCommands(
            ExpectShell(workdir='build', command=['cmd', 'arg']) +
            0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()

    @defer.inlineCallbacks
    def test_build_workdir(self):
        self.setupStep(SimpleShellCommand(command=['cmd', 'arg']), wantDefaultWorkdir=False)
        self.build.workdir = '/alternate'
        self.expectCommands(
            ExpectShell(workdir='/alternate', command=['cmd', 'arg']) +
            0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()

    @defer.inlineCallbacks
    def test_build_workdir_callable(self):
        self.setupStep(SimpleShellCommand(command=['cmd', 'arg']), wantDefaultWorkdir=False)
        self.build.workdir = lambda x: '/alternate'
        self.expectCommands(
            ExpectShell(workdir='/alternate', command=['cmd', 'arg']) +
            0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()

    @defer.inlineCallbacks
    def test_build_workdir_callable_error(self):
        self.setupStep(SimpleShellCommand(command=['cmd', 'arg']), wantDefaultWorkdir=False)
        self.build.workdir = lambda x: x.nosuchattribute  # will raise AttributeError
        self.expectException(buildstep.CallableAttributeError)
        yield self.runStep()

    @defer.inlineCallbacks
    def test_build_workdir_renderable(self):
        self.setupStep(SimpleShellCommand(command=['cmd', 'arg']), wantDefaultWorkdir=False)
        self.build.workdir = properties.Property("myproperty")
        self.properties.setProperty("myproperty", "/myproperty", "test")
        self.expectCommands(
            ExpectShell(workdir='/myproperty', command=['cmd', 'arg']) +
            0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()

    @defer.inlineCallbacks
    def test_step_workdir(self):
        self.setupStep(SimpleShellCommand(command=['cmd', 'arg'], workdir='/stepdir'))
        self.build.workdir = '/builddir'
        self.expectCommands(
            ExpectShell(workdir='/stepdir', command=['cmd', 'arg']) +
            0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()

    @defer.inlineCallbacks
    def test_step_renderable_workdir(self):
        @renderer
        def rendered_workdir(_):
            return '/stepdir'

        self.setupStep(SimpleShellCommand(command=['cmd', 'arg'], workdir=rendered_workdir))
        self.build.workdir = '/builddir'
        self.expectCommands(
            ExpectShell(workdir='/stepdir', command=['cmd', 'arg']) +
            0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()

    @defer.inlineCallbacks
    def test_step_workdir_overridden(self):
        self.setupStep(SimpleShellCommand(command=['cmd', 'arg'], workdir='/stepdir',
                                          make_cmd_kwargs={'workdir': '/overridden'}))
        self.build.workdir = '/builddir'
        self.expectCommands(
            ExpectShell(workdir='/overridden', command=['cmd', 'arg']) +
            0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()

    @defer.inlineCallbacks
    def test_extra_logfile(self):
        self.setupStep(SimpleShellCommand(command=['cmd', 'arg'],
                                          logfiles={'logname': 'logpath.log'}))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['cmd', 'arg'],
                        logfiles={'logname': 'logpath.log'}) +
            Expect.log('logname', stdout='logline\nlogline2\n') +
            Expect.log('stdio', stdout="some log\n") +
            0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()
        self.assertEqual(self.step.getLog('logname').stdout,
                         'logline\nlogline2\n')

    @defer.inlineCallbacks
    def test_lazy_logfiles_stdout_has_stdout(self):
        self.setupStep(SimpleShellCommand(command=['cmd', 'arg'], lazylogfiles=True))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['cmd', 'arg']) +
            Expect.log('stdio', stdout="some log\n") +
            0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()
        self.assertEqual(self.step.getLog('stdio').stdout, 'some log\n')

    @defer.inlineCallbacks
    def test_lazy_logfiles_stdout_no_stdout(self):
        # lazy log files do not apply to stdout
        self.setupStep(SimpleShellCommand(command=['cmd', 'arg'], lazylogfiles=True))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['cmd', 'arg']) +
            0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()
        self.assertEqual(self.step.getLog('stdio').stdout, '')

    @defer.inlineCallbacks
    def test_lazy_logfiles_logfile(self):
        self.setupStep(SimpleShellCommand(command=['cmd', 'arg'], lazylogfiles=True,
                                          logfiles={'logname': 'logpath.log'}))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['cmd', 'arg'],
                        logfiles={'logname': 'logpath.log'}) +
            Expect.log('logname', stdout='logline\nlogline2\n') +
            0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()
        self.assertEqual(self.step.getLog('logname').stdout,
                         'logline\nlogline2\n')

    @defer.inlineCallbacks
    def test_lazy_logfiles_no_logfile(self):
        self.setupStep(SimpleShellCommand(command=['cmd', 'arg'], lazylogfiles=True,
                                          logfiles={'logname': 'logpath.log'}))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['cmd', 'arg'],
                        logfiles={'logname': 'logpath.log'}) +
            0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()
        with self.assertRaises(KeyError):
            self.step.getLog('logname')

    @defer.inlineCallbacks
    def test_env(self):
        self.setupStep(SimpleShellCommand(command=['cmd', 'arg'], env={'BAR': 'BAR'}))
        self.build.builder.config.env = {'FOO': 'FOO'}
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['cmd', 'arg'],
                        env={'FOO': 'FOO', 'BAR': 'BAR'})
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()

    @defer.inlineCallbacks
    def test_old_worker_args(self):
        self.setupStep(SimpleShellCommand(command=['cmd', 'arg'], usePTY=False,
                                          interruptSignal='DIE'),
                       worker_version={'*': "1.1"})
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['cmd', 'arg']) +
            # note missing parameters
            0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()
        self.assertEqual(self.step.getLog('stdio').header,
                         'NOTE: worker does not allow master to override usePTY\n'
                         'NOTE: worker does not allow master to specify interruptSignal\n')

    @defer.inlineCallbacks
    def test_new_worker_args(self):
        self.setupStep(SimpleShellCommand(command=['cmd', 'arg'], usePTY=False,
                                          interruptSignal='DIE'),
                       worker_version={'*': "3.0"})
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY=False, interruptSignal='DIE',
                        command=['cmd', 'arg']) +
            0,
        )
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()
        self.assertEqual(self.step.getLog('stdio').header, '')

    @defer.inlineCallbacks
    def test_description(self):
        self.setupStep(SimpleShellCommand(command=['foo', properties.Property('bar', 'BAR')]))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['foo', 'BAR']) +
            0,
        )
        self.expectOutcome(result=SUCCESS, state_string="'foo BAR'")
        yield self.runStep()

    def test_getResultSummary(self):
        self.setupStep(SimpleShellCommand(command=['a', ['b', 'c']]))
        self.step.results = SUCCESS
        self.assertEqual(self.step.getResultSummary(), {'step': "'a b ...'"})
