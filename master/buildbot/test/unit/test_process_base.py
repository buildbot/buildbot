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

from twisted.trial import unittest
from twisted.internet import defer

from buildbot.process.base import Build
from buildbot.process.properties import Properties
from buildbot.status.builder import FAILURE, SUCCESS, WARNINGS, RETRY, EXCEPTION
from buildbot.locks import SlaveLock
from buildbot.process.buildstep import LoggingBuildStep

from mock import Mock

class FakeChange(object):
    properties = Properties()
    who = "me"

class FakeSource(object):
    changes = [FakeChange()]
    branch = None
    revision = "12345"
    repository = None
    project = None

class FakeRequest(object):
    startCount = 0
    source = FakeSource()
    reason = "Because"
    properties = Properties()

    def mergeWith(self, others):
        return self.source

    def mergeReasons(self, others):
        return self.reason

class FakeBuildStep(object):
    haltOnFailure = False
    flunkOnWarnings = False
    flunkOnFailure = True
    warnOnWarnings = True
    warnOnFailure = False
    alwaysRun = False
    name = 'fake'

class FakeMaster(object):
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

        self.assertEqual(b.result, EXCEPTION)

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
        self.assertEqual(b.result, EXCEPTION)
        self.assert_( ('interrupt', ('stop it',), {}) not in step.method_calls)

    def testStopBuildWaitingForStepLocks(self):
        r = FakeRequest()

        b = Build([r])
        b.setBuilder(Mock())
        b.builder.botmaster = FakeMaster()
        slavebuilder = Mock()
        status = Mock()

        l = SlaveLock('lock')
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
        self.assertEqual(b.result, EXCEPTION)

    def testStepDone(self):
        r = FakeRequest()
        b = Build([r])
        b.results = [SUCCESS]
        b.result = SUCCESS
        b.remote = Mock()
        step = FakeBuildStep()
        terminate = b.stepDone(SUCCESS, step)
        self.assertEqual(terminate, False)
        self.assertEqual(b.result, SUCCESS)

    def testStepDoneHaltOnFailure(self):
        r = FakeRequest()
        b = Build([r])
        b.results = []
        b.result = SUCCESS
        b.remote = Mock()
        step = FakeBuildStep()
        step.haltOnFailure = True
        terminate = b.stepDone(FAILURE, step)
        self.assertEqual(terminate, True)
        self.assertEqual(b.result, FAILURE)

    def testStepDoneHaltOnFailureNoFlunkOnFailure(self):
        r = FakeRequest()
        b = Build([r])
        b.results = []
        b.result = SUCCESS
        b.remote = Mock()
        step = FakeBuildStep()
        step.flunkOnFailure = False
        step.haltOnFailure = True
        terminate = b.stepDone(FAILURE, step)
        self.assertEqual(terminate, True)
        self.assertEqual(b.result, SUCCESS)

    def testStepDoneFlunkOnWarningsFlunkOnFailure(self):
        r = FakeRequest()
        b = Build([r])
        b.results = []
        b.result = SUCCESS
        b.remote = Mock()
        step = FakeBuildStep()
        step.flunkOnFailure = True
        step.flunkOnWarnings = True
        b.stepDone(WARNINGS, step)
        terminate = b.stepDone(FAILURE, step)
        self.assertEqual(terminate, False)
        self.assertEqual(b.result, FAILURE)

    def testStepDoneNoWarnOnWarnings(self):
        r = FakeRequest()
        b = Build([r])
        b.results = [SUCCESS]
        b.result = SUCCESS
        b.remote = Mock()
        step = FakeBuildStep()
        step.warnOnWarnings = False
        terminate = b.stepDone(WARNINGS, step)
        self.assertEqual(terminate, False)
        self.assertEqual(b.result, SUCCESS)

    def testStepDoneWarnings(self):
        r = FakeRequest()
        b = Build([r])
        b.results = [SUCCESS]
        b.result = SUCCESS
        b.remote = Mock()
        step = FakeBuildStep()
        terminate = b.stepDone(WARNINGS, step)
        self.assertEqual(terminate, False)
        self.assertEqual(b.result, WARNINGS)

    def testStepDoneFail(self):
        r = FakeRequest()
        b = Build([r])
        b.results = [SUCCESS]
        b.result = SUCCESS
        b.remote = Mock()
        step = FakeBuildStep()
        terminate = b.stepDone(FAILURE, step)
        self.assertEqual(terminate, False)
        self.assertEqual(b.result, FAILURE)

    def testStepDoneFailOverridesWarnings(self):
        r = FakeRequest()
        b = Build([r])
        b.results = [SUCCESS, WARNINGS]
        b.result = WARNINGS
        b.remote = Mock()
        step = FakeBuildStep()
        terminate = b.stepDone(FAILURE, step)
        self.assertEqual(terminate, False)
        self.assertEqual(b.result, FAILURE)

    def testStepDoneWarnOnFailure(self):
        r = FakeRequest()
        b = Build([r])
        b.results = [SUCCESS]
        b.result = SUCCESS
        b.remote = Mock()
        step = FakeBuildStep()
        step.warnOnFailure = True
        step.flunkOnFailure = False
        terminate = b.stepDone(FAILURE, step)
        self.assertEqual(terminate, False)
        self.assertEqual(b.result, WARNINGS)

    def testStepDoneFlunkOnWarnings(self):
        r = FakeRequest()
        b = Build([r])
        b.results = [SUCCESS]
        b.result = SUCCESS
        b.remote = Mock()
        step = FakeBuildStep()
        step.flunkOnWarnings = True
        terminate = b.stepDone(WARNINGS, step)
        self.assertEqual(terminate, False)
        self.assertEqual(b.result, FAILURE)

    def testStepDoneHaltOnFailureFlunkOnWarnings(self):
        r = FakeRequest()
        b = Build([r])
        b.results = [SUCCESS]
        b.result = SUCCESS
        b.remote = Mock()
        step = FakeBuildStep()
        step.flunkOnWarnings = True
        self.haltOnFailure = True
        terminate = b.stepDone(WARNINGS, step)
        self.assertEqual(terminate, False)
        self.assertEqual(b.result, FAILURE)

    def testStepDoneWarningsDontOverrideFailure(self):
        r = FakeRequest()
        b = Build([r])
        b.results = [FAILURE]
        b.result = FAILURE
        b.remote = Mock()
        step = FakeBuildStep()
        terminate = b.stepDone(WARNINGS, step)
        self.assertEqual(terminate, False)
        self.assertEqual(b.result, FAILURE)

    def testStepDoneRetryOverridesAnythingElse(self):
        r = FakeRequest()
        b = Build([r])
        b.results = [RETRY]
        b.result = RETRY
        b.remote = Mock()
        step = FakeBuildStep()
        step.alwaysRun = True
        b.stepDone(WARNINGS, step)
        b.stepDone(FAILURE, step)
        b.stepDone(SUCCESS, step)
        terminate = b.stepDone(EXCEPTION, step)
        self.assertEqual(terminate, True)
        self.assertEqual(b.result, RETRY)
