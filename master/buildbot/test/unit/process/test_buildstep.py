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

from unittest import mock

from parameterized import parameterized
from twisted.internet import defer
from twisted.internet import error
from twisted.internet.task import deferLater
from twisted.python import failure
from twisted.python import log
from twisted.trial import unittest

from buildbot import locks
from buildbot.config import ConfigErrors
from buildbot.interfaces import WorkerSetupError
from buildbot.plugins import util
from buildbot.process import buildstep
from buildbot.process import properties
from buildbot.process import remotecommand
from buildbot.process.buildstep import create_step_from_step_or_factory
from buildbot.process.locks import get_real_locks_from_accesses
from buildbot.process.properties import Secret
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
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import ExpectGlob
from buildbot.test.steps import ExpectMkdir
from buildbot.test.steps import ExpectRmdir
from buildbot.test.steps import ExpectShell
from buildbot.test.steps import ExpectStat
from buildbot.test.steps import TestBuildStepMixin
from buildbot.test.util import config
from buildbot.test.util import interfaces
from buildbot.util.eventual import eventually
from buildbot.util.twisted import async_to_deferred


class NewStyleStep(buildstep.BuildStep):
    def run(self):
        pass


class CustomActionBuildStep(buildstep.BuildStep):
    # The caller is expected to set the action attribute on the step
    def run(self):
        return self.action()


def _is_lock_owned_by_step(step, lock):
    accesses = [
        step_access for step_lock, step_access in step._locks_to_acquire if step_lock == lock
    ]
    if not accesses:
        return False
    return lock.isOwner(step, accesses[0])


def _is_lock_available_for_step(step, lock):
    accesses = [
        step_access for step_lock, step_access in step._locks_to_acquire if step_lock == lock
    ]
    if not accesses:
        return False
    return lock.isAvailable(step, accesses[0])


class TestBuildStep(
    TestBuildStepMixin, config.ConfigErrorsMixin, TestReactorMixin, unittest.TestCase
):
    class FakeBuildStep(buildstep.BuildStep):
        def run(self):
            d = defer.Deferred()
            eventually(d.callback, 0)  # FIXME: this uses real reactor instead of fake one
            return d

    class SkippingBuildStep(buildstep.BuildStep):
        def run(self):
            return SKIPPED

    class LockBuildStep(buildstep.BuildStep):
        def __init__(self, testcase=None, lock_accesses=None, **kwargs):
            super().__init__(**kwargs)
            self.testcase = testcase
            self.lock_accesses = lock_accesses

        @defer.inlineCallbacks
        def run(self):
            locks = yield get_real_locks_from_accesses(self.lock_accesses, self.build)

            self.testcase.assertFalse(locks[0][0].isAvailable(self.testcase, self.lock_accesses[0]))
            self.testcase.assertFalse(locks[1][0].isAvailable(self.testcase, self.lock_accesses[1]))
            return SUCCESS

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    # support

    def _setupWaterfallTest(self, hideStepIf, expect, expectedResult=SUCCESS):
        self.setup_step(TestBuildStep.FakeBuildStep(hideStepIf=hideStepIf))
        self.expect_outcome(result=expectedResult)
        self.expect_hidden(expect)

    # tests

    def test_nameIsntString(self):
        """
        When BuildStep is passed a name that isn't a string, it reports
        a config error.
        """
        with self.assertRaisesConfigError("BuildStep argument name must be an instance of str"):
            buildstep.BuildStep(name=5)

    def test_name_too_long(self):
        with self.assertRaisesConfigError("exceeds maximum length of"):
            buildstep.BuildStep(name="b" * 100)

    def test_unexpectedKeywordArgument(self):
        """
        When BuildStep is passed an unknown keyword argument, it reports
        a config error.
        """
        with self.assertRaisesConfigError(
            "__init__ got unexpected keyword argument(s) ['oogaBooga']"
        ):
            buildstep.BuildStep(oogaBooga=5)

    def test_updateBuildSummaryPolicyDefaults(self):
        """
        updateBuildSummaryPolicy builds default value according to resultsMixin
        parameters (flunkOnFailure..)
        """
        step = buildstep.BuildStep()
        self.assertEqual(
            sorted(step.updateBuildSummaryPolicy), sorted([EXCEPTION, RETRY, CANCELLED, FAILURE])
        )

        step = buildstep.BuildStep(warnOnWarnings=True)
        self.assertEqual(
            sorted(step.updateBuildSummaryPolicy),
            sorted([EXCEPTION, RETRY, CANCELLED, FAILURE, WARNINGS]),
        )

        step = buildstep.BuildStep(flunkOnFailure=False)
        self.assertEqual(
            sorted(step.updateBuildSummaryPolicy), sorted([EXCEPTION, RETRY, CANCELLED])
        )

        step = buildstep.BuildStep(updateBuildSummaryPolicy=False)
        self.assertEqual(sorted(step.updateBuildSummaryPolicy), [])

        step = buildstep.BuildStep(updateBuildSummaryPolicy=True)
        self.assertEqual(sorted(step.updateBuildSummaryPolicy), sorted(ALL_RESULTS))

    def test_updateBuildSummaryPolicyBadType(self):
        """
        updateBuildSummaryPolicy raise ConfigError in case of bad type
        """
        with self.assertRaisesConfigError(
            "BuildStep updateBuildSummaryPolicy must be a list of result ids or boolean but it is 2"
        ):
            buildstep.BuildStep(updateBuildSummaryPolicy=FAILURE)

    class RecordingBuildStep(buildstep.BuildStep):
        def __init__(self, record_target=None, arg=None, **kwargs):
            super().__init__(**kwargs)
            self.record_target = record_target
            self.arg = arg

        def run(self):
            self.record_target.append(self.arg)
            return SUCCESS

    @defer.inlineCallbacks
    def test_arg_changes(self):
        try:
            recorded_arg = []

            step = self.RecordingBuildStep(record_target=recorded_arg, arg="orig")
            self.setup_step(step)

            self.expect_outcome(result=SUCCESS)
            yield self.run_step()

            self.assertEqual(recorded_arg, ["orig"])
        except ConfigErrors as e:
            self.assertEqual(
                "Changes to attributes of a BuildStep instance are ignored, this is a bug. "
                "Use set_step_arg(name, value) for that.",
                e.errors[0],
            )

    @defer.inlineCallbacks
    def test_arg_changes_set_step_arg(self):
        recorded_arg = []

        step = self.RecordingBuildStep(record_target=recorded_arg, arg="orig")
        step.set_step_arg("arg", "changed")
        self.setup_step(step)

        self.expect_outcome(result=SUCCESS)
        yield self.run_step()

        self.assertEqual(recorded_arg, ["changed"])

    def test_getProperty(self):
        bs = create_step_from_step_or_factory(buildstep.BuildStep())
        bs.build = fakebuild.FakeBuild()
        props = bs.build.properties = mock.Mock()
        bs.getProperty("xyz", 'b')
        props.getProperty.assert_called_with("xyz", 'b')
        bs.getProperty("xyz")
        props.getProperty.assert_called_with("xyz", None)

    def test_setProperty(self):
        bs = create_step_from_step_or_factory(buildstep.BuildStep())
        bs.build = fakebuild.FakeBuild()
        props = bs.build.properties = mock.Mock()
        bs.setProperty("x", "y", "t")
        props.setProperty.assert_called_with("x", "y", "t", runtime=True)
        bs.setProperty("x", "abc", "test", runtime=True)
        props.setProperty.assert_called_with("x", "abc", "test", runtime=True)

    @defer.inlineCallbacks
    def test_renderableLocks(self):
        master_lock = locks.MasterLock("masterlock")
        worker_lock = locks.WorkerLock("workerlock")

        lock_accesses = []

        @renderer
        def rendered_locks(props):
            master_access = locks.LockAccess(master_lock, 'counting')
            worker_access = locks.LockAccess(worker_lock, 'exclusive')
            lock_accesses.append(master_access)
            lock_accesses.append(worker_access)
            return [master_access, worker_access]

        self.setup_step(
            self.LockBuildStep(testcase=self, lock_accesses=lock_accesses, locks=rendered_locks)
        )
        self.expect_outcome(result=SUCCESS)
        yield self.run_step()

        self.assertEqual(len(lock_accesses), 2)

        self.assertTrue(
            self.get_nth_step(0)._locks_to_acquire[0][0].isAvailable(self, lock_accesses[0])
        )
        self.assertTrue(
            self.get_nth_step(0)._locks_to_acquire[1][0].isAvailable(self, lock_accesses[1])
        )

    def test_compare(self):
        lbs1 = buildstep.BuildStep(name="me")
        lbs2 = buildstep.BuildStep(name="me")
        lbs3 = buildstep.BuildStep(name="me2")
        self.assertEqual(lbs1, lbs2)
        self.assertNotEqual(lbs1, lbs3)

    def test_repr(self):
        self.assertEqual(repr(buildstep.BuildStep(name="me")), 'BuildStep(name=' + repr("me") + ')')
        self.assertEqual(repr(NewStyleStep(name="me")), 'NewStyleStep(name=' + repr("me") + ')')

    @defer.inlineCallbacks
    def test_regularLocks(self):
        master_lock = locks.MasterLock("masterlock")
        worker_lock = locks.WorkerLock("workerlock")
        lock_accesses = [
            locks.LockAccess(master_lock, 'counting'),
            locks.LockAccess(worker_lock, 'exclusive'),
        ]

        self.setup_step(
            self.LockBuildStep(testcase=self, lock_accesses=lock_accesses, locks=lock_accesses)
        )
        self.expect_outcome(result=SUCCESS)
        yield self.run_step()

        self.assertTrue(
            self.get_nth_step(0)._locks_to_acquire[0][0].isAvailable(self, lock_accesses[0])
        )
        self.assertTrue(
            self.get_nth_step(0)._locks_to_acquire[1][0].isAvailable(self, lock_accesses[1])
        )

    @defer.inlineCallbacks
    def test_regular_locks_skip_step(self):
        # BuildStep should not try to acquire locks when it's skipped
        lock = locks.MasterLock("masterlock")
        lock_access = locks.LockAccess(lock, "exclusive")

        self.setup_step(
            buildstep.BuildStep(locks=[locks.LockAccess(lock, "counting")], doStepIf=False)
        )

        locks_list = yield get_real_locks_from_accesses([lock_access], self.build)
        locks_list[0][0].claim(self, lock_access)

        self.expect_outcome(result=SKIPPED)
        yield self.run_step()

    @defer.inlineCallbacks
    def test_acquire_multiple_locks_after_not_available(self):
        lock1 = locks.MasterLock("masterlock1")
        lock2 = locks.MasterLock("masterlock2")

        stepa = self.setup_step(self.FakeBuildStep(locks=[locks.LockAccess(lock1, 'exclusive')]))
        stepb = self.setup_step(self.FakeBuildStep(locks=[locks.LockAccess(lock2, 'exclusive')]))

        stepc = self.setup_step(
            self.FakeBuildStep(
                locks=[locks.LockAccess(lock1, 'exclusive'), locks.LockAccess(lock2, 'exclusive')]
            )
        )

        yield stepa._setup_locks()
        yield stepb._setup_locks()
        yield stepc._setup_locks()

        real_lock1 = stepc._locks_to_acquire[0][0]
        real_lock2 = stepc._locks_to_acquire[1][0]

        yield stepa.acquireLocks()
        yield stepb.acquireLocks()
        c_d = stepc.acquireLocks()

        self.assertTrue(_is_lock_owned_by_step(stepa, real_lock1))
        self.assertFalse(_is_lock_owned_by_step(stepa, real_lock2))
        self.assertFalse(_is_lock_owned_by_step(stepb, real_lock1))
        self.assertTrue(_is_lock_owned_by_step(stepb, real_lock2))
        self.assertFalse(_is_lock_owned_by_step(stepc, real_lock1))
        self.assertFalse(_is_lock_owned_by_step(stepc, real_lock2))

        self.assertFalse(_is_lock_available_for_step(stepc, real_lock1))
        self.assertFalse(_is_lock_available_for_step(stepc, real_lock2))

        stepa.releaseLocks()
        yield deferLater(self.reactor, 0, lambda: None)

        self.assertTrue(_is_lock_available_for_step(stepc, real_lock1))
        self.assertFalse(_is_lock_available_for_step(stepc, real_lock2))

        stepb.releaseLocks()
        yield deferLater(self.reactor, 0, lambda: None)

        self.assertTrue(_is_lock_owned_by_step(stepc, real_lock1))
        self.assertTrue(_is_lock_owned_by_step(stepc, real_lock2))

        yield c_d

    @defer.inlineCallbacks
    def test_cancel_when_lock_available(self):
        lock = locks.MasterLock("masterlock1")

        stepa = self.setup_step(self.FakeBuildStep(locks=[locks.LockAccess(lock, 'exclusive')]))
        stepb = self.setup_step(self.FakeBuildStep(locks=[locks.LockAccess(lock, 'exclusive')]))
        stepc = self.setup_step(self.FakeBuildStep(locks=[locks.LockAccess(lock, 'exclusive')]))

        yield stepa._setup_locks()
        yield stepb._setup_locks()
        yield stepc._setup_locks()

        real_lock = stepc._locks_to_acquire[0][0]

        yield stepa.acquireLocks()
        b_d = stepb.acquireLocks()
        c_d = stepc.acquireLocks()

        self.assertTrue(_is_lock_owned_by_step(stepa, real_lock))
        self.assertFalse(_is_lock_owned_by_step(stepb, real_lock))
        self.assertFalse(_is_lock_owned_by_step(stepc, real_lock))

        self.assertFalse(_is_lock_available_for_step(stepb, real_lock))
        self.assertFalse(_is_lock_available_for_step(stepc, real_lock))

        stepa.releaseLocks()
        yield deferLater(self.reactor, 0, lambda: None)

        self.assertFalse(_is_lock_owned_by_step(stepa, real_lock))
        self.assertTrue(_is_lock_owned_by_step(stepb, real_lock))
        self.assertFalse(_is_lock_available_for_step(stepc, real_lock))

        stepb.interrupt("cancelling")
        yield b_d
        stepb.releaseLocks()

        self.assertFalse(_is_lock_owned_by_step(stepa, real_lock))
        self.assertFalse(_is_lock_owned_by_step(stepb, real_lock))
        self.assertTrue(_is_lock_available_for_step(stepc, real_lock))

        yield c_d

        self.assertFalse(_is_lock_owned_by_step(stepa, real_lock))
        self.assertFalse(_is_lock_owned_by_step(stepb, real_lock))
        self.assertTrue(_is_lock_owned_by_step(stepc, real_lock))

    @defer.inlineCallbacks
    def test_cancel_when_lock_not_available(self):
        lock = locks.MasterLock("masterlock1")

        stepa = self.setup_step(self.FakeBuildStep(locks=[locks.LockAccess(lock, 'exclusive')]))
        stepb = self.setup_step(self.FakeBuildStep(locks=[locks.LockAccess(lock, 'exclusive')]))
        stepc = self.setup_step(self.FakeBuildStep(locks=[locks.LockAccess(lock, 'exclusive')]))

        yield stepa._setup_locks()
        yield stepb._setup_locks()
        yield stepc._setup_locks()

        real_lock = stepc._locks_to_acquire[0][0]

        yield stepa.acquireLocks()
        b_d = stepb.acquireLocks()
        c_d = stepc.acquireLocks()

        self.assertTrue(_is_lock_owned_by_step(stepa, real_lock))
        self.assertFalse(_is_lock_owned_by_step(stepb, real_lock))
        self.assertFalse(_is_lock_owned_by_step(stepc, real_lock))

        self.assertFalse(_is_lock_available_for_step(stepb, real_lock))
        self.assertFalse(_is_lock_available_for_step(stepc, real_lock))

        stepb.interrupt("cancelling")
        yield b_d

        stepa.releaseLocks()
        yield deferLater(self.reactor, 0, lambda: None)

        self.assertFalse(_is_lock_owned_by_step(stepa, real_lock))
        self.assertFalse(_is_lock_owned_by_step(stepb, real_lock))
        self.assertTrue(_is_lock_owned_by_step(stepc, real_lock))

        yield c_d

        self.assertFalse(_is_lock_owned_by_step(stepa, real_lock))
        self.assertFalse(_is_lock_owned_by_step(stepb, real_lock))
        self.assertTrue(_is_lock_owned_by_step(stepc, real_lock))

    @defer.inlineCallbacks
    def test_checks_step_and_builder_locks_not_same(self):
        lock = locks.MasterLock("masterlock1")

        step = self.setup_step(self.FakeBuildStep(locks=[lock.access("exclusive")]))

        lock_list = yield get_real_locks_from_accesses([lock.access("counting")], self.build)
        self.build._locks_to_acquire = lock_list

        with self.assertRaises(RuntimeError) as e:
            yield step._setup_locks()
        self.assertEqual(
            e.exception.args,
            ("lock claimed by both Step and Build (<MasterLock(masterlock1, 1)>)",),
        )

    @defer.inlineCallbacks
    def test_multiple_cancel(self):
        step = self.setup_step(CustomActionBuildStep())

        def double_interrupt():
            step.interrupt('reason1')
            step.interrupt('reason2')
            return CANCELLED

        step.action = double_interrupt

        self.expect_outcome(result=CANCELLED)
        yield self.run_step()

    @defer.inlineCallbacks
    def test_runCommand(self):
        bs = create_step_from_step_or_factory(buildstep.BuildStep())
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
        step = self.setup_step(CustomActionBuildStep())

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

        self.expect_outcome(result=CANCELLED)
        yield self.run_step()

    @defer.inlineCallbacks
    def test_lost_remote_during_interrupt(self):
        step = self.setup_step(CustomActionBuildStep())

        cmd = remotecommand.RemoteShellCommand("build", ["echo", "hello"])

        @defer.inlineCallbacks
        def on_command(cmd):
            conn = cmd.conn
            conn.set_expect_interrupt()
            conn.set_block_on_interrupt()
            d1 = step.interrupt('interrupt reason')
            d2 = step.interrupt(failure.Failure(error.ConnectionLost()))

            conn.unblock_waiters()
            yield d1
            yield d2

        self.expect_commands(
            ExpectShell(workdir='build', command=['echo', 'hello'])
            .behavior(on_command)
            .break_connection()
        )

        @defer.inlineCallbacks
        def run_command():
            res = yield step.runCommand(cmd)
            return res.results()

        step.action = run_command

        self.expect_outcome(result=RETRY)
        yield self.run_step()

    @defer.inlineCallbacks
    def test_start_returns_SKIPPED(self):
        self.setup_step(self.SkippingBuildStep())
        self.get_nth_step(0).finished = mock.Mock()
        self.expect_outcome(result=SKIPPED, state_string='finished (skipped)')
        yield self.run_step()
        # 837: we want to specifically avoid calling finished() if skipping
        self.get_nth_step(0).finished.assert_not_called()

    @defer.inlineCallbacks
    def test_doStepIf_false(self):
        self.setup_step(self.FakeBuildStep(doStepIf=False))
        self.get_nth_step(0).finished = mock.Mock()
        self.expect_outcome(result=SKIPPED, state_string='finished (skipped)')
        yield self.run_step()
        # 837: we want to specifically avoid calling finished() if skipping
        self.get_nth_step(0).finished.assert_not_called()

    @defer.inlineCallbacks
    def test_doStepIf_renderable_false(self):
        @util.renderer
        def dostepif(props):
            return False

        self.setup_step(self.FakeBuildStep(doStepIf=dostepif))
        self.get_nth_step(0).finished = mock.Mock()
        self.expect_outcome(result=SKIPPED, state_string='finished (skipped)')
        yield self.run_step()
        # 837: we want to specifically avoid calling finished() if skipping
        self.get_nth_step(0).finished.assert_not_called()

    @defer.inlineCallbacks
    def test_doStepIf_returns_false(self):
        self.setup_step(self.FakeBuildStep(doStepIf=lambda step: False))
        self.get_nth_step(0).finished = mock.Mock()
        self.expect_outcome(result=SKIPPED, state_string='finished (skipped)')
        yield self.run_step()
        # 837: we want to specifically avoid calling finished() if skipping
        self.get_nth_step(0).finished.assert_not_called()

    @defer.inlineCallbacks
    def test_doStepIf_returns_deferred_false(self):
        self.setup_step(self.FakeBuildStep(doStepIf=lambda step: defer.succeed(False)))
        self.get_nth_step(0).finished = mock.Mock()
        self.expect_outcome(result=SKIPPED, state_string='finished (skipped)')
        yield self.run_step()
        # 837: we want to specifically avoid calling finished() if skipping
        self.get_nth_step(0).finished.assert_not_called()

    def test_hideStepIf_False(self):
        self._setupWaterfallTest(False, False)
        return self.run_step()

    def test_hideStepIf_True(self):
        self._setupWaterfallTest(True, True)
        return self.run_step()

    @defer.inlineCallbacks
    def test_hideStepIf_Callable_False(self):
        called = [False]

        def shouldHide(result, step):
            called[0] = True
            self.assertTrue(step is self.get_nth_step(0))
            self.assertEqual(result, SUCCESS)
            return False

        self._setupWaterfallTest(shouldHide, False)

        yield self.run_step()
        self.assertTrue(called[0])

    @defer.inlineCallbacks
    def test_hideStepIf_Callable_True(self):
        called = [False]

        def shouldHide(result, step):
            called[0] = True
            self.assertTrue(step is self.get_nth_step(0))
            self.assertEqual(result, SUCCESS)
            return True

        self._setupWaterfallTest(shouldHide, True)

        yield self.run_step()
        self.assertTrue(called[0])

    @defer.inlineCallbacks
    def test_hideStepIf_fails(self):
        # 0/0 causes DivideByZeroError, which should be flagged as an exception

        self._setupWaterfallTest(lambda x, y: 0 / 0, False, expectedResult=EXCEPTION)
        self.get_nth_step(0).addLogWithFailure = mock.Mock()
        yield self.run_step()
        self.assertEqual(len(self.flushLoggedErrors(ZeroDivisionError)), 1)

    @defer.inlineCallbacks
    def test_hideStepIf_Callable_Exception(self):
        called = [False]

        def shouldHide(result, step):
            called[0] = True
            self.assertTrue(step is self.get_nth_step(0))
            self.assertEqual(result, EXCEPTION)
            return True

        def createException(*args, **kwargs):
            raise RuntimeError()

        self.setup_step(self.FakeBuildStep(hideStepIf=shouldHide, doStepIf=createException))
        self.expect_outcome(result=EXCEPTION, state_string='finished (exception)')
        self.expect_hidden(True)

        try:
            yield self.run_step()
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
                testcase.assertRaises(KeyError, lambda: self.getLog('testy'))
                log1 = yield self.addLog('testy')
                log2 = self.getLog('testy')
                testcase.assertIdentical(log1, log2)
                return SUCCESS

        self.setup_step(TestGetLogStep())
        self.expect_outcome(result=SUCCESS)
        yield self.run_step()

    @defer.inlineCallbacks
    def test_step_renders_flunkOnFailure(self):
        self.setup_step(TestBuildStep.FakeBuildStep(flunkOnFailure=properties.Property('fOF')))
        self.build.setProperty('fOF', 'yes', 'test')
        self.expect_outcome(result=SUCCESS)
        yield self.run_step()
        self.assertEqual(self.get_nth_step(0).flunkOnFailure, 'yes')

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

    @defer.inlineCallbacks
    def setup_summary_test(self):
        self.patch(NewStyleStep, 'getCurrentSummary', lambda self: defer.succeed({'step': 'C'}))
        self.patch(
            NewStyleStep,
            'getResultSummary',
            lambda self: defer.succeed({'step': 'CS', 'build': 'CB'}),
        )
        step = create_step_from_step_or_factory(NewStyleStep())
        step.master = yield fakemaster.make_master(self, wantData=True, wantDb=True)
        step.stepid = 13
        step.build = fakebuild.FakeBuild()
        return step

    @defer.inlineCallbacks
    def test_updateSummary_running(self):
        step = yield self.setup_summary_test()
        step._running = True
        step.updateSummary()
        self.reactor.advance(1)
        self.assertEqual(step.master.data.updates.stepStateString[13], 'C')

    @defer.inlineCallbacks
    def test_updateSummary_running_empty_dict(self):
        step = yield self.setup_summary_test()
        step.getCurrentSummary = lambda: {}
        step._running = True
        step.updateSummary()
        self.reactor.advance(1)
        self.assertEqual(step.master.data.updates.stepStateString[13], 'finished')

    @defer.inlineCallbacks
    def test_updateSummary_running_not_unicode(self):
        step = yield self.setup_summary_test()
        step.getCurrentSummary = lambda: {'step': b'bytestring'}
        step._running = True
        step.updateSummary()
        self.reactor.advance(1)
        self.assertEqual(len(self.flushLoggedErrors(TypeError)), 1)

    @defer.inlineCallbacks
    def test_updateSummary_running_not_dict(self):
        step = yield self.setup_summary_test()
        step.getCurrentSummary = lambda: 'foo!'
        step._running = True
        step.updateSummary()
        self.reactor.advance(1)
        self.assertEqual(len(self.flushLoggedErrors(TypeError)), 1)

    @defer.inlineCallbacks
    def test_updateSummary_finished(self):
        step = yield self.setup_summary_test()
        step._running = False
        step.updateSummary()
        self.reactor.advance(1)
        self.assertEqual(step.master.data.updates.stepStateString[13], 'CS')

    @defer.inlineCallbacks
    def test_updateSummary_finished_empty_dict(self):
        step = yield self.setup_summary_test()
        step.getResultSummary = lambda: {}
        step._running = False
        step.updateSummary()
        self.reactor.advance(1)
        self.assertEqual(step.master.data.updates.stepStateString[13], 'finished')

    @defer.inlineCallbacks
    def test_updateSummary_finished_not_dict(self):
        step = yield self.setup_summary_test()
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
        st = create_step_from_step_or_factory(buildstep.BuildStep())
        st.description = None
        self.checkSummary(st.getCurrentSummary(), 'running')

    def test_getCurrentSummary_description(self):
        st = create_step_from_step_or_factory(buildstep.BuildStep())
        st.description = 'fooing'
        self.checkSummary(st.getCurrentSummary(), 'fooing')

    def test_getCurrentSummary_descriptionSuffix(self):
        st = create_step_from_step_or_factory(buildstep.BuildStep())
        st.description = 'fooing'
        st.descriptionSuffix = 'bar'
        self.checkSummary(st.getCurrentSummary(), 'fooing bar')

    def test_getCurrentSummary_description_list(self):
        st = create_step_from_step_or_factory(buildstep.BuildStep())
        st.description = ['foo', 'ing']
        self.checkSummary(st.getCurrentSummary(), 'foo ing')

    def test_getCurrentSummary_descriptionSuffix_list(self):
        st = create_step_from_step_or_factory(buildstep.BuildStep())
        st.results = SUCCESS
        st.description = ['foo', 'ing']
        st.descriptionSuffix = ['bar', 'bar2']
        self.checkSummary(st.getCurrentSummary(), 'foo ing bar bar2')

    def test_getResultSummary(self):
        st = create_step_from_step_or_factory(buildstep.BuildStep())
        st.results = SUCCESS
        st.description = None
        self.checkSummary(st.getResultSummary(), 'finished')

    def test_getResultSummary_description(self):
        st = create_step_from_step_or_factory(buildstep.BuildStep())
        st.results = SUCCESS
        st.description = 'fooing'
        self.checkSummary(st.getResultSummary(), 'fooing')

    def test_getResultSummary_descriptionDone(self):
        st = create_step_from_step_or_factory(buildstep.BuildStep())
        st.results = SUCCESS
        st.description = 'fooing'
        st.descriptionDone = 'fooed'
        self.checkSummary(st.getResultSummary(), 'fooed')

    def test_getResultSummary_descriptionSuffix(self):
        st = create_step_from_step_or_factory(buildstep.BuildStep())
        st.results = SUCCESS
        st.description = 'fooing'
        st.descriptionSuffix = 'bar'
        self.checkSummary(st.getResultSummary(), 'fooing bar')

    def test_getResultSummary_descriptionDone_and_Suffix(self):
        st = create_step_from_step_or_factory(buildstep.BuildStep())
        st.results = SUCCESS
        st.descriptionDone = 'fooed'
        st.descriptionSuffix = 'bar'
        self.checkSummary(st.getResultSummary(), 'fooed bar')

    def test_getResultSummary_description_list(self):
        st = create_step_from_step_or_factory(buildstep.BuildStep())
        st.results = SUCCESS
        st.description = ['foo', 'ing']
        self.checkSummary(st.getResultSummary(), 'foo ing')

    def test_getResultSummary_descriptionSuffix_list(self):
        st = create_step_from_step_or_factory(buildstep.BuildStep())
        st.results = SUCCESS
        st.description = ['foo', 'ing']
        st.descriptionSuffix = ['bar', 'bar2']
        self.checkSummary(st.getResultSummary(), 'foo ing bar bar2')

    @defer.inlineCallbacks
    def test_getResultSummary_descriptionSuffix_failure(self):
        st = create_step_from_step_or_factory(buildstep.BuildStep())
        st.results = FAILURE
        st.description = 'fooing'
        self.checkSummary(
            (yield st.getBuildResultSummary()), 'fooing (failure)', 'fooing (failure)'
        )
        self.checkSummary(st.getResultSummary(), 'fooing (failure)')

    @defer.inlineCallbacks
    def test_getResultSummary_descriptionSuffix_skipped(self):
        st = create_step_from_step_or_factory(buildstep.BuildStep())
        st.results = SKIPPED
        st.description = 'fooing'
        self.checkSummary((yield st.getBuildResultSummary()), 'fooing (skipped)')
        self.checkSummary(st.getResultSummary(), 'fooing (skipped)')

    @defer.inlineCallbacks
    def test_getResultSummary_description_failure_timed_out(self):
        st = create_step_from_step_or_factory(buildstep.BuildStep())
        st.results = FAILURE
        st.description = "fooing"
        st.timed_out = True
        self.checkSummary(
            (yield st.getBuildResultSummary()),
            "fooing (failure) (timed out)",
            "fooing (failure) (timed out)",
        )
        self.checkSummary(st.getResultSummary(), "fooing (failure) (timed out)")

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
        self.patch(buildstep.BuildStep, "workerVersion", mock.Mock(return_value=None))

        # make sure appropriate exception is raised
        step = buildstep.BuildStep()
        with self.assertRaisesRegex(WorkerSetupError, "worker is too old, does not know about foo"):
            step.checkWorkerHasCommand("foo")

    @defer.inlineCallbacks
    def testRunRaisesException(self):
        step = create_step_from_step_or_factory(NewStyleStep())
        step.master = mock.Mock()
        step.master.reactor = self.reactor
        step.build = mock.Mock()
        step.build._locks_to_acquire = []
        step.build.properties.cleanupTextFromSecrets = lambda s: s
        step.build.builder.botmaster.getLockFromLockAccesses = mock.Mock(return_value=[])
        step.locks = []
        step.renderables = []
        step.build.render = defer.succeed
        step.master.data.updates.addStep = lambda **kwargs: defer.succeed((0, 0, 0))
        step.addLogWithFailure = lambda x: defer.succeed(None)
        step.run = lambda: defer.fail(RuntimeError('got exception'))
        res = yield step.startStep(mock.Mock())
        self.assertFalse(step._running)
        errors = self.flushLoggedErrors()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].getErrorMessage(), 'got exception')
        self.assertEqual(res, EXCEPTION)


class InterfaceTests(interfaces.InterfaceTests):
    # ensure that TestBuildStepMixin creates a convincing facsimile of the
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
            self.assertTrue(hasattr(self.get_nth_step(0), attr))

    def test_signature_setBuild(self):
        @self.assertArgSpecMatches(self.get_nth_step(0).setBuild)
        def setBuild(self, build):
            pass

    def test_signature_setWorker(self):
        @self.assertArgSpecMatches(self.get_nth_step(0).setWorker)
        def setWorker(self, worker):
            pass

    def test_signature_setupProgress(self):
        @self.assertArgSpecMatches(self.get_nth_step(0).setupProgress)
        def setupProgress(self):
            pass

    def test_signature_startStep(self):
        @self.assertArgSpecMatches(self.get_nth_step(0).startStep)
        def startStep(self, remote):
            pass

    def test_signature_run(self):
        @self.assertArgSpecMatches(self.get_nth_step(0).run)
        def run(self):
            pass

    def test_signature_interrupt(self):
        @self.assertArgSpecMatches(self.get_nth_step(0).interrupt)
        def interrupt(self, reason):
            pass

    def test_signature_setProgress(self):
        @self.assertArgSpecMatches(self.get_nth_step(0).setProgress)
        def setProgress(self, metric, value):
            pass

    def test_signature_workerVersion(self):
        @self.assertArgSpecMatches(self.get_nth_step(0).workerVersion)
        def workerVersion(self, command, oldversion=None):
            pass

    def test_signature_workerVersionIsOlderThan(self):
        @self.assertArgSpecMatches(self.get_nth_step(0).workerVersionIsOlderThan)
        def workerVersionIsOlderThan(self, command, minversion):
            pass

    def test_signature_getWorkerName(self):
        @self.assertArgSpecMatches(self.get_nth_step(0).getWorkerName)
        def getWorkerName(self):
            pass

    def test_signature_runCommand(self):
        @self.assertArgSpecMatches(self.get_nth_step(0).runCommand)
        def runCommand(self, command):
            pass

    def test_signature_addURL(self):
        @self.assertArgSpecMatches(self.get_nth_step(0).addURL)
        def addURL(self, name, url):
            pass

    def test_signature_addLog(self):
        @self.assertArgSpecMatches(self.get_nth_step(0).addLog)
        def addLog(self, name, type='s', logEncoding=None):
            pass

    def test_signature_getLog(self):
        @self.assertArgSpecMatches(self.get_nth_step(0).getLog)
        def getLog(self, name):
            pass

    def test_signature_addCompleteLog(self):
        @self.assertArgSpecMatches(self.get_nth_step(0).addCompleteLog)
        def addCompleteLog(self, name, text):
            pass

    def test_signature_addHTMLLog(self):
        @self.assertArgSpecMatches(self.get_nth_step(0).addHTMLLog)
        def addHTMLLog(self, name, html):
            pass

    def test_signature_addLogObserver(self):
        @self.assertArgSpecMatches(self.get_nth_step(0).addLogObserver)
        def addLogObserver(self, logname, observer):
            pass


class TestFakeItfc(unittest.TestCase, TestBuildStepMixin, TestReactorMixin, InterfaceTests):
    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        yield self.setup_test_build_step()
        self.setup_step(buildstep.BuildStep())


class TestRealItfc(unittest.TestCase, InterfaceTests):
    def setUp(self):
        self.step = buildstep.BuildStep()

    def get_nth_step(self, index):
        return self.step


class CommandMixinExample(buildstep.CommandMixin, buildstep.BuildStep):
    @defer.inlineCallbacks
    def run(self):
        rv = yield self.testMethod()
        self.method_return_value = rv
        return SUCCESS


class TestCommandMixin(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        yield self.setup_test_build_step()
        self.setup_step(CommandMixinExample())

    @defer.inlineCallbacks
    def test_runRmdir(self):
        self.get_nth_step(0).testMethod = lambda: self.get_nth_step(0).runRmdir('/some/path')
        self.expect_commands(ExpectRmdir(dir='/some/path', log_environ=False).exit(0))
        self.expect_outcome(result=SUCCESS)
        yield self.run_step()
        self.assertTrue(self.get_nth_step(0).method_return_value)

    @defer.inlineCallbacks
    def test_runMkdir(self):
        self.get_nth_step(0).testMethod = lambda: self.get_nth_step(0).runMkdir('/some/path')
        self.expect_commands(ExpectMkdir(dir='/some/path', log_environ=False).exit(0))
        self.expect_outcome(result=SUCCESS)
        yield self.run_step()
        self.assertTrue(self.get_nth_step(0).method_return_value)

    @defer.inlineCallbacks
    def test_runMkdir_fails(self):
        self.get_nth_step(0).testMethod = lambda: self.get_nth_step(0).runMkdir('/some/path')
        self.expect_commands(ExpectMkdir(dir='/some/path', log_environ=False).exit(1))
        self.expect_outcome(result=FAILURE)
        yield self.run_step()

    @defer.inlineCallbacks
    def test_runMkdir_fails_no_abandon(self):
        self.get_nth_step(0).testMethod = lambda: self.get_nth_step(0).runMkdir(
            '/some/path', abandonOnFailure=False
        )
        self.expect_commands(ExpectMkdir(dir='/some/path', log_environ=False).exit(1))
        self.expect_outcome(result=SUCCESS)
        yield self.run_step()
        self.assertFalse(self.get_nth_step(0).method_return_value)

    @defer.inlineCallbacks
    def test_pathExists(self):
        self.get_nth_step(0).testMethod = lambda: self.get_nth_step(0).pathExists('/some/path')
        self.expect_commands(ExpectStat(file='/some/path', log_environ=False).exit(0))
        self.expect_outcome(result=SUCCESS)
        yield self.run_step()
        self.assertTrue(self.get_nth_step(0).method_return_value)

    @defer.inlineCallbacks
    def test_pathExists_doesnt(self):
        self.get_nth_step(0).testMethod = lambda: self.get_nth_step(0).pathExists('/some/path')
        self.expect_commands(ExpectStat(file='/some/path', log_environ=False).exit(1))
        self.expect_outcome(result=SUCCESS)
        yield self.run_step()
        self.assertFalse(self.get_nth_step(0).method_return_value)

    @defer.inlineCallbacks
    def test_pathExists_logging(self):
        self.get_nth_step(0).testMethod = lambda: self.get_nth_step(0).pathExists('/some/path')
        self.expect_commands(
            ExpectStat(file='/some/path', log_environ=False)
            .log('stdio', header='NOTE: never mind\n')
            .exit(1)
        )
        self.expect_outcome(result=SUCCESS)
        yield self.run_step()
        self.assertFalse(self.get_nth_step(0).method_return_value)
        self.assertEqual(
            self.get_nth_step(0).getLog('stdio').header,
            'NOTE: never mind\nprogram finished with exit code 1\n',
        )

    def test_glob(self):
        @defer.inlineCallbacks
        def testFunc():
            res = yield self.get_nth_step(0).runGlob("*.pyc")
            self.assertEqual(res, ["one.pyc", "two.pyc"])

        self.get_nth_step(0).testMethod = testFunc
        self.expect_commands(
            ExpectGlob(path='*.pyc', log_environ=False).files(["one.pyc", "two.pyc"]).exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_glob_empty(self):
        self.get_nth_step(0).testMethod = lambda: self.get_nth_step(0).runGlob("*.pyc")
        self.expect_commands(ExpectGlob(path='*.pyc', log_environ=False).files().exit(0))
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_glob_fail(self):
        self.get_nth_step(0).testMethod = lambda: self.get_nth_step(0).runGlob("*.pyc")
        self.expect_commands(ExpectGlob(path='*.pyc', log_environ=False).exit(1))
        self.expect_outcome(result=FAILURE)
        return self.run_step()


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


class TestShellMixin(
    TestBuildStepMixin, config.ConfigErrorsMixin, TestReactorMixin, unittest.TestCase
):
    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        yield self.setup_test_build_step(with_secrets={"s3cr3t": "really_safe_string"})

    def test_setupShellMixin_bad_arg(self):
        mixin = SimpleShellCommand()
        with self.assertRaisesConfigError("invalid SimpleShellCommand argument invarg"):
            mixin.setupShellMixin({'invarg': 13})

    def test_setupShellMixin_prohibited_arg(self):
        mixin = SimpleShellCommand()
        with self.assertRaisesConfigError("invalid SimpleShellCommand argument logfiles"):
            mixin.setupShellMixin({'logfiles': None}, prohibitArgs=['logfiles'])

    def test_constructor_defaults(self):
        class MySubclass(SimpleShellCommand):
            timeout = 9999

        # ShellMixin arg
        self.assertEqual(MySubclass().timeout, 9999)
        self.assertEqual(MySubclass(timeout=88).timeout, 88)
        # BuildStep arg
        self.assertEqual(MySubclass().logEncoding, None)
        self.assertEqual(MySubclass(logEncoding='latin-1').logEncoding, 'latin-1')
        self.assertEqual(MySubclass().description, None)
        self.assertEqual(MySubclass(description='charming').description, ['charming'])

    @defer.inlineCallbacks
    def test_prohibit_args(self):
        self.setup_step(
            SimpleShellCommand(
                prohibit_args=['command'], make_cmd_kwargs={'command': ['cmd', 'arg']}
            )
        )
        self.expect_commands(ExpectShell(workdir='wkdir', command=['cmd', 'arg']).exit(0))
        self.expect_outcome(result=SUCCESS)
        yield self.run_step()

    def test_bad_arg_type(self):
        mixin = SimpleShellCommand()
        with self.assertRaisesConfigError(
            "SimpleShellCommand argument usePTY must be an instance of bool"
        ):
            mixin.setupShellMixin({'usePTY': 13})

    @defer.inlineCallbacks
    def test_no_default_workdir(self):
        self.setup_step(SimpleShellCommand(command=['cmd', 'arg']), want_default_work_dir=False)
        self.expect_commands(ExpectShell(workdir='build', command=['cmd', 'arg']).exit(0))
        self.expect_outcome(result=SUCCESS)
        yield self.run_step()

    @defer.inlineCallbacks
    def test_build_workdir(self):
        self.setup_step(SimpleShellCommand(command=['cmd', 'arg']), want_default_work_dir=False)
        self.build.workdir = '/alternate'
        self.expect_commands(ExpectShell(workdir='/alternate', command=['cmd', 'arg']).exit(0))
        self.expect_outcome(result=SUCCESS)
        yield self.run_step()

    @defer.inlineCallbacks
    def test_build_workdir_callable(self):
        self.setup_step(SimpleShellCommand(command=['cmd', 'arg']), want_default_work_dir=False)
        self.build.workdir = lambda x: '/alternate'
        self.expect_commands(ExpectShell(workdir='/alternate', command=['cmd', 'arg']).exit(0))
        self.expect_outcome(result=SUCCESS)
        yield self.run_step()

    @defer.inlineCallbacks
    def test_build_workdir_callable_error(self):
        self.setup_step(SimpleShellCommand(command=['cmd', 'arg']), want_default_work_dir=False)
        self.build.workdir = lambda x: x.nosuchattribute  # will raise AttributeError
        self.expect_exception(buildstep.CallableAttributeError)
        yield self.run_step()

    @defer.inlineCallbacks
    def test_build_workdir_renderable(self):
        self.setup_step(SimpleShellCommand(command=['cmd', 'arg']), want_default_work_dir=False)
        self.build.workdir = properties.Property("myproperty")
        self.build.setProperty("myproperty", "/myproperty", "test")
        self.expect_commands(ExpectShell(workdir='/myproperty', command=['cmd', 'arg']).exit(0))
        self.expect_outcome(result=SUCCESS)
        yield self.run_step()

    @defer.inlineCallbacks
    def test_step_workdir(self):
        self.setup_step(SimpleShellCommand(command=['cmd', 'arg'], workdir='/stepdir'))
        self.build.workdir = '/builddir'
        self.expect_commands(ExpectShell(workdir='/stepdir', command=['cmd', 'arg']).exit(0))
        self.expect_outcome(result=SUCCESS)
        yield self.run_step()

    @defer.inlineCallbacks
    def test_step_renderable_workdir(self):
        @renderer
        def rendered_workdir(_):
            return '/stepdir'

        self.setup_step(SimpleShellCommand(command=['cmd', 'arg'], workdir=rendered_workdir))
        self.build.workdir = '/builddir'
        self.expect_commands(ExpectShell(workdir='/stepdir', command=['cmd', 'arg']).exit(0))
        self.expect_outcome(result=SUCCESS)
        yield self.run_step()

    @defer.inlineCallbacks
    def test_step_workdir_overridden(self):
        self.setup_step(
            SimpleShellCommand(
                command=['cmd', 'arg'],
                workdir='/stepdir',
                make_cmd_kwargs={'workdir': '/overridden'},
            )
        )
        self.build.workdir = '/builddir'
        self.expect_commands(ExpectShell(workdir='/overridden', command=['cmd', 'arg']).exit(0))
        self.expect_outcome(result=SUCCESS)
        yield self.run_step()

    @defer.inlineCallbacks
    def test_step_env_default(self):
        env = {'ENV': 'TRUE'}
        self.setup_step(SimpleShellCommand(command=['cmd', 'arg'], env=env))
        self.expect_commands(ExpectShell(workdir='wkdir', command=['cmd', 'arg'], env=env).exit(0))
        self.expect_outcome(result=SUCCESS)
        yield self.run_step()

    @defer.inlineCallbacks
    def test_step_env_overridden(self):
        env = {'ENV': 'TRUE'}
        env_override = {'OVERRIDE': 'TRUE'}
        self.setup_step(
            SimpleShellCommand(
                command=['cmd', 'arg'], env=env, make_cmd_kwargs={'env': env_override}
            )
        )
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['cmd', 'arg'], env=env_override).exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        yield self.run_step()

    @defer.inlineCallbacks
    def test_extra_logfile(self):
        self.setup_step(
            SimpleShellCommand(command=['cmd', 'arg'], logfiles={'logname': 'logpath.log'})
        )
        self.expect_commands(
            ExpectShell(
                workdir='wkdir', command=['cmd', 'arg'], logfiles={'logname': 'logpath.log'}
            )
            .log('logname', stdout='logline\nlogline2\n')
            .stdout("some log\n")
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        yield self.run_step()
        self.assertEqual(self.get_nth_step(0).getLog('logname').stdout, 'logline\nlogline2\n')

    @defer.inlineCallbacks
    def test_lazy_logfiles_stdout_has_stdout(self):
        self.setup_step(SimpleShellCommand(command=['cmd', 'arg'], lazylogfiles=True))
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['cmd', 'arg']).stdout("some log\n").exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        yield self.run_step()
        self.assertEqual(self.get_nth_step(0).getLog('stdio').stdout, 'some log\n')

    @defer.inlineCallbacks
    def test_lazy_logfiles_stdout_no_stdout(self):
        # lazy log files do not apply to stdout
        self.setup_step(SimpleShellCommand(command=['cmd', 'arg'], lazylogfiles=True))
        self.expect_commands(ExpectShell(workdir='wkdir', command=['cmd', 'arg']).exit(0))
        self.expect_outcome(result=SUCCESS)
        yield self.run_step()
        self.assertEqual(self.get_nth_step(0).getLog('stdio').stdout, '')

    @defer.inlineCallbacks
    def test_lazy_logfiles_logfile(self):
        self.setup_step(
            SimpleShellCommand(
                command=['cmd', 'arg'], lazylogfiles=True, logfiles={'logname': 'logpath.log'}
            )
        )
        self.expect_commands(
            ExpectShell(
                workdir='wkdir', command=['cmd', 'arg'], logfiles={'logname': 'logpath.log'}
            )
            .log('logname', stdout='logline\nlogline2\n')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        yield self.run_step()
        self.assertEqual(self.get_nth_step(0).getLog('logname').stdout, 'logline\nlogline2\n')

    @defer.inlineCallbacks
    def test_lazy_logfiles_no_logfile(self):
        self.setup_step(
            SimpleShellCommand(
                command=['cmd', 'arg'], lazylogfiles=True, logfiles={'logname': 'logpath.log'}
            )
        )
        self.expect_commands(
            ExpectShell(
                workdir='wkdir', command=['cmd', 'arg'], logfiles={'logname': 'logpath.log'}
            ).exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        yield self.run_step()
        with self.assertRaises(KeyError):
            self.get_nth_step(0).getLog('logname')

    @defer.inlineCallbacks
    def test_env(self):
        self.setup_step(SimpleShellCommand(command=['cmd', 'arg'], env={'BAR': 'BAR'}))
        self.build.builder.config.env = {'FOO': 'FOO'}
        self.expect_commands(
            ExpectShell(
                workdir='wkdir', command=['cmd', 'arg'], env={'FOO': 'FOO', 'BAR': 'BAR'}
            ).exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        yield self.run_step()

    @defer.inlineCallbacks
    def test_old_worker_args(self):
        self.setup_build(worker_version={'*': "1.1"})
        self.setup_step(
            SimpleShellCommand(command=['cmd', 'arg'], usePTY=False, interruptSignal='DIE')
        )
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['cmd', 'arg']).exit(0)
            # note missing parameters
        )
        self.expect_outcome(result=SUCCESS)
        yield self.run_step()
        self.assertEqual(
            self.get_nth_step(0).getLog('stdio').header,
            'NOTE: worker does not allow master to override usePTY\n'
            'NOTE: worker does not allow master to specify interruptSignal\n'
            'program finished with exit code 0\n',
        )

    @defer.inlineCallbacks
    def test_new_worker_args(self):
        self.setup_build(worker_version={'*': "3.0"})
        self.setup_step(
            SimpleShellCommand(command=['cmd', 'arg'], usePTY=False, interruptSignal='DIE')
        )
        self.expect_commands(
            ExpectShell(
                workdir='wkdir', use_pty=False, interrupt_signal='DIE', command=['cmd', 'arg']
            ).exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        yield self.run_step()
        self.assertEqual(
            self.get_nth_step(0).getLog('stdio').header, 'program finished with exit code 0\n'
        )

    @defer.inlineCallbacks
    def test_description(self):
        self.setup_step(SimpleShellCommand(command=['foo', properties.Property('bar', 'BAR')]))
        self.expect_commands(ExpectShell(workdir='wkdir', command=['foo', 'BAR']).exit(0))
        self.expect_outcome(result=SUCCESS, state_string="'foo BAR'")
        yield self.run_step()

    @parameterized.expand(["timeout", "timeout_without_output"])
    @defer.inlineCallbacks
    def test_description_timed_out(self, failure_reason):
        self.setup_step(SimpleShellCommand(command=["foo"]))
        self.expect_commands(
            ExpectShell(workdir="wkdir", command=["foo"])
            .update("failure_reason", failure_reason)
            .exit(1)
        )
        self.expect_outcome(result=FAILURE, state_string="'foo' (failure) (timed out)")
        yield self.run_step()

    def test_getResultSummary(self):
        self.setup_step(SimpleShellCommand(command=['a', ['b', 'c']]))
        self.get_nth_step(0).results = SUCCESS
        self.assertEqual(self.get_nth_step(0).getResultSummary(), {'step': "'a b ...'"})

    @async_to_deferred
    async def test_step_with_secret_success(self):
        self.setup_step(SimpleShellCommand(command=["echo", Secret("s3cr3t")]))
        self.expect_commands(
            ExpectShell(workdir="wkdir", command=["echo", 'really_safe_string']).exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="'echo <s3cr3t>'")
        summary = "'echo <s3cr3t>'"
        self.expect_result_summary({'step': summary})
        self.expect_build_result_summary({'step': summary})
        await self.run_step()

    @async_to_deferred
    async def test_step_with_secret_failure(self):
        self.setup_step(SimpleShellCommand(command=["echo", Secret("s3cr3t")]))
        self.expect_commands(
            ExpectShell(workdir="wkdir", command=["echo", 'really_safe_string']).exit(1)
        )
        self.expect_outcome(result=FAILURE, state_string="'echo <s3cr3t>' (failure)")
        summary = "'echo <s3cr3t>' (failure)"
        self.expect_result_summary({'step': summary})
        self.expect_build_result_summary({'step': summary, 'build': summary})
        await self.run_step()
