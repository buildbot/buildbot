from buildbot.process.build import Build
from buildbot.process.properties import Properties
from mock import Mock
from buildbot.locks import SlaveLock
from twisted.trial import unittest
from buildbot.steps import artifact
from zope.interface import implements
from buildbot import interfaces
from buildbot.test.fake.fakebuild import  FakeStepFactory, FakeBuildStatus
from buildbot.test.fake.fakemaster import FakeMaster

class FakeRequest:
    def __init__(self):
        self.sources = []
        self.reason = "Because"
        self.properties = Properties()

    def mergeSourceStampsWith(self, others):
        return self.sources

    def mergeReasons(self, others):
        return self.reason


class TestStepLocks(unittest.TestCase):

    def setUp(self):
        r = FakeRequest()

        self.request = r
        self.master = FakeMaster()
        self.master.maybeStartBuildsForSlave = lambda slave: True

        self.build = Build([r])
        self.builder = Mock()
        self.builder.botmaster = self.master.botmaster
        self.build.setBuilder(self.builder)

    def test_acquire_build_Lock_step(self):
        b = self.build
        slavebuilder = Mock()

        l = SlaveLock("slave_builds",
                             maxCount=1)

        self.assertEqual(len(b.locks), 0)
        step = artifact.AcquireBuildLocks(locks=[l.access('exclusive')])
        b.setStepFactories([FakeStepFactory(step)])
        b.startBuild(FakeBuildStatus(), None, slavebuilder)
        b.currentStep.start()
        self.assertEqual(len(b.locks), 1)
        self.assertTrue(b.locks[0][0].owners[0][0], step)

    def test_release_build_Lock_step(self):
        b = self.build
        slavebuilder = Mock()

        l = SlaveLock("slave_builds",
                             maxCount=1)

        step = artifact.AcquireBuildLocks(locks=[l.access('exclusive')])
        step2 = artifact.ReleaseBuildLocks()
        b.setStepFactories([FakeStepFactory(step), FakeStepFactory(step2)])
        self.assertEqual(len(b.locks), 0)

        b.startBuild(FakeBuildStatus(), None, slavebuilder)
        b.currentStep.start()
        self.assertTrue(b.locks[0][0].owners[0][0], step)

        b.currentStep.start()
        self.assertEqual(len(b.locks[0][0].owners), 0)
