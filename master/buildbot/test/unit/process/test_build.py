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
from __future__ import annotations

import operator
import posixpath
from datetime import datetime
from itertools import count
from pathlib import PurePosixPath
from typing import TYPE_CHECKING
from typing import Any
from typing import cast
from unittest.mock import Mock
from unittest.mock import call

from twisted.internet import defer
from twisted.trial import unittest
from zope.interface import implementer

from buildbot import interfaces
from buildbot.locks import WorkerLock
from buildbot.process.build import Build
from buildbot.process.buildrequest import BuildRequest
from buildbot.process.buildrequest import TempChange
from buildbot.process.buildrequest import TempSourceStamp
from buildbot.process.buildstep import BuildStep
from buildbot.process.buildstep import create_step_from_step_or_factory
from buildbot.process.locks import get_real_locks_from_accesses
from buildbot.process.metrics import MetricLogObserver
from buildbot.process.properties import Properties
from buildbot.process.properties import renderer
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.fake import fakeprotocol
from buildbot.test.fake import worker
from buildbot.test.reactor import TestReactorMixin

if TYPE_CHECKING:
    from collections.abc import Iterable

    from twisted.python.failure import Failure

    from buildbot.interfaces import IBuildStep
    from buildbot.interfaces import IProperties
    from buildbot.locks import BaseLock
    from buildbot.locks import LockAccess
    from buildbot.master import BuildMaster
    from buildbot.process.builder import Builder
    from buildbot.process.workerforbuilder import AbstractWorkerForBuilder
    from buildbot.util.twisted import InlineCallbacksType
    from buildbot.worker.protocols.base import Connection


class FakeChange:
    def __init__(self, number: int | None = None) -> None:
        self.properties = Properties()
        self.number = number
        self.who = "me"


class FakeSource:
    def __init__(self) -> None:
        self.sourcestampsetid = None
        self.changes = []  # type: ignore[var-annotated]
        self.branch = None
        self.revision = None
        self.repository = ''
        self.codebase = ''
        self.project = ''
        self.patch_info = None
        self.patch = None

    def getRepository(self) -> str:
        return self.repository


class FakeRequest:
    def __init__(self) -> None:
        self.sources = []  # type: ignore[var-annotated]
        self.reason = "Because"
        self.properties = Properties()
        self.id = 9385

    def mergeSourceStampsWith(self, others: Iterable[BuildRequest]) -> list[TempSourceStamp]:
        return self.sources

    def mergeReasons(self, others: list[BuildRequest]) -> str:
        return self.reason


class FakeBuildStep(BuildStep):
    def __init__(self) -> None:
        super().__init__(
            haltOnFailure=False,
            flunkOnWarnings=False,
            flunkOnFailure=True,
            warnOnWarnings=True,
            warnOnFailure=False,
            alwaysRun=False,
            name='fake',
        )
        self._summary = {'step': 'result', 'build': 'build result'}
        self._expected_results = SUCCESS

    def run(self) -> int:  # type: ignore[override]
        return self._expected_results

    def getResultSummary(self) -> dict[str, str]:
        return self._summary

    def interrupt(self, reason: str | Failure) -> None:  # type: ignore[override]
        self.running = False
        self.interrupted = reason


class FakeBuilder:
    def __init__(self, master: BuildMaster) -> None:
        self.config = Mock()
        self.config.workerbuilddir = 'wbd'
        self.config.description = 'builder-description'
        self.config.env = {}
        self.name = 'fred'
        self.master = master
        self.botmaster = master.botmaster
        self.builderid = 83
        self._builders = {}  # type: ignore[var-annotated]
        self.config_version = 0

    def getBuilderId(self) -> defer.Deferred[int]:
        return defer.succeed(self.builderid)

    def setup_properties(self, props: Properties) -> defer.Deferred[None]:
        return defer.succeed(None)

    def buildFinished(self, build: Build, workerforbuilder: AbstractWorkerForBuilder) -> None:
        pass

    def getBuilderIdForName(self, name: str) -> defer.Deferred[int | None]:
        return defer.succeed(self._builders.get(name, None) or self.builderid)

    def find_project_id(self, name: str) -> defer.Deferred[None]:
        return defer.succeed(None)


@implementer(interfaces.IBuildStepFactory)
class FakeStepFactory:
    """Fake step factory that just returns a fixed step object."""

    def __init__(self, step: IBuildStep) -> None:
        self.step = step

    def buildStep(self) -> IBuildStep:
        return self.step


class TestException(Exception):
    pass


@implementer(interfaces.IBuildStepFactory)
class FailingStepFactory:
    """Fake step factory that just returns a fixed step object."""

    def buildStep(self) -> None:  # type: ignore[override]
        raise TestException("FailingStepFactory")


class _StepController:
    def __init__(self, step: _ControllableStep) -> None:
        self._step = step

    def finishStep(self, result: int) -> None:
        self._step._deferred.callback(result)


class _ControllableStep(BuildStep):
    def __init__(self) -> None:
        super().__init__()
        self._deferred = defer.Deferred()  # type: ignore[var-annotated]

    def run(self) -> defer.Deferred[int]:
        return self._deferred


def makeControllableStepFactory() -> tuple[_StepController, FakeStepFactory]:
    step = create_step_from_step_or_factory(_ControllableStep())
    controller = _StepController(cast(_ControllableStep, step))
    return controller, FakeStepFactory(step)


class TestBuild(TestReactorMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        r = FakeRequest()
        r.sources = [FakeSource()]
        r.sources[0].changes = [FakeChange()]
        r.sources[0].revision = "12345"

        self.request = r
        self.master = yield fakemaster.make_master(self, wantData=True)

        yield self.master.db.insert_test_data([
            fakedb.Master(id=fakedb.FakeDBConnector.MASTER_ID),
            fakedb.Worker(id=1234),
            fakedb.Builder(id=83),
            fakedb.Buildset(id=8822),
            fakedb.BuildRequest(id=9385, builderid=83, buildsetid=8822),
        ])

        self.worker = worker.FakeWorker(self.master)
        self.worker.attached(None)
        self.builder = FakeBuilder(self.master)
        self.build = Build([r], self.builder)  # type: ignore[arg-type, list-item]
        self.build.conn = fakeprotocol.FakeConnection(self.worker)
        self.build.workername = self.worker.workername

        self.workerforbuilder = Mock(name='workerforbuilder')
        self.workerforbuilder.worker = self.worker
        self.workerforbuilder.substantiate_if_needed = lambda _: True
        self.workerforbuilder.ping = lambda: True

        self.build.workerforbuilder = self.workerforbuilder
        self.build.text = []
        self.build.buildid = 666

    @defer.inlineCallbacks
    def assert_worker_preparation_failure(self, reason: str) -> InlineCallbacksType[None]:
        steps = yield self.master.data.get(('builds', self.build.buildid, 'steps'))
        self.assertIn(steps[-1]['state_string'], reason)

    def create_fake_build_step(self) -> FakeBuildStep:
        return create_step_from_step_or_factory(FakeBuildStep())  # type: ignore[return-value]

    def _setup_lock_claim_log(self, lock: BaseLock, claim_log: list[object]) -> None:
        if hasattr(lock, "_old_claim"):
            return

        def claim(owner: object, access: LockAccess) -> None:
            claim_log.append(owner)
            return lock._old_claim(owner, access)  # type: ignore[attr-defined]

        lock._old_claim = lock.claim  # type: ignore[attr-defined]
        lock.claim = claim  # type: ignore[method-assign]

    def testRunSuccessfulBuild(self) -> None:
        b = self.build

        step = self.create_fake_build_step()
        b.setStepFactories([FakeStepFactory(step)])

        b.startBuild(self.workerforbuilder)

        self.assertEqual(b.results, SUCCESS)

    def testStopBuild(self) -> None:
        b = self.build

        step = self.create_fake_build_step()
        b.setStepFactories([FakeStepFactory(step)])

        def startStep(remote: Connection) -> defer.Deferred[int]:
            # Now interrupt the build
            b.stopBuild("stop it")
            return defer.Deferred()

        step.startStep = startStep  # type: ignore[method-assign]

        b.startBuild(self.workerforbuilder)

        self.assertEqual(b.results, CANCELLED)

        self.assertIn('stop it', step.interrupted)

    @defer.inlineCallbacks
    def test_build_retry_when_worker_substantiate_returns_false(self) -> InlineCallbacksType[None]:
        b = self.build

        step = self.create_fake_build_step()
        b.setStepFactories([FakeStepFactory(step)])

        self.workerforbuilder.substantiate_if_needed = lambda _: False

        yield b.startBuild(self.workerforbuilder)
        self.assertEqual(b.results, RETRY)
        yield self.assert_worker_preparation_failure('error while worker_prepare')

    @defer.inlineCallbacks
    def test_build_cancelled_when_worker_substantiate_returns_false_due_to_cancel(
        self,
    ) -> InlineCallbacksType[None]:
        b = self.build

        step = self.create_fake_build_step()
        b.setStepFactories([FakeStepFactory(step)])

        substantiation_d = defer.Deferred()  # type: ignore[var-annotated]
        self.workerforbuilder.substantiate_if_needed = lambda _: substantiation_d

        build_d = b.startBuild(self.workerforbuilder)
        b.stopBuild('Cancel Build', CANCELLED)

        substantiation_d.callback(False)
        yield build_d

        self.assertEqual(b.results, CANCELLED)
        yield self.assert_worker_preparation_failure('pending')

    @defer.inlineCallbacks
    def test_build_retry_when_worker_substantiate_returns_false_due_to_cancel(
        self,
    ) -> InlineCallbacksType[None]:
        b = self.build

        step = self.create_fake_build_step()
        b.setStepFactories([FakeStepFactory(step)])

        d = defer.Deferred()  # type: ignore[var-annotated]
        self.workerforbuilder.substantiate_if_needed = lambda _: d
        b.startBuild(self.workerforbuilder)
        b.stopBuild('Cancel Build', RETRY)
        d.callback(False)
        self.assertEqual(b.results, RETRY)
        yield self.assert_worker_preparation_failure('pending')

    @defer.inlineCallbacks
    def testAlwaysRunStepStopBuild(self) -> InlineCallbacksType[None]:
        """Test that steps marked with alwaysRun=True still get run even if
        the build is stopped."""

        # Create a build with 2 steps, the first one will get interrupted, and
        # the second one is marked with alwaysRun=True
        b = self.build

        step1 = self.create_fake_build_step()
        step1.alwaysRun = False
        step1.results = None
        step2 = self.create_fake_build_step()
        step2.alwaysRun = True
        step2.results = None
        b.setStepFactories([
            FakeStepFactory(step1),
            FakeStepFactory(step2),
        ])

        def startStep1(remote: Connection) -> defer.Deferred[int]:
            # Now interrupt the build
            b.stopBuild("stop it")
            return defer.succeed(SUCCESS)

        step1.startStep = startStep1  # type: ignore[method-assign]
        step1.stepDone = lambda: False  # type: ignore[attr-defined]

        step2Started = [False]

        def startStep2(remote: Connection) -> defer.Deferred[int]:
            step2Started[0] = True
            return defer.succeed(SUCCESS)

        step2.startStep = startStep2  # type: ignore[method-assign]
        step1.stepDone = lambda: False  # type: ignore[attr-defined]

        yield b.startBuild(self.workerforbuilder)

        self.assertEqual(b.results, CANCELLED)
        self.assertIn('stop it', step1.interrupted)
        self.assertTrue(step2Started[0])

    @defer.inlineCallbacks
    def test_start_step_throws_exception(self) -> InlineCallbacksType[None]:
        b = self.build

        step1 = self.create_fake_build_step()
        b.setStepFactories([
            FakeStepFactory(step1),
        ])

        def startStep(remote: Connection) -> None:
            raise TestException()

        step1.startStep = startStep  # type: ignore[method-assign, assignment]

        yield b.startBuild(self.workerforbuilder)

        self.assertEqual(b.results, EXCEPTION)
        self.flushLoggedErrors(TestException)

    def testBuilddirPropType(self) -> None:
        b = self.build

        b.builder.config.workerbuilddir = 'test'  # type: ignore[union-attr]
        self.workerforbuilder.worker.worker_basedir = "/srv/buildbot/worker"
        self.workerforbuilder.worker.path_module = posixpath
        self.workerforbuilder.worker.path_cls = PurePosixPath
        b.getProperties = Mock()  # type: ignore[method-assign]
        b.setProperty = Mock()  # type: ignore[method-assign]

        b.setupWorkerProperties(self.workerforbuilder)

        expected_path = '/srv/buildbot/worker/test'

        b.setProperty.assert_has_calls([call('builddir', expected_path, 'Worker')], any_order=True)

    @defer.inlineCallbacks
    def testBuildLocksAcquired(self) -> InlineCallbacksType[None]:
        b = self.build

        lock = WorkerLock('lock')
        claim_log = []  # type: ignore[var-annotated]
        lock_access = lock.access('counting')
        lock.access = lambda mode: lock_access  # type: ignore[assignment, method-assign, misc]

        b.setLocks([lock_access])  # type: ignore[list-item]
        yield b._setup_locks()

        self._setup_lock_claim_log(b._locks_to_acquire[0][0], claim_log)

        step = self.create_fake_build_step()
        b.setStepFactories([FakeStepFactory(step)])

        b.startBuild(self.workerforbuilder)

        self.assertEqual(b.results, SUCCESS)
        self.assertEqual(len(claim_log), 1)

    @defer.inlineCallbacks
    def test_build_locks_acquired_renderable(self) -> InlineCallbacksType[None]:
        b = self.build

        lock = WorkerLock('lock')
        claim_log = []  # type: ignore[var-annotated]
        lock_access = lock.access('counting')
        lock.access = lambda mode: lock_access  # type: ignore[assignment, method-assign, misc]

        @renderer
        def render_locks(props: IProperties) -> list[LockAccess]:
            return [lock_access]

        b.setLocks(render_locks)
        yield b._setup_locks()

        self._setup_lock_claim_log(b._locks_to_acquire[0][0], claim_log)

        step = self.create_fake_build_step()
        b.setStepFactories([FakeStepFactory(step)])

        b.startBuild(self.workerforbuilder)

        self.assertEqual(b.results, SUCCESS)
        self.assertEqual(len(claim_log), 1)

    @defer.inlineCallbacks
    def testBuildLocksOrder(self) -> InlineCallbacksType[None]:
        """Test that locks are acquired in FIFO order; specifically that
        counting locks cannot jump ahead of exclusive locks"""
        eBuild = self.build
        cBuilder = FakeBuilder(self.master)
        cBuild = Build([self.request], cBuilder)  # type: ignore[arg-type, list-item]
        cBuild.workerforbuilder = self.workerforbuilder
        cBuild.workername = self.worker.workername

        eWorker = Mock()
        cWorker = Mock()

        eWorker.worker = self.worker
        cWorker.worker = self.worker
        eWorker.substantiate_if_needed = cWorker.substantiate_if_needed = lambda _: True
        eWorker.ping = cWorker.ping = lambda: True

        lock = WorkerLock('lock', 2)
        claim_log = []  # type: ignore[var-annotated]

        eBuild.setLocks([lock.access('exclusive')])  # type: ignore[list-item]
        yield eBuild._setup_locks()

        cBuild.setLocks([lock.access('counting')])  # type: ignore[list-item]
        yield cBuild._setup_locks()

        self._setup_lock_claim_log(eBuild._locks_to_acquire[0][0], claim_log)
        self._setup_lock_claim_log(cBuild._locks_to_acquire[0][0], claim_log)

        real_lock = eBuild._locks_to_acquire[0][0]

        b3 = Mock()
        b3_access = lock.access('counting')
        real_lock.claim(b3, b3_access)

        step = self.create_fake_build_step()
        eBuild.setStepFactories([FakeStepFactory(step)])
        cBuild.setStepFactories([FakeStepFactory(step)])

        e = eBuild.startBuild(eWorker)
        c = cBuild.startBuild(cWorker)
        d = defer.DeferredList([e, c], consumeErrors=True)

        real_lock.release(b3, b3_access)

        yield d
        self.assertEqual(eBuild.results, SUCCESS)
        self.assertEqual(cBuild.results, SUCCESS)
        self.assertEqual(claim_log, [b3, eBuild, cBuild])

    @defer.inlineCallbacks
    def testBuildWaitingForLocks(self) -> InlineCallbacksType[None]:
        b = self.build

        claim_log = []  # type: ignore[var-annotated]

        lock = WorkerLock('lock')
        lock_access = lock.access('counting')

        b.setLocks([lock_access])  # type: ignore[list-item]
        yield b._setup_locks()
        self._setup_lock_claim_log(b._locks_to_acquire[0][0], claim_log)

        step = self.create_fake_build_step()
        b.setStepFactories([FakeStepFactory(step)])

        real_lock = b._locks_to_acquire[0][0]
        real_lock.claim(Mock(), lock.access('counting'))

        b.startBuild(self.workerforbuilder)

        self.assertEqual(len(claim_log), 1)
        self.assertTrue(b.currentStep is None)
        self.assertTrue(b._acquiringLock is not None)

    @defer.inlineCallbacks
    def testStopBuildWaitingForLocks(self) -> InlineCallbacksType[None]:
        b = self.build

        lock = WorkerLock('lock')
        lock_access = lock.access('counting')

        b.setLocks([lock_access])  # type: ignore[list-item]
        yield b._setup_locks()

        step = self.create_fake_build_step()
        step.alwaysRun = False
        b.setStepFactories([FakeStepFactory(step)])

        real_lock = b._locks_to_acquire[0][0]
        real_lock.claim(Mock(), lock.access('counting'))

        def acquireLocks(res: BaseLock | None = None) -> defer.Deferred[None]:
            retval = Build.acquireLocks(b, res)
            b.stopBuild('stop it')
            return retval

        b.acquireLocks = acquireLocks  # type: ignore[method-assign]

        b.startBuild(self.workerforbuilder)

        self.assertTrue(b.currentStep is None)
        self.assertEqual(b.results, CANCELLED)

    @defer.inlineCallbacks
    def testStopBuildWaitingForLocks_lostRemote(self) -> InlineCallbacksType[None]:
        b = self.build

        lock = WorkerLock('lock')
        lock_access = lock.access('counting')
        lock.access = lambda mode: lock_access  # type: ignore[assignment, method-assign, misc]

        b.setLocks([lock_access])  # type: ignore[list-item]
        yield b._setup_locks()

        step = self.create_fake_build_step()
        step.alwaysRun = False
        b.setStepFactories([FakeStepFactory(step)])

        real_lock = b._locks_to_acquire[0][0]
        real_lock.claim(Mock(), lock.access('counting'))

        def acquireLocks(res: BaseLock | None = None) -> defer.Deferred[None]:
            retval = Build.acquireLocks(b, res)
            b.lostRemote()
            return retval

        b.acquireLocks = acquireLocks  # type: ignore[method-assign]

        b.startBuild(self.workerforbuilder)

        self.assertTrue(b.currentStep is None)
        self.assertEqual(b.results, RETRY)

    @defer.inlineCallbacks
    def testStopBuildWaitingForStepLocks(self) -> InlineCallbacksType[None]:
        b = self.build

        lock = WorkerLock('lock')
        lock_access = lock.access('counting')

        locks = yield get_real_locks_from_accesses([lock_access], b)

        step = create_step_from_step_or_factory(BuildStep(locks=[lock_access]))
        b.setStepFactories([FakeStepFactory(step)])

        locks[0][0].claim(Mock(), lock.access('counting'))

        gotLocks = [False]

        def acquireLocks(res: BaseLock | None = None) -> defer.Deferred[None | BaseLock]:
            gotLocks[0] = True
            retval = BuildStep.acquireLocks(step, res)  # type: ignore[arg-type]
            self.assertTrue(b.currentStep is step)
            b.stopBuild('stop it')
            return retval

        step.acquireLocks = acquireLocks  # type: ignore[attr-defined]

        b.startBuild(self.workerforbuilder)

        self.assertEqual(gotLocks, [True])
        self.assertEqual(b.results, CANCELLED)

    def testStepDone(self) -> None:
        b = self.build
        b.results = SUCCESS
        step = self.create_fake_build_step()
        terminate = b.stepDone(SUCCESS, step)
        self.assertFalse(terminate.result)
        self.assertEqual(b.results, SUCCESS)

    def testStepDoneHaltOnFailure(self) -> None:
        b = self.build
        b.results = SUCCESS
        step = self.create_fake_build_step()
        step.haltOnFailure = True
        terminate = b.stepDone(FAILURE, step)
        self.assertTrue(terminate.result)
        self.assertEqual(b.results, FAILURE)

    def testStepDoneHaltOnFailureNoFlunkOnFailure(self) -> None:
        b = self.build
        b.results = SUCCESS
        step = self.create_fake_build_step()
        step.flunkOnFailure = False
        step.haltOnFailure = True
        terminate = b.stepDone(FAILURE, step)
        self.assertTrue(terminate.result)
        self.assertEqual(b.results, SUCCESS)

    def testStepDoneFlunkOnWarningsFlunkOnFailure(self) -> None:
        b = self.build
        b.results = SUCCESS
        step = self.create_fake_build_step()
        step.flunkOnFailure = True
        step.flunkOnWarnings = True
        b.stepDone(WARNINGS, step)
        terminate = b.stepDone(FAILURE, step)
        self.assertFalse(terminate.result)
        self.assertEqual(b.results, FAILURE)

    def testStepDoneNoWarnOnWarnings(self) -> None:
        b = self.build
        b.results = SUCCESS
        step = self.create_fake_build_step()
        step.warnOnWarnings = False
        terminate = b.stepDone(WARNINGS, step)
        self.assertFalse(terminate.result)
        self.assertEqual(b.results, SUCCESS)

    def testStepDoneWarnings(self) -> None:
        b = self.build
        b.results = SUCCESS
        step = self.create_fake_build_step()
        terminate = b.stepDone(WARNINGS, step)
        self.assertFalse(terminate.result)
        self.assertEqual(b.results, WARNINGS)

    def testStepDoneFail(self) -> None:
        b = self.build
        b.results = SUCCESS
        step = self.create_fake_build_step()
        terminate = b.stepDone(FAILURE, step)
        self.assertFalse(terminate.result)
        self.assertEqual(b.results, FAILURE)

    def testStepDoneFailOverridesWarnings(self) -> None:
        b = self.build
        b.results = WARNINGS
        step = self.create_fake_build_step()
        terminate = b.stepDone(FAILURE, step)
        self.assertFalse(terminate.result)
        self.assertEqual(b.results, FAILURE)

    def testStepDoneWarnOnFailure(self) -> None:
        b = self.build
        b.results = SUCCESS
        step = self.create_fake_build_step()
        step.warnOnFailure = True
        step.flunkOnFailure = False
        terminate = b.stepDone(FAILURE, step)
        self.assertFalse(terminate.result)
        self.assertEqual(b.results, WARNINGS)

    def testStepDoneFlunkOnWarnings(self) -> None:
        b = self.build
        b.results = SUCCESS
        step = self.create_fake_build_step()
        step.flunkOnWarnings = True
        terminate = b.stepDone(WARNINGS, step)
        self.assertFalse(terminate.result)
        self.assertEqual(b.results, FAILURE)

    def testStepDoneHaltOnFailureFlunkOnWarnings(self) -> None:
        b = self.build
        b.results = SUCCESS
        step = self.create_fake_build_step()
        step.flunkOnWarnings = True
        self.haltOnFailure = True
        terminate = b.stepDone(WARNINGS, step)
        self.assertFalse(terminate.result)
        self.assertEqual(b.results, FAILURE)

    def testStepDoneWarningsDontOverrideFailure(self) -> None:
        b = self.build
        b.results = FAILURE
        step = self.create_fake_build_step()
        terminate = b.stepDone(WARNINGS, step)
        self.assertFalse(terminate.result)
        self.assertEqual(b.results, FAILURE)

    def testStepDoneRetryOverridesAnythingElse(self) -> None:
        b = self.build
        b.results = RETRY
        step = self.create_fake_build_step()
        step.alwaysRun = True
        b.stepDone(WARNINGS, step)
        b.stepDone(FAILURE, step)
        b.stepDone(SUCCESS, step)
        terminate = b.stepDone(EXCEPTION, step)
        self.assertTrue(terminate.result)
        self.assertEqual(b.results, RETRY)

    def test_getSummaryStatistic(self) -> None:
        b = self.build

        b.executedSteps = [BuildStep(), BuildStep(), BuildStep()]
        b.executedSteps[0].setStatistic('casualties', 7)  # type: ignore[attr-defined]
        b.executedSteps[2].setStatistic('casualties', 4)  # type: ignore[attr-defined]

        add = operator.add
        self.assertEqual(b.getSummaryStatistic('casualties', add), 11)
        self.assertEqual(b.getSummaryStatistic('casualties', add, 10), 21)

    def create_fake_steps(self, names: Iterable[str]) -> list[FakeBuildStep]:
        steps: list[FakeBuildStep] = []

        def create_fake_step(name: str) -> FakeBuildStep:
            step = self.create_fake_build_step()
            step.name = name
            return step

        for name in names:
            step = create_fake_step(name)
            steps.append(step)
        return steps

    @defer.inlineCallbacks
    def test_start_build_sets_properties(self) -> InlineCallbacksType[None]:
        b = self.build
        b.setProperty("foo", "bar", "test")

        step = create_step_from_step_or_factory(self.create_fake_build_step())
        b.setStepFactories([FakeStepFactory(step)])

        yield b.startBuild(self.workerforbuilder)
        self.assertEqual(b.results, SUCCESS)

        properties = yield self.master.data.get(('builds', 1, 'properties'))
        del properties['builddir']  # contains per-platform data
        self.assertEqual(
            properties,
            {
                'basedir': ('/wrk', 'Worker'),
                'branch': (None, 'Build'),
                'buildnumber': (1, 'Build'),
                'codebase': ('', 'Build'),
                'foo': ('bar', 'test'),  # custom property
                'owners': (['me'], 'Build'),
                'project': ('', 'Build'),
                'repository': ('', 'Build'),
                'revision': ('12345', 'Build'),
            },
        )

    @defer.inlineCallbacks
    def testAddStepsAfterCurrentStep(self) -> InlineCallbacksType[None]:
        b = self.build

        steps = self.create_fake_steps(["a", "b", "c"])

        def startStepB(remote: Connection) -> int:
            new_steps = self.create_fake_steps(["d", "e"])
            b.addStepsAfterCurrentStep([FakeStepFactory(s) for s in new_steps])
            return SUCCESS

        steps[1].startStep = startStepB  # type: ignore[method-assign, assignment]
        b.setStepFactories([FakeStepFactory(s) for s in steps])

        yield b.startBuild(self.workerforbuilder)
        self.assertEqual(b.results, SUCCESS)
        expected_names = ["a", "b", "d", "e", "c"]
        executed_names = [s.name for s in b.executedSteps]  # type: ignore[attr-defined]
        self.assertEqual(executed_names, expected_names)

    @defer.inlineCallbacks
    def testAddStepsAfterLastStep(self) -> InlineCallbacksType[None]:
        b = self.build

        steps = self.create_fake_steps(["a", "b", "c"])

        def startStepB(remote: Connection) -> int:
            new_steps = self.create_fake_steps(["d", "e"])
            b.addStepsAfterLastStep([FakeStepFactory(s) for s in new_steps])
            return SUCCESS

        steps[1].startStep = startStepB  # type: ignore[method-assign, assignment]
        b.setStepFactories([FakeStepFactory(s) for s in steps])

        yield b.startBuild(self.workerforbuilder)
        self.assertEqual(b.results, SUCCESS)
        expected_names = ["a", "b", "c", "d", "e"]
        executed_names = [s.name for s in b.executedSteps]  # type: ignore[attr-defined]
        self.assertEqual(executed_names, expected_names)

    def testStepNamesUnique(self) -> None:
        # if the step names are unique they should remain unchanged
        b = self.build

        steps = self.create_fake_steps(["clone", "command", "clean"])
        b.setStepFactories([FakeStepFactory(s) for s in steps])

        b.startBuild(self.workerforbuilder)
        self.assertEqual(b.results, SUCCESS)
        expected_names = ["clone", "command", "clean"]
        executed_names = [s.name for s in b.executedSteps]  # type: ignore[attr-defined]
        self.assertEqual(executed_names, expected_names)

    def testStepNamesDuplicate(self) -> None:
        b = self.build

        steps = self.create_fake_steps(["stage", "stage", "stage"])
        b.setStepFactories([FakeStepFactory(s) for s in steps])

        b.startBuild(self.workerforbuilder)
        self.assertEqual(b.results, SUCCESS)
        expected_names = ["stage", "stage_1", "stage_2"]
        executed_names = [s.name for s in b.executedSteps]  # type: ignore[attr-defined]
        self.assertEqual(executed_names, expected_names)

    def testStepNamesDuplicateAfterAdd(self) -> None:
        b = self.build

        steps = self.create_fake_steps(["a", "b", "c"])

        def startStepB(remote: Connection) -> int:
            new_steps = self.create_fake_steps(["c", "c"])
            b.addStepsAfterCurrentStep([FakeStepFactory(s) for s in new_steps])
            return SUCCESS

        steps[1].startStep = startStepB  # type: ignore[method-assign, assignment]
        b.setStepFactories([FakeStepFactory(s) for s in steps])

        b.startBuild(self.workerforbuilder)
        self.assertEqual(b.results, SUCCESS)
        expected_names = ["a", "b", "c", "c_1", "c_2"]
        executed_names = [s.name for s in b.executedSteps]  # type: ignore[attr-defined]
        self.assertEqual(executed_names, expected_names)

    @defer.inlineCallbacks
    def testGetUrl(self) -> InlineCallbacksType[None]:
        self.build.number = 3
        url = yield self.build.getUrl()
        self.assertEqual(url, 'http://localhost:8080/#/builders/83/builds/3')

    @defer.inlineCallbacks
    def testGetUrlForVirtualBuilder(self) -> InlineCallbacksType[None]:
        # Let's fake a virtual builder
        yield self.master.db.insert_test_data([
            fakedb.Builder(id=108, name='wilma'),
        ])
        self.builder._builders['wilma'] = 108
        self.build.setProperty('virtual_builder_name', 'wilma', 'Build')
        self.build.setProperty('virtual_builder_tags', ['_virtual_'])
        self.build.number = 33
        url = yield self.build.getUrl()
        self.assertEqual(url, 'http://localhost:8080/#/builders/108/builds/33')

    def test_active_builds_metric(self) -> None:
        """
        The number of active builds is increased when a build starts
        and decreased when it finishes.
        """
        b = self.build

        controller, step_factory = makeControllableStepFactory()
        b.setStepFactories([step_factory])

        observer = MetricLogObserver()
        observer.enable()
        self.addCleanup(observer.disable)

        def get_active_builds() -> int:
            return observer.asDict()['counters'].get('active_builds', 0)

        self.assertEqual(get_active_builds(), 0)

        b.startBuild(self.workerforbuilder)

        self.assertEqual(get_active_builds(), 1)

        controller.finishStep(SUCCESS)

        self.assertEqual(get_active_builds(), 0)

    def test_active_builds_metric_failure(self) -> None:
        """
        The number of active builds is increased when a build starts
        and decreased when it finishes..
        """
        b = self.build

        b.setStepFactories([FailingStepFactory()])

        observer = MetricLogObserver()
        observer.enable()
        self.addCleanup(observer.disable)

        def get_active_builds() -> int:
            return observer.asDict()['counters'].get('active_builds', 0)

        self.assertEqual(get_active_builds(), 0)

        b.startBuild(self.workerforbuilder)

        self.flushLoggedErrors(TestException)

        self.assertEqual(get_active_builds(), 0)

    def test_build_env_mutation_not_propagated(self) -> None:
        builder = FakeBuilder(self.master)
        builder.config.env['PATH'] = ['/a/b/c', '/d/e/f']
        build = Build(self.build.requests, builder)  # type: ignore[arg-type]

        # build correctly inherited
        self.assertEqual(build.env['PATH'], ['/a/b/c', '/d/e/f'])
        # should NOT be the same object
        self.assertIsNot(build.env['PATH'], builder.config.env['PATH'])

        # mutate build.env
        build.env['PATH'].insert(0, '/x/y/z')

        self.assertEqual(build.env['PATH'], ['/x/y/z', '/a/b/c', '/d/e/f'])
        self.assertEqual(builder.config.env['PATH'], ['/a/b/c', '/d/e/f'])


class TestMultipleSourceStamps(TestReactorMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self)
        self.builder = FakeBuilder(self.master)

        r = FakeRequest()
        s1 = FakeSource()
        s1.repository = "repoA"
        s1.codebase = "A"
        s1.changes = [FakeChange(10), FakeChange(11)]
        s1.revision = "12345"  # type: ignore[assignment]
        s2 = FakeSource()
        s2.repository = "repoB"
        s2.codebase = "B"
        s2.changes = [FakeChange(12), FakeChange(13)]
        s2.revision = "67890"  # type: ignore[assignment]
        s3 = FakeSource()
        s3.repository = "repoC"
        # no codebase defined
        s3.changes = [FakeChange(14), FakeChange(15)]
        s3.revision = "111213"  # type: ignore[assignment]
        r.sources.extend([s1, s2, s3])

        self.build = Build([r], self.builder)  # type: ignore[arg-type, list-item]

    def test_buildReturnSourceStamp(self) -> None:
        """
        Test that a build returns the correct sourcestamp
        """
        source1 = self.build.getSourceStamp("A")
        source2 = self.build.getSourceStamp("B")

        self.assertEqual([source1.repository, source1.revision], ["repoA", "12345"])  # type: ignore[union-attr]
        self.assertEqual([source2.repository, source2.revision], ["repoB", "67890"])  # type: ignore[union-attr]

    def test_buildReturnSourceStamp_empty_codebase(self) -> None:
        """
        Test that a build returns the correct sourcestamp if codebase is empty
        """
        codebase = ''
        source3 = self.build.getSourceStamp(codebase)
        self.assertTrue(source3 is not None)
        self.assertEqual([source3.repository, source3.revision], ["repoC", "111213"])  # type: ignore[union-attr]


class TestBuildBlameList(TestReactorMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self)
        self.builder = FakeBuilder(self.master)

        self.sourceByMe = FakeSource()
        self.sourceByMe.repository = "repoA"
        self.sourceByMe.codebase = "A"
        self.sourceByMe.changes = [FakeChange(10), FakeChange(11)]
        self.sourceByMe.changes[0].who = "me"
        self.sourceByMe.changes[1].who = "me"

        self.sourceByHim = FakeSource()
        self.sourceByHim.repository = "repoB"
        self.sourceByHim.codebase = "B"
        self.sourceByHim.changes = [FakeChange(12), FakeChange(13)]
        self.sourceByHim.changes[0].who = "him"
        self.sourceByHim.changes[1].who = "him"

        self.patchSource = FakeSource()
        self.patchSource.repository = "repoB"
        self.patchSource.codebase = "B"
        self.patchSource.changes = []
        self.patchSource.revision = "67890"  # type: ignore[assignment]
        self.patchSource.patch_info = ("jeff", "jeff's new feature")  # type: ignore[assignment]

    def test_blamelist_for_changes(self) -> None:
        r = FakeRequest()
        r.sources.extend([self.sourceByMe, self.sourceByHim])
        build = Build([r], self.builder)  # type: ignore[arg-type, list-item]
        blamelist = build.blamelist()
        self.assertEqual(blamelist, ['him', 'me'])

    def test_blamelist_for_patch(self) -> None:
        r = FakeRequest()
        r.sources.extend([self.patchSource])
        build = Build([r], self.builder)  # type: ignore[arg-type, list-item]
        blamelist = build.blamelist()
        # If no patch is set, author will not be est
        self.assertEqual(blamelist, [])


class TestSetupProperties_MultipleSources(TestReactorMixin, unittest.TestCase):
    """
    Test that the property values, based on the available requests, are
    initialized properly
    """

    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.props = {}  # type: ignore[var-annotated]
        self.r = FakeRequest()
        self.r.sources = []
        self.r.sources.append(FakeSource())
        self.r.sources[0].changes = [FakeChange()]
        self.r.sources[0].repository = "http://svn-repo-A"
        self.r.sources[0].codebase = "A"
        self.r.sources[0].branch = "develop"
        self.r.sources[0].revision = "12345"
        self.r.sources.append(FakeSource())
        self.r.sources[1].changes = [FakeChange()]
        self.r.sources[1].repository = "http://svn-repo-B"
        self.r.sources[1].codebase = "B"
        self.r.sources[1].revision = "34567"
        self.builder = FakeBuilder((yield fakemaster.make_master(self, wantData=True)))
        self.build = Build([self.r], self.builder)  # type: ignore[arg-type, list-item]
        self.build.setStepFactories([])
        # record properties that will be set
        self.build.properties.setProperty = self.setProperty  # type: ignore[assignment, method-assign]

    def setProperty(self, n: str, v: Any, s: str, runtime: bool = False) -> None:
        if s not in self.props:
            self.props[s] = {}
        if not self.props[s]:
            self.props[s] = {}
        self.props[s][n] = v

    def test_sourcestamp_properties_not_set(self) -> None:
        Build.setupBuildProperties(self.build.getProperties(), [self.r], self.r.sources)  # type: ignore[list-item]
        self.assertNotIn("codebase", self.props["Build"])
        self.assertNotIn("revision", self.props["Build"])
        self.assertNotIn("branch", self.props["Build"])
        self.assertNotIn("project", self.props["Build"])
        self.assertNotIn("repository", self.props["Build"])


class TestSetupProperties_SingleSource(TestReactorMixin, unittest.TestCase):
    """
    Test that the property values, based on the available requests, are
    initialized properly
    """

    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.props = {}  # type: ignore[var-annotated]
        self.r = FakeRequest()
        self.r.sources = []
        self.r.sources.append(FakeSource())
        self.r.sources[0].changes = [FakeChange()]
        self.r.sources[0].repository = "http://svn-repo-A"
        self.r.sources[0].codebase = "A"
        self.r.sources[0].branch = "develop"
        self.r.sources[0].revision = "12345"
        self.builder = FakeBuilder((yield fakemaster.make_master(self, wantData=True)))
        self.build = Build([self.r], self.builder)  # type: ignore[arg-type, list-item]
        self.build.setStepFactories([])
        # record properties that will be set
        self.build.properties.setProperty = self.setProperty  # type: ignore[assignment, method-assign]

    def setProperty(self, n: str, v: Any, s: str, runtime: bool = False) -> None:
        if s not in self.props:
            self.props[s] = {}
        if not self.props[s]:
            self.props[s] = {}
        self.props[s][n] = v

    def test_properties_codebase(self) -> None:
        Build.setupBuildProperties(self.build.getProperties(), [self.r], self.r.sources)  # type: ignore[list-item]
        codebase = self.props["Build"]["codebase"]
        self.assertEqual(codebase, "A")

    def test_properties_repository(self) -> None:
        Build.setupBuildProperties(self.build.getProperties(), [self.r], self.r.sources)  # type: ignore[list-item]
        repository = self.props["Build"]["repository"]
        self.assertEqual(repository, "http://svn-repo-A")

    def test_properties_revision(self) -> None:
        Build.setupBuildProperties(self.build.getProperties(), [self.r], self.r.sources)  # type: ignore[list-item]
        revision = self.props["Build"]["revision"]
        self.assertEqual(revision, "12345")

    def test_properties_branch(self) -> None:
        Build.setupBuildProperties(self.build.getProperties(), [self.r], self.r.sources)  # type: ignore[list-item]
        branch = self.props["Build"]["branch"]
        self.assertEqual(branch, "develop")

    def test_property_project(self) -> None:
        Build.setupBuildProperties(self.build.getProperties(), [self.r], self.r.sources)  # type: ignore[list-item]
        project = self.props["Build"]["project"]
        self.assertEqual(project, '')


class TestBuildFiles(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = FakeBuilder(master=Mock())

        sstamp_id_next = count(start=1)
        change_id_next = count(start=1)

        def _tmp_sstamp(repository: str = "", codebase: str = "") -> TempSourceStamp:
            return TempSourceStamp({
                "ssid": next(sstamp_id_next),
                "branch": None,
                "revision": None,
                "project": "",
                "repository": repository,
                "codebase": codebase,
                "created_at": datetime.now(),
                "patch": None,
            })

        def _add_tmp_change(sstamp: TempSourceStamp, author: str, files: list[str]) -> TempChange:
            return TempChange({
                "changeid": next(change_id_next),
                "author": author,
                "committer": None,
                "comments": "",
                "branch": sstamp.branch,
                "revision": sstamp.revision,
                "revlink": None,
                "when_timestamp": 0,
                "category": None,
                "parent_changeids": [],
                "repository": sstamp.repository,
                "codebase": sstamp.codebase,
                "project": sstamp.project,
                "files": files,
                "sourcestamp": sstamp.asSSDict(),
                "properties": {},
            })

        self.source_by_me = _tmp_sstamp(repository="repoA", codebase="A")
        self.source_by_me.changes = [
            _add_tmp_change(self.source_by_me, author="me", files=["a/1"]),
            _add_tmp_change(self.source_by_me, author="me", files=["a/2"]),
        ]

        self.source_by_him = _tmp_sstamp(repository="repoB", codebase="B")
        self.source_by_him.changes = [
            _add_tmp_change(self.source_by_me, author="him", files=["b/1"]),
            _add_tmp_change(self.source_by_me, author="him", files=["b/2"]),
        ]

        self.source_by_other = _tmp_sstamp(repository="repoB", codebase="B")
        self.source_by_other.changes = [
            _add_tmp_change(self.source_by_me, author="other", files=["b/3"]),
            _add_tmp_change(self.source_by_me, author="other", files=["b/2"]),
        ]

    def test_files_merged_buildrequests(self) -> None:
        def _buildrequest(sources: dict[str, TempSourceStamp]) -> BuildRequest:
            return BuildRequest(
                id=1,
                bsid=1,
                buildername=self.builder.name,
                builderid=self.builder.builderid,
                priority=0,
                submitted_at=0,
                master=self.builder.master,
                waited_for=True,
                reason=None,
                properties=Properties(),
                sources=sources,
            )

        first_request = _buildrequest({
            self.source_by_me.codebase: self.source_by_me,
            self.source_by_him.codebase: self.source_by_him,
        })
        second_request = _buildrequest({self.source_by_other.codebase: self.source_by_other})

        build = Build([first_request, second_request], cast("Builder", self.builder))
        files = build.allFiles()
        files.sort()
        self.assertEqual(files, ["a/1", "a/2", "b/1", "b/2", "b/3"])
