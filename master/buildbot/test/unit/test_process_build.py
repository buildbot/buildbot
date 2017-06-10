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

from __future__ import absolute_import
from __future__ import print_function

import operator

from mock import Mock
from mock import call

from twisted.internet import defer
from twisted.trial import unittest
from zope.interface import implementer

from buildbot import interfaces
from buildbot.locks import WorkerLock
from buildbot.process.build import Build
from buildbot.process.buildstep import BuildStep
from buildbot.process.buildstep import LoggingBuildStep
from buildbot.process.metrics import MetricLogObserver
from buildbot.process.properties import Properties
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.test.fake import fakemaster
from buildbot.test.fake import fakeprotocol
from buildbot.test.fake import worker
from buildbot.test.fake.fakebuild import FakeBuildStatus
from buildbot.test.util.warnings import assertNotProducesWarnings
from buildbot.test.util.warnings import assertProducesWarning
from buildbot.worker_transition import DeprecatedWorkerAPIWarning
from buildbot.worker_transition import DeprecatedWorkerNameWarning


class FakeChange:

    def __init__(self, number=None):
        self.properties = Properties()
        self.number = number
        self.who = "me"


class FakeSource:

    def __init__(self):
        self.sourcestampsetid = None
        self.changes = []
        self.branch = None
        self.revision = None
        self.repository = ''
        self.codebase = ''
        self.project = ''
        self.patch_info = None
        self.patch = None

    def getRepository(self):
        return self.repository


class FakeRequest:

    def __init__(self):
        self.sources = []
        self.reason = "Because"
        self.properties = Properties()
        self.id = 9385

    def mergeSourceStampsWith(self, others):
        return self.sources

    def mergeReasons(self, others):
        return self.reason


class FakeBuildStep(BuildStep):

    def __init__(self):
        BuildStep.__init__(
            self, haltOnFailure=False, flunkOnWarnings=False, flunkOnFailure=True,
            warnOnWarnings=True, warnOnFailure=False, alwaysRun=False, name='fake')
        self._summary = {u'step': u'result', u'build': u'build result'}
        self._expected_results = SUCCESS

    def run(self):
        return self._expected_results

    def getResultSummary(self):
        return self._summary

    def interrupt(self, reason):
        self.running = False
        self.interrupted = reason


class FakeBuilder:

    def __init__(self, master):
        self.config = Mock()
        self.config.workerbuilddir = 'wbd'
        self.name = 'fred'
        self.master = master
        self.botmaster = master.botmaster

    def getBuilderId(self):
        return defer.succeed(83)

    def setupProperties(self, props):
        pass

    def buildFinished(self, build, workerforbuilder):
        pass

    def getBuilderIdForName(self, name):
        return defer.succeed(83)


@implementer(interfaces.IBuildStepFactory)
class FakeStepFactory(object):

    """Fake step factory that just returns a fixed step object."""

    def __init__(self, step):
        self.step = step

    def buildStep(self):
        return self.step


class TestException(Exception):
    pass


@implementer(interfaces.IBuildStepFactory)
class FailingStepFactory(object):

    """Fake step factory that just returns a fixed step object."""

    def buildStep(self):
        raise TestException("FailingStepFactory")


class _StepController():

    def __init__(self, step):
        self._step = step

    def finishStep(self, result):
        self._step._deferred.callback(result)


class _ControllableStep(BuildStep):

    def __init__(self):
        BuildStep.__init__(self)
        self._deferred = defer.Deferred()

    def run(self):
        return self._deferred


def makeControllableStepFactory():
    step = _ControllableStep()
    controller = _StepController(step)
    return controller, FakeStepFactory(step)


class TestBuild(unittest.TestCase):

    def setUp(self):
        r = FakeRequest()
        r.sources = [FakeSource()]
        r.sources[0].changes = [FakeChange()]
        r.sources[0].revision = "12345"

        self.request = r
        self.master = fakemaster.make_master(wantData=True, testcase=self)

        self.worker = worker.FakeWorker(self.master)
        self.worker.attached(None)
        self.builder = FakeBuilder(self.master)
        self.build = Build([r])
        self.build.conn = fakeprotocol.FakeConnection(self.master, self.worker)

        self.workerforbuilder = Mock(name='workerforbuilder')
        self.workerforbuilder.worker = self.worker
        self.workerforbuilder.prepare = lambda _: True
        self.workerforbuilder.ping = lambda: True

        self.build.setBuilder(self.builder)
        self.build.text = []
        self.build.buildid = 666

    def testRunSuccessfulBuild(self):
        b = self.build

        step = FakeBuildStep()
        b.setStepFactories([FakeStepFactory(step)])

        b.startBuild(FakeBuildStatus(), self.workerforbuilder)

        self.assertEqual(b.results, SUCCESS)

    def testStopBuild(self):
        b = self.build

        step = FakeBuildStep()
        b.setStepFactories([FakeStepFactory(step)])

        def startStep(*args, **kw):
            # Now interrupt the build
            b.stopBuild("stop it")
            return defer.Deferred()
        step.startStep = startStep

        b.startBuild(FakeBuildStatus(), self.workerforbuilder)

        self.assertEqual(b.results, CANCELLED)

        self.assertIn('stop it', step.interrupted)

    def testAlwaysRunStepStopBuild(self):
        """Test that steps marked with alwaysRun=True still get run even if
        the build is stopped."""

        # Create a build with 2 steps, the first one will get interrupted, and
        # the second one is marked with alwaysRun=True
        b = self.build

        step1 = FakeBuildStep()
        step1.alwaysRun = False
        step1.results = None
        step2 = FakeBuildStep()
        step2.alwaysRun = True
        step2.results = None
        b.setStepFactories([
            FakeStepFactory(step1),
            FakeStepFactory(step2),
        ])

        def startStep1(*args, **kw):
            # Now interrupt the build
            b.stopBuild("stop it")
            return defer.succeed(SUCCESS)
        step1.startStep = startStep1
        step1.stepDone = lambda: False

        step2Started = [False]

        def startStep2(*args, **kw):
            step2Started[0] = True
            return defer.succeed(SUCCESS)
        step2.startStep = startStep2
        step1.stepDone = lambda: False

        d = b.startBuild(FakeBuildStatus(), self.workerforbuilder)

        def check(ign):
            self.assertEqual(b.results, CANCELLED)
            self.assertIn('stop it', step1.interrupted)
            self.assertTrue(step2Started[0])
        d.addCallback(check)
        return d

    def testBuildcanStartWithWorkerForBuilder(self):
        b = self.build

        workerforbuilder1 = Mock()
        workerforbuilder2 = Mock()

        lock = WorkerLock('lock')
        counting_access = lock.access('counting')
        real_lock = b.builder.botmaster.getLockByID(lock)

        # no locks, so both these pass (call twice to verify there's no
        # state/memory)
        lock_list = [(real_lock, counting_access)]
        self.assertTrue(
            Build.canStartWithWorkerForBuilder(lock_list, workerforbuilder1))
        self.assertTrue(
            Build.canStartWithWorkerForBuilder(lock_list, workerforbuilder1))
        self.assertTrue(
            Build.canStartWithWorkerForBuilder(lock_list, workerforbuilder2))
        self.assertTrue(
            Build.canStartWithWorkerForBuilder(lock_list, workerforbuilder2))

        worker_lock_1 = real_lock.getLock(workerforbuilder1.worker)
        worker_lock_2 = real_lock.getLock(workerforbuilder2.worker)

        # then have workerforbuilder2 claim its lock:
        worker_lock_2.claim(workerforbuilder2, counting_access)
        self.assertTrue(
            Build.canStartWithWorkerForBuilder(lock_list, workerforbuilder1))
        self.assertTrue(
            Build.canStartWithWorkerForBuilder(lock_list, workerforbuilder1))
        self.assertFalse(
            Build.canStartWithWorkerForBuilder(lock_list, workerforbuilder2))
        self.assertFalse(
            Build.canStartWithWorkerForBuilder(lock_list, workerforbuilder2))
        worker_lock_2.release(workerforbuilder2, counting_access)

        # then have workerforbuilder1 claim its lock:
        worker_lock_1.claim(workerforbuilder1, counting_access)
        self.assertFalse(
            Build.canStartWithWorkerForBuilder(lock_list, workerforbuilder1))
        self.assertFalse(
            Build.canStartWithWorkerForBuilder(lock_list, workerforbuilder1))
        self.assertTrue(
            Build.canStartWithWorkerForBuilder(lock_list, workerforbuilder2))
        self.assertTrue(
            Build.canStartWithWorkerForBuilder(lock_list, workerforbuilder2))
        worker_lock_1.release(workerforbuilder1, counting_access)

    def testBuilddirPropType(self):
        import posixpath

        b = self.build

        b.build_status = Mock()
        b.builder.config.workerbuilddir = 'test'
        self.workerforbuilder.worker.worker_basedir = "/srv/buildbot/worker"
        self.workerforbuilder.worker.path_module = posixpath
        b.getProperties = Mock()
        b.setProperty = Mock()

        b.setupWorkerForBuilder(self.workerforbuilder)

        expected_path = '/srv/buildbot/worker/test'

        b.setProperty.assert_has_calls(
            [call('builddir', expected_path, 'worker')],
            any_order=True)

    def testBuildLocksAcquired(self):
        b = self.build

        lock = WorkerLock('lock')
        claimCount = [0]
        lock_access = lock.access('counting')
        lock.access = lambda mode: lock_access
        real_lock = b.builder.botmaster.getLockByID(lock) \
            .getLock(self.workerforbuilder.worker)

        def claim(owner, access):
            claimCount[0] += 1
            return real_lock.old_claim(owner, access)
        real_lock.old_claim = real_lock.claim
        real_lock.claim = claim
        b.setLocks([lock_access])

        step = FakeBuildStep()
        b.setStepFactories([FakeStepFactory(step)])

        b.startBuild(FakeBuildStatus(), self.workerforbuilder)

        self.assertEqual(b.results, SUCCESS)
        self.assertEqual(claimCount[0], 1)

    def testBuildLocksOrder(self):
        """Test that locks are acquired in FIFO order; specifically that
        counting locks cannot jump ahead of exclusive locks"""
        eBuild = self.build

        cBuilder = FakeBuilder(self.master)
        cBuild = Build([self.request])
        cBuild.setBuilder(cBuilder)

        eWorker = Mock()
        cWorker = Mock()

        eWorker.worker = self.worker
        cWorker.worker = self.worker
        eWorker.prepare = cWorker.prepare = lambda _: True
        eWorker.ping = cWorker.ping = lambda: True

        lock = WorkerLock('lock', 2)
        claimLog = []
        realLock = self.master.botmaster.getLockByID(lock).getLock(self.worker)

        def claim(owner, access):
            claimLog.append(owner)
            return realLock.oldClaim(owner, access)
        realLock.oldClaim = realLock.claim
        realLock.claim = claim

        eBuild.setLocks([lock.access('exclusive')])
        cBuild.setLocks([lock.access('counting')])

        fakeBuild = Mock()
        fakeBuildAccess = lock.access('counting')
        realLock.claim(fakeBuild, fakeBuildAccess)

        step = FakeBuildStep()
        eBuild.setStepFactories([FakeStepFactory(step)])
        cBuild.setStepFactories([FakeStepFactory(step)])

        e = eBuild.startBuild(FakeBuildStatus(), eWorker)
        c = cBuild.startBuild(FakeBuildStatus(), cWorker)
        d = defer.DeferredList([e, c])

        realLock.release(fakeBuild, fakeBuildAccess)

        def check(ign):
            self.assertEqual(eBuild.results, SUCCESS)
            self.assertEqual(cBuild.results, SUCCESS)
            self.assertEqual(claimLog, [fakeBuild, eBuild, cBuild])

        d.addCallback(check)
        return d

    def testBuildWaitingForLocks(self):
        b = self.build

        lock = WorkerLock('lock')
        claimCount = [0]
        lock_access = lock.access('counting')
        lock.access = lambda mode: lock_access
        real_lock = b.builder.botmaster.getLockByID(lock) \
            .getLock(self.workerforbuilder.worker)

        def claim(owner, access):
            claimCount[0] += 1
            return real_lock.old_claim(owner, access)
        real_lock.old_claim = real_lock.claim
        real_lock.claim = claim
        b.setLocks([lock_access])

        step = FakeBuildStep()
        b.setStepFactories([FakeStepFactory(step)])

        real_lock.claim(Mock(), lock.access('counting'))

        b.startBuild(FakeBuildStatus(), self.workerforbuilder)

        self.assertEqual(claimCount[0], 1)
        self.assertTrue(b.currentStep is None)
        self.assertTrue(b._acquiringLock is not None)

    def testStopBuildWaitingForLocks(self):
        b = self.build

        lock = WorkerLock('lock')
        lock_access = lock.access('counting')
        lock.access = lambda mode: lock_access
        real_lock = b.builder.botmaster.getLockByID(lock) \
            .getLock(self.workerforbuilder.worker)
        b.setLocks([lock_access])

        step = FakeBuildStep()
        step.alwaysRun = False
        b.setStepFactories([FakeStepFactory(step)])

        real_lock.claim(Mock(), lock.access('counting'))

        def acquireLocks(res=None):
            retval = Build.acquireLocks(b, res)
            b.stopBuild('stop it')
            return retval
        b.acquireLocks = acquireLocks

        b.startBuild(FakeBuildStatus(), self.workerforbuilder)

        self.assertTrue(b.currentStep is None)
        self.assertEqual(b.results, CANCELLED)

    def testStopBuildWaitingForLocks_lostRemote(self):
        b = self.build

        lock = WorkerLock('lock')
        lock_access = lock.access('counting')
        lock.access = lambda mode: lock_access
        real_lock = b.builder.botmaster.getLockByID(lock) \
            .getLock(self.workerforbuilder.worker)
        b.setLocks([lock_access])

        step = FakeBuildStep()
        step.alwaysRun = False
        b.setStepFactories([FakeStepFactory(step)])

        real_lock.claim(Mock(), lock.access('counting'))

        def acquireLocks(res=None):
            retval = Build.acquireLocks(b, res)
            b.lostRemote()
            return retval
        b.acquireLocks = acquireLocks

        b.startBuild(FakeBuildStatus(), self.workerforbuilder)

        self.assertTrue(b.currentStep is None)
        self.assertEqual(b.results, RETRY)
        self.build.build_status.setText.assert_called_with(
            ["retry", "lost", "connection"])
        self.build.build_status.setResults.assert_called_with(RETRY)

    def testStopBuildWaitingForStepLocks(self):
        b = self.build

        lock = WorkerLock('lock')
        lock_access = lock.access('counting')
        lock.access = lambda mode: lock_access
        real_lock = b.builder.botmaster.getLockByID(lock) \
            .getLock(self.workerforbuilder.worker)

        step = LoggingBuildStep(locks=[lock_access])
        b.setStepFactories([FakeStepFactory(step)])

        real_lock.claim(Mock(), lock.access('counting'))

        gotLocks = [False]

        def acquireLocks(res=None):
            gotLocks[0] = True
            retval = LoggingBuildStep.acquireLocks(step, res)
            self.assertTrue(b.currentStep is step)
            b.stopBuild('stop it')
            return retval
        step.acquireLocks = acquireLocks

        b.startBuild(FakeBuildStatus(), self.workerforbuilder)

        self.assertEqual(gotLocks, [True])
        self.assertEqual(b.results, CANCELLED)

    def testStepDone(self):
        b = self.build
        b.results = SUCCESS
        step = FakeBuildStep()
        terminate = b.stepDone(SUCCESS, step)
        self.assertFalse(terminate.result)
        self.assertEqual(b.results, SUCCESS)

    def testStepDoneHaltOnFailure(self):
        b = self.build
        b.results = SUCCESS
        step = FakeBuildStep()
        step.haltOnFailure = True
        terminate = b.stepDone(FAILURE, step)
        self.assertTrue(terminate.result)
        self.assertEqual(b.results, FAILURE)

    def testStepDoneHaltOnFailureNoFlunkOnFailure(self):
        b = self.build
        b.results = SUCCESS
        step = FakeBuildStep()
        step.flunkOnFailure = False
        step.haltOnFailure = True
        terminate = b.stepDone(FAILURE, step)
        self.assertTrue(terminate.result)
        self.assertEqual(b.results, SUCCESS)

    def testStepDoneFlunkOnWarningsFlunkOnFailure(self):
        b = self.build
        b.results = SUCCESS
        step = FakeBuildStep()
        step.flunkOnFailure = True
        step.flunkOnWarnings = True
        b.stepDone(WARNINGS, step)
        terminate = b.stepDone(FAILURE, step)
        self.assertFalse(terminate.result)
        self.assertEqual(b.results, FAILURE)

    def testStepDoneNoWarnOnWarnings(self):
        b = self.build
        b.results = SUCCESS
        step = FakeBuildStep()
        step.warnOnWarnings = False
        terminate = b.stepDone(WARNINGS, step)
        self.assertFalse(terminate.result)
        self.assertEqual(b.results, SUCCESS)

    def testStepDoneWarnings(self):
        b = self.build
        b.results = SUCCESS
        step = FakeBuildStep()
        terminate = b.stepDone(WARNINGS, step)
        self.assertFalse(terminate.result)
        self.assertEqual(b.results, WARNINGS)

    def testStepDoneFail(self):
        b = self.build
        b.results = SUCCESS
        step = FakeBuildStep()
        terminate = b.stepDone(FAILURE, step)
        self.assertFalse(terminate.result)
        self.assertEqual(b.results, FAILURE)

    def testStepDoneFailOverridesWarnings(self):
        b = self.build
        b.results = WARNINGS
        step = FakeBuildStep()
        terminate = b.stepDone(FAILURE, step)
        self.assertFalse(terminate.result)
        self.assertEqual(b.results, FAILURE)

    def testStepDoneWarnOnFailure(self):
        b = self.build
        b.results = SUCCESS
        step = FakeBuildStep()
        step.warnOnFailure = True
        step.flunkOnFailure = False
        terminate = b.stepDone(FAILURE, step)
        self.assertFalse(terminate.result)
        self.assertEqual(b.results, WARNINGS)

    def testStepDoneFlunkOnWarnings(self):
        b = self.build
        b.results = SUCCESS
        step = FakeBuildStep()
        step.flunkOnWarnings = True
        terminate = b.stepDone(WARNINGS, step)
        self.assertFalse(terminate.result)
        self.assertEqual(b.results, FAILURE)

    def testStepDoneHaltOnFailureFlunkOnWarnings(self):
        b = self.build
        b.results = SUCCESS
        step = FakeBuildStep()
        step.flunkOnWarnings = True
        self.haltOnFailure = True
        terminate = b.stepDone(WARNINGS, step)
        self.assertFalse(terminate.result)
        self.assertEqual(b.results, FAILURE)

    def testStepDoneWarningsDontOverrideFailure(self):
        b = self.build
        b.results = FAILURE
        step = FakeBuildStep()
        terminate = b.stepDone(WARNINGS, step)
        self.assertFalse(terminate.result)
        self.assertEqual(b.results, FAILURE)

    def testStepDoneRetryOverridesAnythingElse(self):
        b = self.build
        b.results = RETRY
        step = FakeBuildStep()
        step.alwaysRun = True
        b.stepDone(WARNINGS, step)
        b.stepDone(FAILURE, step)
        b.stepDone(SUCCESS, step)
        terminate = b.stepDone(EXCEPTION, step)
        self.assertTrue(terminate.result)
        self.assertEqual(b.results, RETRY)

    def test_getSummaryStatistic(self):
        b = self.build

        b.executedSteps = [
            BuildStep(),
            BuildStep(),
            BuildStep()
        ]
        b.executedSteps[0].setStatistic('casualties', 7)
        b.executedSteps[2].setStatistic('casualties', 4)

        add = operator.add
        self.assertEqual(b.getSummaryStatistic('casualties', add), 11)
        self.assertEqual(b.getSummaryStatistic('casualties', add, 10), 21)

    @defer.inlineCallbacks
    def testflushProperties(self):
        b = self.build

        b.build_status = FakeBuildStatus()
        b.setProperty("foo", "bar", "test")
        b.buildid = 43
        result = 'SUCCESS'
        res = yield b._flushProperties(result)
        self.assertEqual(res, result)
        self.assertEqual(self.master.data.updates.properties,
                         [(43, u'foo', 'bar', u'test')])

    def create_fake_steps(self, names):
        steps = []

        def create_fake_step(name):
            step = FakeBuildStep()
            step.name = name
            return step

        for name in names:
            step = create_fake_step(name)
            steps.append(step)
        return steps

    def testAddStepsAfterCurrentStep(self):
        b = self.build

        steps = self.create_fake_steps(["a", "b", "c"])

        def startStepB(*args, **kw):
            new_steps = self.create_fake_steps(["d", "e"])
            b.addStepsAfterCurrentStep([FakeStepFactory(s) for s in new_steps])
            return SUCCESS

        steps[1].startStep = startStepB
        b.setStepFactories([FakeStepFactory(s) for s in steps])

        b.startBuild(FakeBuildStatus(), self.workerforbuilder)
        self.assertEqual(b.results, SUCCESS)
        expected_names = ["a", "b", "d", "e", "c"]
        executed_names = [s.name for s in b.executedSteps]
        self.assertEqual(executed_names, expected_names)

    def testAddStepsAfterLastStep(self):
        b = self.build

        steps = self.create_fake_steps(["a", "b", "c"])

        def startStepB(*args, **kw):
            new_steps = self.create_fake_steps(["d", "e"])
            b.addStepsAfterLastStep([FakeStepFactory(s) for s in new_steps])
            return SUCCESS

        steps[1].startStep = startStepB
        b.setStepFactories([FakeStepFactory(s) for s in steps])

        b.startBuild(FakeBuildStatus(), self.workerforbuilder)
        self.assertEqual(b.results, SUCCESS)
        expected_names = ["a", "b", "c", "d", "e"]
        executed_names = [s.name for s in b.executedSteps]
        self.assertEqual(executed_names, expected_names)

    def testStepNamesUnique(self):
        # if the step names are unique they should remain unchanged
        b = self.build

        steps = self.create_fake_steps(["clone", "command", "clean"])
        b.setStepFactories([FakeStepFactory(s) for s in steps])

        b.startBuild(FakeBuildStatus(), self.workerforbuilder)
        self.assertEqual(b.results, SUCCESS)
        expected_names = ["clone", "command", "clean"]
        executed_names = [s.name for s in b.executedSteps]
        self.assertEqual(executed_names, expected_names)

    def testStepNamesDuplicate(self):
        b = self.build

        steps = self.create_fake_steps(["stage", "stage", "stage"])
        b.setStepFactories([FakeStepFactory(s) for s in steps])

        b.startBuild(FakeBuildStatus(), self.workerforbuilder)
        self.assertEqual(b.results, SUCCESS)
        expected_names = ["stage", "stage_1", "stage_2"]
        executed_names = [s.name for s in b.executedSteps]
        self.assertEqual(executed_names, expected_names)

    def testStepNamesDuplicateAfterAdd(self):
        b = self.build

        steps = self.create_fake_steps(["a", "b", "c"])

        def startStepB(*args, **kw):
            new_steps = self.create_fake_steps(["c", "c"])
            b.addStepsAfterCurrentStep([FakeStepFactory(s) for s in new_steps])
            return SUCCESS

        steps[1].startStep = startStepB
        b.setStepFactories([FakeStepFactory(s) for s in steps])

        b.startBuild(FakeBuildStatus(), self.workerforbuilder)
        self.assertEqual(b.results, SUCCESS)
        expected_names = ["a", "b", "c_1", "c_2", "c"]
        executed_names = [s.name for s in b.executedSteps]
        self.assertEqual(executed_names, expected_names)

    @defer.inlineCallbacks
    def testGetUrl(self):
        self.build.number = 3
        url = yield self.build.getUrl()
        self.assertEqual(url, 'http://localhost:8080/#builders/83/builds/3')

    def test_active_builds_metric(self):
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

        def get_active_builds():
            return observer.asDict()['counters'].get('active_builds', 0)
        self.assertEqual(get_active_builds(), 0)

        b.startBuild(FakeBuildStatus(), self.workerforbuilder)

        self.assertEqual(get_active_builds(), 1)

        controller.finishStep(SUCCESS)

        self.assertEqual(get_active_builds(), 0)

    def test_active_builds_metric_failure(self):
        """
        The number of active builds is increased when a build starts
        and decreased when it finishes..
        """
        b = self.build

        b.setStepFactories([FailingStepFactory()])

        observer = MetricLogObserver()
        observer.enable()
        self.addCleanup(observer.disable)

        def get_active_builds():
            return observer.asDict()['counters'].get('active_builds', 0)
        self.assertEqual(get_active_builds(), 0)

        b.startBuild(FakeBuildStatus(), self.workerforbuilder)

        self.flushLoggedErrors(TestException)

        self.assertEqual(get_active_builds(), 0)


class TestMultipleSourceStamps(unittest.TestCase):

    def setUp(self):
        r = FakeRequest()
        s1 = FakeSource()
        s1.repository = "repoA"
        s1.codebase = "A"
        s1.changes = [FakeChange(10), FakeChange(11)]
        s1.revision = "12345"
        s2 = FakeSource()
        s2.repository = "repoB"
        s2.codebase = "B"
        s2.changes = [FakeChange(12), FakeChange(13)]
        s2.revision = "67890"
        s3 = FakeSource()
        s3.repository = "repoC"
        # no codebase defined
        s3.changes = [FakeChange(14), FakeChange(15)]
        s3.revision = "111213"
        r.sources.extend([s1, s2, s3])

        self.build = Build([r])

    def test_buildReturnSourceStamp(self):
        """
        Test that a build returns the correct sourcestamp
        """
        source1 = self.build.getSourceStamp("A")
        source2 = self.build.getSourceStamp("B")

        self.assertEqual(
            [source1.repository, source1.revision], ["repoA", "12345"])
        self.assertEqual(
            [source2.repository, source2.revision], ["repoB", "67890"])

    def test_buildReturnSourceStamp_empty_codebase(self):
        """
        Test that a build returns the correct sourcestamp if codebase is empty
        """
        codebase = ''
        source3 = self.build.getSourceStamp(codebase)
        self.assertTrue(source3 is not None)
        self.assertEqual(
            [source3.repository, source3.revision], ["repoC", "111213"])


class TestBuildBlameList(unittest.TestCase):

    def setUp(self):
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
        self.patchSource.revision = "67890"
        self.patchSource.patch_info = ("jeff", "jeff's new feature")

    def test_blamelist_for_changes(self):
        r = FakeRequest()
        r.sources.extend([self.sourceByMe, self.sourceByHim])
        build = Build([r])
        blamelist = build.blamelist()
        self.assertEqual(blamelist, ['him', 'me'])

    def test_blamelist_for_patch(self):
        r = FakeRequest()
        r.sources.extend([self.patchSource])
        build = Build([r])
        blamelist = build.blamelist()
        # If no patch is set, author will not be est
        self.assertEqual(blamelist, [])


class TestSetupProperties_MultipleSources(unittest.TestCase):

    """
    Test that the property values, based on the available requests, are
    initialized properly
    """

    def setUp(self):
        self.props = {}
        r = FakeRequest()
        r.sources = []
        r.sources.append(FakeSource())
        r.sources[0].changes = [FakeChange()]
        r.sources[0].repository = "http://svn-repo-A"
        r.sources[0].codebase = "A"
        r.sources[0].branch = "develop"
        r.sources[0].revision = "12345"
        r.sources.append(FakeSource())
        r.sources[1].changes = [FakeChange()]
        r.sources[1].repository = "http://svn-repo-B"
        r.sources[1].codebase = "B"
        r.sources[1].revision = "34567"
        self.build = Build([r])
        self.build.setStepFactories([])
        self.builder = FakeBuilder(
            fakemaster.make_master(wantData=True, testcase=self))
        self.build.setBuilder(self.builder)
        self.build.build_status = FakeBuildStatus()
        # record properties that will be set
        self.build.properties.setProperty = self.setProperty

    def setProperty(self, n, v, s, runtime=False):
        if s not in self.props:
            self.props[s] = {}
        if not self.props[s]:
            self.props[s] = {}
        self.props[s][n] = v

    def test_sourcestamp_properties_not_set(self):
        self.build.setupOwnProperties()
        self.assertNotIn("codebase", self.props["Build"])
        self.assertNotIn("revision", self.props["Build"])
        self.assertNotIn("branch", self.props["Build"])
        self.assertNotIn("project", self.props["Build"])
        self.assertNotIn("repository", self.props["Build"])


class TestSetupProperties_SingleSource(unittest.TestCase):

    """
    Test that the property values, based on the available requests, are
    initialized properly
    """

    def setUp(self):
        self.props = {}
        r = FakeRequest()
        r.sources = []
        r.sources.append(FakeSource())
        r.sources[0].changes = [FakeChange()]
        r.sources[0].repository = "http://svn-repo-A"
        r.sources[0].codebase = "A"
        r.sources[0].branch = "develop"
        r.sources[0].revision = "12345"
        self.build = Build([r])
        self.build.setStepFactories([])
        self.builder = FakeBuilder(
            fakemaster.make_master(wantData=True, testcase=self))
        self.build.setBuilder(self.builder)
        self.build.build_status = FakeBuildStatus()
        # record properties that will be set
        self.build.properties.setProperty = self.setProperty

    def setProperty(self, n, v, s, runtime=False):
        if s not in self.props:
            self.props[s] = {}
        if not self.props[s]:
            self.props[s] = {}
        self.props[s][n] = v

    def test_properties_codebase(self):
        self.build.setupOwnProperties()
        codebase = self.props["Build"]["codebase"]
        self.assertEqual(codebase, "A")

    def test_properties_repository(self):
        self.build.setupOwnProperties()
        repository = self.props["Build"]["repository"]
        self.assertEqual(repository, "http://svn-repo-A")

    def test_properties_revision(self):
        self.build.setupOwnProperties()
        revision = self.props["Build"]["revision"]
        self.assertEqual(revision, "12345")

    def test_properties_branch(self):
        self.build.setupOwnProperties()
        branch = self.props["Build"]["branch"]
        self.assertEqual(branch, "develop")

    def test_property_project(self):
        self.build.setupOwnProperties()
        project = self.props["Build"]["project"]
        self.assertEqual(project, '')


class TestBuildProperties(unittest.TestCase):

    """
    Test that a Build has the necessary L{IProperties} methods, and that they
    properly delegate to the C{build_status} attribute - so really just a test
    of the L{IProperties} adapter.
    """

    def setUp(self):
        @implementer(interfaces.IProperties)
        class FakeProperties(Mock):
            pass
        FakeProperties.render = Mock(side_effect=lambda x: x)

        class FakeBuildStatus(Mock):
            pass
        r = FakeRequest()
        r.sources = [FakeSource()]
        r.sources[0].changes = [FakeChange()]
        r.sources[0].revision = "12345"
        self.master = fakemaster.make_master(wantData=True, testcase=self)
        self.worker = worker.FakeWorker(self.master)
        self.worker.attached(None)
        self.workerforbuilder = Mock(name='workerforbuilder')
        self.workerforbuilder.worker = self.worker
        self.build = Build([r])
        self.build.setStepFactories([])
        self.builder = FakeBuilder(
            fakemaster.make_master(wantData=True, testcase=self))
        self.build.setBuilder(self.builder)
        self.properties = self.build.properties = FakeProperties()
        self.build_status = FakeBuildStatus()
        self.build._flushProperties = Mock()
        self.build.startBuild(self.build_status, self.workerforbuilder)

    def test_getProperty(self):
        self.build.getProperty('x')
        self.properties.getProperty.assert_called_with('x', None)

    def test_getProperty_default(self):
        self.build.getProperty('x', 'nox')
        self.properties.getProperty.assert_called_with('x', 'nox')

    def test_setProperty(self):
        self.build.setProperty('n', 'v', 's')
        self.properties.setProperty.assert_called_with('n', 'v', 's',
                                                       runtime=True)

    def test_hasProperty(self):
        self.properties.hasProperty.return_value = True
        self.assertTrue(self.build.hasProperty('p'))
        self.properties.hasProperty.assert_called_with('p')

    def test_has_key(self):
        self.properties.has_key.return_value = True
        # getattr because pep8 doesn't like calls to has_key
        self.assertTrue(getattr(self.build, 'has_key')('p'))
        # has_key calls through to hasProperty
        self.properties.hasProperty.assert_called_with('p')

    def test_render(self):
        self.build.render("xyz")
        self.properties.render.assert_called_with("xyz")

    def test_getWorkerName_old_api(self):
        @implementer(interfaces.IProperties)
        class FakeProperties(Mock):
            pass
        import posixpath

        r = FakeRequest()
        build = Build([r])
        build.properties = FakeProperties()
        build.builder = FakeBuilder(self.master)
        build.build_status = FakeBuildStatus()

        w = worker.FakeWorker(self.master)
        w.path_module = posixpath
        w.properties = FakeProperties()
        w.workername = 'worker name'
        w.worker_basedir = None

        workerforbuilder = Mock(name='workerforbuilder')
        workerforbuilder.worker = w

        build.workerforbuilder = workerforbuilder

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            new = build.getWorkerName()

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'getSlaveName' method is deprecated"):
            old = build.getSlaveName()

        self.assertEqual(old, 'worker name')
        self.assertIdentical(new, old)

    def test_workername_old_api(self):
        @implementer(interfaces.IProperties)
        class FakeProperties(Mock):
            pass

        import posixpath

        r = FakeRequest()
        build = Build([r])
        build.properties = FakeProperties()
        build.builder = FakeBuilder(self.master)
        build.build_status = FakeBuildStatus()

        w = worker.FakeWorker(self.master)
        w.path_module = posixpath
        w.properties = FakeProperties()
        w.workername = 'worker name'
        w.worker_basedir = None

        workerforbuilder = Mock(name='workerforbuilder')
        workerforbuilder.worker = w

        build.setupWorkerForBuilder(workerforbuilder)

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            new = build.workername

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'slavename' attribute is deprecated"):
            old = build.slavename

        self.assertEqual(old, 'worker name')
        self.assertIdentical(new, old)
