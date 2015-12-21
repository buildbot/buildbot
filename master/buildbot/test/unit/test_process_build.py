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

import operator

from buildbot import interfaces
from buildbot.locks import SlaveLock
from buildbot.process.build import Build
from buildbot.process.buildstep import BuildStep
from buildbot.process.buildstep import LoggingBuildStep
from buildbot.process.properties import Properties
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.test.fake import fakemaster
from buildbot.test.fake import fakeprotocol
from buildbot.test.fake import slave
from buildbot.test.fake.fakebuild import FakeBuildStatus
from twisted.internet import defer
from twisted.trial import unittest
from zope.interface import implements

from mock import Mock
from mock import call


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


class FakeBuildStep:

    def __init__(self):
        self.haltOnFailure = False
        self.flunkOnWarnings = False
        self.flunkOnFailure = True
        self.warnOnWarnings = True
        self.warnOnFailure = False
        self.alwaysRun = False
        self.name = 'fake'


class FakeBuilder:

    def __init__(self, master):
        self.config = Mock()
        self.config.slavebuilddir = 'sbd'
        self.name = 'fred'
        self.master = master
        self.botmaster = master.botmaster

    def getBuilderId(self):
        return defer.succeed(83)

    def setupProperties(self, props):
        pass


class FakeStepFactory(object):

    """Fake step factory that just returns a fixed step object."""
    implements(interfaces.IBuildStepFactory)

    def __init__(self, step):
        self.step = step

    def buildStep(self):
        return self.step


class TestBuild(unittest.TestCase):

    def setUp(self):
        r = FakeRequest()
        r.sources = [FakeSource()]
        r.sources[0].changes = [FakeChange()]
        r.sources[0].revision = "12345"

        self.request = r
        self.master = fakemaster.make_master(wantData=True, testcase=self)

        self.slave = slave.FakeSlave(self.master)
        self.slave.attached(None)
        self.builder = FakeBuilder(self.master)
        self.build = Build([r])
        self.build.conn = fakeprotocol.FakeConnection(self.master, self.slave)

        self.slavebuilder = Mock(name='slavebuilder')
        self.slavebuilder.slave = self.slave

        self.build.setBuilder(self.builder)

    def testRunSuccessfulBuild(self):
        b = self.build

        step = Mock()
        step.return_value = step
        step.startStep.return_value = SUCCESS
        b.setStepFactories([FakeStepFactory(step)])

        b.startBuild(FakeBuildStatus(), None, self.slavebuilder)

        self.assertEqual(b.results, SUCCESS)
        self.assert_(('startStep', (self.slavebuilder.slave.conn,), {})
                     in step.method_calls)

    def testStopBuild(self):
        b = self.build

        step = Mock()
        step.return_value = step
        b.setStepFactories([FakeStepFactory(step)])

        def startStep(*args, **kw):
            # Now interrupt the build
            b.stopBuild("stop it")
            return defer.Deferred()
        step.startStep = startStep

        b.startBuild(FakeBuildStatus(), None, self.slavebuilder)

        self.assertEqual(b.results, CANCELLED)

        self.assert_(('interrupt', ('stop it',), {}) in step.method_calls)

    def testAlwaysRunStepStopBuild(self):
        """Test that steps marked with alwaysRun=True still get run even if
        the build is stopped."""

        # Create a build with 2 steps, the first one will get interrupted, and
        # the second one is marked with alwaysRun=True
        b = self.build

        step1 = Mock()
        step1.return_value = step1
        step1.alwaysRun = False
        step2 = Mock()
        step2.return_value = step2
        step2.alwaysRun = True
        b.setStepFactories([
            FakeStepFactory(step1),
            FakeStepFactory(step2),
        ])

        def startStep1(*args, **kw):
            # Now interrupt the build
            b.stopBuild("stop it")
            return defer.succeed(SUCCESS)
        step1.startStep = startStep1
        step1.stepDone.return_value = False

        step2Started = [False]

        def startStep2(*args, **kw):
            step2Started[0] = True
            return defer.succeed(SUCCESS)
        step2.startStep = startStep2
        step1.stepDone.return_value = False

        d = b.startBuild(FakeBuildStatus(), None, self.slavebuilder)

        def check(ign):
            self.assertEqual(b.results, CANCELLED)
            self.assert_(('interrupt', ('stop it',), {}) in step1.method_calls)
            self.assert_(step2Started[0])
        d.addCallback(check)
        return d

    def testBuildcanStartWithSlavebuilder(self):
        b = self.build

        slavebuilder1 = Mock()
        slavebuilder2 = Mock()

        l = SlaveLock('lock')
        counting_access = l.access('counting')
        real_lock = b.builder.botmaster.getLockByID(l)

        # no locks, so both these pass (call twice to verify there's no state/memory)
        lock_list = [(real_lock, counting_access)]
        self.assertTrue(Build.canStartWithSlavebuilder(lock_list, slavebuilder1))
        self.assertTrue(Build.canStartWithSlavebuilder(lock_list, slavebuilder1))
        self.assertTrue(Build.canStartWithSlavebuilder(lock_list, slavebuilder2))
        self.assertTrue(Build.canStartWithSlavebuilder(lock_list, slavebuilder2))

        slave_lock_1 = real_lock.getLock(slavebuilder1.slave)
        slave_lock_2 = real_lock.getLock(slavebuilder2.slave)

        # then have slavebuilder2 claim its lock:
        slave_lock_2.claim(slavebuilder2, counting_access)
        self.assertTrue(Build.canStartWithSlavebuilder(lock_list, slavebuilder1))
        self.assertTrue(Build.canStartWithSlavebuilder(lock_list, slavebuilder1))
        self.assertFalse(Build.canStartWithSlavebuilder(lock_list, slavebuilder2))
        self.assertFalse(Build.canStartWithSlavebuilder(lock_list, slavebuilder2))
        slave_lock_2.release(slavebuilder2, counting_access)

        # then have slavebuilder1 claim its lock:
        slave_lock_1.claim(slavebuilder1, counting_access)
        self.assertFalse(Build.canStartWithSlavebuilder(lock_list, slavebuilder1))
        self.assertFalse(Build.canStartWithSlavebuilder(lock_list, slavebuilder1))
        self.assertTrue(Build.canStartWithSlavebuilder(lock_list, slavebuilder2))
        self.assertTrue(Build.canStartWithSlavebuilder(lock_list, slavebuilder2))
        slave_lock_1.release(slavebuilder1, counting_access)

    def testBuilddirPropType(self):
        import posixpath

        b = self.build

        b.build_status = Mock()
        b.builder.config.slavebuilddir = 'test'
        self.slavebuilder.slave.slave_basedir = "/srv/buildbot/slave"
        self.slavebuilder.slave.path_module = posixpath
        b.getProperties = Mock()
        b.setProperty = Mock()

        b.setupSlaveBuilder(self.slavebuilder)

        expected_path = '/srv/buildbot/slave/test'

        b.setProperty.assert_has_calls(
            [call('workdir', expected_path, 'slave (deprecated)'),
             call('builddir', expected_path, 'slave')],
            any_order=True)

    def testBuildLocksAcquired(self):
        b = self.build

        l = SlaveLock('lock')
        claimCount = [0]
        lock_access = l.access('counting')
        l.access = lambda mode: lock_access
        real_lock = b.builder.botmaster.getLockByID(l) \
            .getLock(self.slavebuilder.slave)

        def claim(owner, access):
            claimCount[0] += 1
            return real_lock.old_claim(owner, access)
        real_lock.old_claim = real_lock.claim
        real_lock.claim = claim
        b.setLocks([lock_access])

        step = Mock()
        step.return_value = step
        step.startStep.return_value = SUCCESS
        b.setStepFactories([FakeStepFactory(step)])

        b.startBuild(FakeBuildStatus(), None, self.slavebuilder)

        self.assertEqual(b.results, SUCCESS)
        self.assertIn(('startStep', (self.slavebuilder.slave.conn,), {}),
                      step.method_calls)
        self.assertEquals(claimCount[0], 1)

    def testBuildLocksOrder(self):
        """Test that locks are acquired in FIFO order; specifically that
        counting locks cannot jump ahead of exclusive locks"""
        eBuild = self.build

        cBuilder = FakeBuilder(self.master)
        cBuild = Build([self.request])
        cBuild.setBuilder(cBuilder)

        eSlavebuilder = Mock()
        cSlavebuilder = Mock()

        eSlavebuilder.slave = self.slave
        cSlavebuilder.slave = self.slave

        l = SlaveLock('lock', 2)
        claimLog = []
        realLock = self.master.botmaster.getLockByID(l).getLock(self.slave)

        def claim(owner, access):
            claimLog.append(owner)
            return realLock.oldClaim(owner, access)
        realLock.oldClaim = realLock.claim
        realLock.claim = claim

        eBuild.setLocks([l.access('exclusive')])
        cBuild.setLocks([l.access('counting')])

        fakeBuild = Mock()
        fakeBuildAccess = l.access('counting')
        realLock.claim(fakeBuild, fakeBuildAccess)

        step = Mock()
        step.return_value = step
        step.startStep.return_value = SUCCESS
        eBuild.setStepFactories([FakeStepFactory(step)])
        cBuild.setStepFactories([FakeStepFactory(step)])

        e = eBuild.startBuild(FakeBuildStatus(), None, eSlavebuilder)
        c = cBuild.startBuild(FakeBuildStatus(), None, cSlavebuilder)
        d = defer.DeferredList([e, c])

        realLock.release(fakeBuild, fakeBuildAccess)

        def check(ign):
            self.assertEqual(eBuild.results, SUCCESS)
            self.assertEqual(cBuild.results, SUCCESS)
            self.assertEquals(claimLog, [fakeBuild, eBuild, cBuild])

        d.addCallback(check)
        return d

    def testBuildWaitingForLocks(self):
        b = self.build

        l = SlaveLock('lock')
        claimCount = [0]
        lock_access = l.access('counting')
        l.access = lambda mode: lock_access
        real_lock = b.builder.botmaster.getLockByID(l) \
            .getLock(self.slavebuilder.slave)

        def claim(owner, access):
            claimCount[0] += 1
            return real_lock.old_claim(owner, access)
        real_lock.old_claim = real_lock.claim
        real_lock.claim = claim
        b.setLocks([lock_access])

        step = Mock()
        step.return_value = step
        step.startStep.return_value = SUCCESS
        b.setStepFactories([FakeStepFactory(step)])

        real_lock.claim(Mock(), l.access('counting'))

        b.startBuild(FakeBuildStatus(), None, self.slavebuilder)

        self.assert_(('startStep', (self.slavebuilder.slave.conn,), {})
                     not in step.method_calls)
        self.assertEquals(claimCount[0], 1)
        self.assert_(b.currentStep is None)
        self.assert_(b._acquiringLock is not None)

    def testStopBuildWaitingForLocks(self):
        b = self.build

        l = SlaveLock('lock')
        lock_access = l.access('counting')
        l.access = lambda mode: lock_access
        real_lock = b.builder.botmaster.getLockByID(l) \
            .getLock(self.slavebuilder.slave)
        b.setLocks([lock_access])

        step = Mock()
        step.return_value = step
        step.startStep.return_value = SUCCESS
        step.alwaysRun = False
        b.setStepFactories([FakeStepFactory(step)])

        real_lock.claim(Mock(), l.access('counting'))

        def acquireLocks(res=None):
            retval = Build.acquireLocks(b, res)
            b.stopBuild('stop it')
            return retval
        b.acquireLocks = acquireLocks

        b.startBuild(FakeBuildStatus(), None, self.slavebuilder)

        self.assert_(('startStep', (self.slavebuilder.slave.conn,), {})
                     not in step.method_calls)
        self.assert_(b.currentStep is None)
        self.assertEqual(b.results, CANCELLED)
        self.assert_(('interrupt', ('stop it',), {}) not in step.method_calls)

    def testStopBuildWaitingForLocks_lostRemote(self):
        b = self.build

        l = SlaveLock('lock')
        lock_access = l.access('counting')
        l.access = lambda mode: lock_access
        real_lock = b.builder.botmaster.getLockByID(l) \
            .getLock(self.slavebuilder.slave)
        b.setLocks([lock_access])

        step = Mock()
        step.return_value = step
        step.startStep.return_value = SUCCESS
        step.alwaysRun = False
        b.setStepFactories([FakeStepFactory(step)])

        real_lock.claim(Mock(), l.access('counting'))

        def acquireLocks(res=None):
            retval = Build.acquireLocks(b, res)
            b.lostRemote()
            return retval
        b.acquireLocks = acquireLocks

        b.startBuild(FakeBuildStatus(), None, self.slavebuilder)

        self.assert_(('startStep', (self.slavebuilder.slave.conn,), {})
                     not in step.method_calls)
        self.assert_(b.currentStep is None)
        self.assertEqual(b.results, RETRY)
        self.assert_(('interrupt', ('stop it',), {}) not in step.method_calls)
        self.build.build_status.setText.assert_called_with(["retry", "lost", "connection"])
        self.build.build_status.setResults.assert_called_with(RETRY)

    def testStopBuildWaitingForStepLocks(self):
        b = self.build

        l = SlaveLock('lock')
        lock_access = l.access('counting')
        l.access = lambda mode: lock_access
        real_lock = b.builder.botmaster.getLockByID(l) \
            .getLock(self.slavebuilder.slave)

        step = LoggingBuildStep(locks=[lock_access])
        b.setStepFactories([FakeStepFactory(step)])

        real_lock.claim(Mock(), l.access('counting'))

        gotLocks = [False]

        def acquireLocks(res=None):
            gotLocks[0] = True
            retval = LoggingBuildStep.acquireLocks(step, res)
            self.assert_(b.currentStep is step)
            b.stopBuild('stop it')
            return retval
        step.acquireLocks = acquireLocks

        b.startBuild(FakeBuildStatus(), None, self.slavebuilder)

        self.assertEqual(gotLocks, [True])
        self.assertEqual(b.results, CANCELLED)

    def testStepDone(self):
        b = self.build
        b.results = [SUCCESS]
        b.results = SUCCESS
        step = FakeBuildStep()
        terminate = b.stepDone(SUCCESS, step)
        self.assertEqual(terminate, False)
        self.assertEqual(b.results, SUCCESS)

    def testStepDoneHaltOnFailure(self):
        b = self.build
        b.results = []
        b.results = SUCCESS
        step = FakeBuildStep()
        step.haltOnFailure = True
        terminate = b.stepDone(FAILURE, step)
        self.assertEqual(terminate, True)
        self.assertEqual(b.results, FAILURE)

    def testStepDoneHaltOnFailureNoFlunkOnFailure(self):
        b = self.build
        b.results = []
        b.results = SUCCESS
        step = FakeBuildStep()
        step.flunkOnFailure = False
        step.haltOnFailure = True
        terminate = b.stepDone(FAILURE, step)
        self.assertEqual(terminate, True)
        self.assertEqual(b.results, SUCCESS)

    def testStepDoneFlunkOnWarningsFlunkOnFailure(self):
        b = self.build
        b.results = []
        b.results = SUCCESS
        step = FakeBuildStep()
        step.flunkOnFailure = True
        step.flunkOnWarnings = True
        b.stepDone(WARNINGS, step)
        terminate = b.stepDone(FAILURE, step)
        self.assertEqual(terminate, False)
        self.assertEqual(b.results, FAILURE)

    def testStepDoneNoWarnOnWarnings(self):
        b = self.build
        b.results = [SUCCESS]
        b.results = SUCCESS
        step = FakeBuildStep()
        step.warnOnWarnings = False
        terminate = b.stepDone(WARNINGS, step)
        self.assertEqual(terminate, False)
        self.assertEqual(b.results, SUCCESS)

    def testStepDoneWarnings(self):
        b = self.build
        b.results = [SUCCESS]
        b.results = SUCCESS
        step = FakeBuildStep()
        terminate = b.stepDone(WARNINGS, step)
        self.assertEqual(terminate, False)
        self.assertEqual(b.results, WARNINGS)

    def testStepDoneFail(self):
        b = self.build
        b.results = [SUCCESS]
        b.results = SUCCESS
        step = FakeBuildStep()
        terminate = b.stepDone(FAILURE, step)
        self.assertEqual(terminate, False)
        self.assertEqual(b.results, FAILURE)

    def testStepDoneFailOverridesWarnings(self):
        b = self.build
        b.results = [SUCCESS, WARNINGS]
        b.results = WARNINGS
        step = FakeBuildStep()
        terminate = b.stepDone(FAILURE, step)
        self.assertEqual(terminate, False)
        self.assertEqual(b.results, FAILURE)

    def testStepDoneWarnOnFailure(self):
        b = self.build
        b.results = [SUCCESS]
        b.results = SUCCESS
        step = FakeBuildStep()
        step.warnOnFailure = True
        step.flunkOnFailure = False
        terminate = b.stepDone(FAILURE, step)
        self.assertEqual(terminate, False)
        self.assertEqual(b.results, WARNINGS)

    def testStepDoneFlunkOnWarnings(self):
        b = self.build
        b.results = [SUCCESS]
        b.results = SUCCESS
        step = FakeBuildStep()
        step.flunkOnWarnings = True
        terminate = b.stepDone(WARNINGS, step)
        self.assertEqual(terminate, False)
        self.assertEqual(b.results, FAILURE)

    def testStepDoneHaltOnFailureFlunkOnWarnings(self):
        b = self.build
        b.results = [SUCCESS]
        b.results = SUCCESS
        step = FakeBuildStep()
        step.flunkOnWarnings = True
        self.haltOnFailure = True
        terminate = b.stepDone(WARNINGS, step)
        self.assertEqual(terminate, False)
        self.assertEqual(b.results, FAILURE)

    def testStepDoneWarningsDontOverrideFailure(self):
        b = self.build
        b.results = [FAILURE]
        b.results = FAILURE
        step = FakeBuildStep()
        terminate = b.stepDone(WARNINGS, step)
        self.assertEqual(terminate, False)
        self.assertEqual(b.results, FAILURE)

    def testStepDoneRetryOverridesAnythingElse(self):
        b = self.build
        b.results = [RETRY]
        b.results = RETRY
        step = FakeBuildStep()
        step.alwaysRun = True
        b.stepDone(WARNINGS, step)
        b.stepDone(FAILURE, step)
        b.stepDone(SUCCESS, step)
        terminate = b.stepDone(EXCEPTION, step)
        self.assertEqual(terminate, True)
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
        self.assertEquals(res, result)
        self.assertEqual(self.master.data.updates.properties,
                         [(43, u'foo', 'bar', u'test')])

    def create_mock_steps(self, names):
        steps = []

        def create_mock_step(name):
            step = Mock()
            step.return_value = step
            step.startStep.return_value = SUCCESS
            step.name = name
            return step

        for name in names:
            step = create_mock_step(name)
            steps.append(step)
        return steps

    def testAddStepsAfterCurrentStep(self):
        b = self.build

        steps = self.create_mock_steps(["a", "b", "c"])

        def startStepB(*args, **kw):
            new_steps = self.create_mock_steps(["d", "e"])
            b.addStepsAfterCurrentStep([FakeStepFactory(s) for s in new_steps])
            return SUCCESS

        steps[1].startStep = startStepB
        b.setStepFactories([FakeStepFactory(s) for s in steps])

        b.startBuild(FakeBuildStatus(), None, self.slavebuilder)
        self.assertEqual(b.results, SUCCESS)
        expected_names = ["a", "b", "d", "e", "c"]
        executed_names = [s.name for s in b.executedSteps]
        self.assertEqual(executed_names, expected_names)

    def testAddStepsAfterLastStep(self):
        b = self.build

        steps = self.create_mock_steps(["a", "b", "c"])

        def startStepB(*args, **kw):
            new_steps = self.create_mock_steps(["d", "e"])
            b.addStepsAfterLastStep([FakeStepFactory(s) for s in new_steps])
            return SUCCESS

        steps[1].startStep = startStepB
        b.setStepFactories([FakeStepFactory(s) for s in steps])

        b.startBuild(FakeBuildStatus(), None, self.slavebuilder)
        self.assertEqual(b.results, SUCCESS)
        expected_names = ["a", "b", "c", "d", "e"]
        executed_names = [s.name for s in b.executedSteps]
        self.assertEqual(executed_names, expected_names)

    def testStepNamesUnique(self):
        # if the step names are unique they should remain unchanged
        b = self.build

        steps = self.create_mock_steps(["clone", "command", "clean"])
        b.setStepFactories([FakeStepFactory(s) for s in steps])

        b.startBuild(FakeBuildStatus(), None, self.slavebuilder)
        self.assertEqual(b.results, SUCCESS)
        expected_names = ["clone", "command", "clean"]
        executed_names = [s.name for s in b.executedSteps]
        self.assertEqual(executed_names, expected_names)

    def testStepNamesDuplicate(self):
        b = self.build

        steps = self.create_mock_steps(["stage", "stage", "stage"])
        b.setStepFactories([FakeStepFactory(s) for s in steps])

        b.startBuild(FakeBuildStatus(), None, self.slavebuilder)
        self.assertEqual(b.results, SUCCESS)
        expected_names = ["stage", "stage_1", "stage_2"]
        executed_names = [s.name for s in b.executedSteps]
        self.assertEqual(executed_names, expected_names)

    def testStepNamesDuplicateAfterAdd(self):
        b = self.build

        steps = self.create_mock_steps(["a", "b", "c"])

        def startStepB(*args, **kw):
            new_steps = self.create_mock_steps(["c", "c"])
            b.addStepsAfterCurrentStep([FakeStepFactory(s) for s in new_steps])
            return SUCCESS

        steps[1].startStep = startStepB
        b.setStepFactories([FakeStepFactory(s) for s in steps])

        b.startBuild(FakeBuildStatus(), None, self.slavebuilder)
        self.assertEqual(b.results, SUCCESS)
        expected_names = ["a", "b", "c_1", "c_2", "c"]
        executed_names = [s.name for s in b.executedSteps]
        self.assertEqual(executed_names, expected_names)


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

        self.assertEqual([source1.repository, source1.revision], ["repoA", "12345"])
        self.assertEqual([source2.repository, source2.revision], ["repoB", "67890"])

    def test_buildReturnSourceStamp_empty_codebase(self):
        """
        Test that a build returns the correct sourcestamp if codebase is empty
        """
        codebase = ''
        source3 = self.build.getSourceStamp(codebase)
        self.assertTrue(source3 is not None)
        self.assertEqual([source3.repository, source3.revision], ["repoC", "111213"])


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
        self.build.setupProperties()
        self.assertTrue("codebase" not in self.props["Build"])
        self.assertTrue("revision" not in self.props["Build"])
        self.assertTrue("branch" not in self.props["Build"])
        self.assertTrue("project" not in self.props["Build"])
        self.assertTrue("repository" not in self.props["Build"])


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
        self.build.setupProperties()
        codebase = self.props["Build"]["codebase"]
        self.assertEqual(codebase, "A")

    def test_properties_repository(self):
        self.build.setupProperties()
        repository = self.props["Build"]["repository"]
        self.assertEqual(repository, "http://svn-repo-A")

    def test_properties_revision(self):
        self.build.setupProperties()
        revision = self.props["Build"]["revision"]
        self.assertEqual(revision, "12345")

    def test_properties_branch(self):
        self.build.setupProperties()
        branch = self.props["Build"]["branch"]
        self.assertEqual(branch, "develop")

    def test_property_project(self):
        self.build.setupProperties()
        project = self.props["Build"]["project"]
        self.assertEqual(project, '')


class TestBuildProperties(unittest.TestCase):

    """
    Test that a Build has the necessary L{IProperties} methods, and that they
    properly delegate to the C{build_status} attribute - so really just a test
    of the L{IProperties} adapter.
    """

    def setUp(self):
        class FakeProperties(Mock):
            implements(interfaces.IProperties)

        class FakeBuildStatus(Mock):
            pass
        r = FakeRequest()
        r.sources = [FakeSource()]
        r.sources[0].changes = [FakeChange()]
        r.sources[0].revision = "12345"
        self.master = fakemaster.make_master(wantData=True, testcase=self)
        self.slave = slave.FakeSlave(self.master)
        self.slave.attached(None)
        self.slavebuilder = Mock(name='slavebuilder')
        self.slavebuilder.slave = self.slave
        self.build = Build([r])
        self.build.setStepFactories([])
        self.builder = FakeBuilder(
            fakemaster.make_master(wantData=True, testcase=self))
        self.build.setBuilder(self.builder)
        self.properties = self.build.properties = FakeProperties()
        self.build_status = FakeBuildStatus()
        self.build._flushProperties = Mock()
        self.build.startBuild(self.build_status, None, self.slavebuilder)

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
