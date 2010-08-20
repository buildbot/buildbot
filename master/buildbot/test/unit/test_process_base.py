from twisted.trial import unittest
from twisted.internet import defer

from buildbot.process.base import Build
from buildbot.process.properties import Properties
from buildbot.buildrequest import BuildRequest
from buildbot.status.builder import FAILURE, SUCCESS
from buildbot.locks import SlaveLock, RealSlaveLock
from buildbot.process.buildstep import BuildStep, LoggingBuildStep

from mock import Mock

class FakeChange:
    properties = Properties()
    who = "me"

class FakeSource:
    changes = [FakeChange()]
    branch = None
    revision = "12345"
    repository = None
    project = None

class FakeRequest:
    startCount = 0
    source = FakeSource()
    reason = "Because"
    properties = Properties()

    def mergeWith(self, others):
        return self.source

    def mergeReasons(self, others):
        return self.reason

class FakeMaster:
    locks = {}
    parent = Mock()
    def getLockByID(self, lockid):
        if not lockid in self.locks:
            self.locks[lockid] = lockid.lockClass(lockid)
        return self.locks[lockid]

class TestBuild(unittest.TestCase):
    def testRunSuccessfulBuild(self):
        r = FakeRequest()

        b = Build([r])
        b.setBuilder(Mock())

        step = Mock()
        step.return_value = step
        step.startStep.return_value = SUCCESS
        b.setStepFactories([(step, {})])

        slavebuilder = Mock()
        status = Mock()

        b.startBuild(status, None, slavebuilder)

        self.assertEqual(b.result, SUCCESS)
        self.assert_( ('startStep', (b.remote,), {}) in step.method_calls)

    def testStopBuild(self):
        r = FakeRequest()

        b = Build([r])
        b.setBuilder(Mock())

        step = Mock()
        step.return_value = step
        b.setStepFactories([(step, {})])

        slavebuilder = Mock()
        status = Mock()

        def startStep(*args, **kw):
            # Now interrupt the build
            b.stopBuild("stop it")
            return defer.Deferred()
        step.startStep = startStep

        b.startBuild(status, None, slavebuilder)

        self.assert_("Interrupted" in b.text)
        self.assertEqual(b.result, FAILURE)

        self.assert_( ('interrupt', ('stop it',), {}) in step.method_calls)

    def testBuildLocksAcquired(self):
        r = FakeRequest()

        b = Build([r])
        b.setBuilder(Mock())
        b.builder.botmaster = FakeMaster()
        slavebuilder = Mock()
        status = Mock()

        l = SlaveLock('lock')
        claimCount = [0]
        lock_access = l.access('counting')
        l.access = lambda mode: lock_access
        real_lock = b.builder.botmaster.getLockByID(l).getLock(slavebuilder)
        def claim(owner, access):
            claimCount[0] += 1
            return real_lock.old_claim(owner, access)
        real_lock.old_claim = real_lock.claim
        real_lock.claim = claim
        b.setLocks([l])

        step = Mock()
        step.return_value = step
        step.startStep.return_value = SUCCESS
        b.setStepFactories([(step, {})])

        b.startBuild(status, None, slavebuilder)

        self.assertEqual(b.result, SUCCESS)
        self.assert_( ('startStep', (b.remote,), {}) in step.method_calls)
        self.assertEquals(claimCount[0], 1)

    def testBuildWaitingForLocks(self):
        r = FakeRequest()

        b = Build([r])
        b.setBuilder(Mock())
        b.builder.botmaster = FakeMaster()
        slavebuilder = Mock()
        status = Mock()

        l = SlaveLock('lock')
        claimCount = [0]
        lock_access = l.access('counting')
        l.access = lambda mode: lock_access
        real_lock = b.builder.botmaster.getLockByID(l).getLock(slavebuilder)
        def claim(owner, access):
            claimCount[0] += 1
            return real_lock.old_claim(owner, access)
        real_lock.old_claim = real_lock.claim
        real_lock.claim = claim
        b.setLocks([l])

        step = Mock()
        step.return_value = step
        step.startStep.return_value = SUCCESS
        b.setStepFactories([(step, {})])

        real_lock.claim(Mock(), l.access('counting'))

        b.startBuild(status, None, slavebuilder)

        self.assert_( ('startStep', (b.remote,), {}) not in step.method_calls)
        self.assertEquals(claimCount[0], 1)
        self.assert_(b.currentStep is None)
        self.assert_(b._acquiringLock is not None)

    def testStopBuildWaitingForLocks(self):
        r = FakeRequest()

        b = Build([r])
        b.setBuilder(Mock())
        b.builder.botmaster = FakeMaster()
        slavebuilder = Mock()
        status = Mock()

        l = SlaveLock('lock')
        claimCount = [0]
        lock_access = l.access('counting')
        l.access = lambda mode: lock_access
        real_lock = b.builder.botmaster.getLockByID(l).getLock(slavebuilder)
        b.setLocks([l])

        step = Mock()
        step.return_value = step
        step.startStep.return_value = SUCCESS
        b.setStepFactories([(step, {})])

        real_lock.claim(Mock(), l.access('counting'))

        def acquireLocks(res=None):
            retval = Build.acquireLocks(b, res)
            b.stopBuild('stop it')
            return retval
        b.acquireLocks = acquireLocks

        b.startBuild(status, None, slavebuilder)

        self.assert_( ('startStep', (b.remote,), {}) not in step.method_calls)
        self.assert_(b.currentStep is None)
        self.assert_("Interrupted" in b.text, b.text)
        self.assertEqual(b.result, FAILURE)
        self.assert_( ('interrupt', ('stop it',), {}) not in step.method_calls)

    def testStopBuildWaitingForStepLocks(self):
        r = FakeRequest()

        b = Build([r])
        b.setBuilder(Mock())
        b.builder.botmaster = FakeMaster()
        slavebuilder = Mock()
        status = Mock()

        l = SlaveLock('lock')
        claimCount = [0]
        lock_access = l.access('counting')
        l.access = lambda mode: lock_access
        real_lock = b.builder.botmaster.getLockByID(l).getLock(slavebuilder)

        step = LoggingBuildStep(locks=[lock_access])
        def factory(*args):
            return step
        b.setStepFactories([(factory, {})])

        real_lock.claim(Mock(), l.access('counting'))

        gotLocks = [False]

        def acquireLocks(res=None):
            gotLocks[0] = True
            retval = LoggingBuildStep.acquireLocks(step, res)
            self.assert_(b.currentStep is step)
            b.stopBuild('stop it')
            return retval
        step.acquireLocks = acquireLocks
        step.setStepStatus = Mock()
        step.step_status = Mock()
        step.step_status.addLog().chunkSize = 10
        step.step_status.getLogs.return_value = []

        b.startBuild(status, None, slavebuilder)

        self.assertEqual(gotLocks, [True])
        self.assert_(('stepStarted', (), {}) in step.step_status.method_calls)
        self.assert_("Interrupted" in b.text, b.text)
        self.assertEqual(b.result, FAILURE)
