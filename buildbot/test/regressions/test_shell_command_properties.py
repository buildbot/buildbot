from twisted.trial import unittest

from buildbot.steps.shell import ShellCommand, SetProperty
from buildbot.process.properties import WithProperties, Properties
from buildbot.process.factory import BuildFactory
from buildbot.buildrequest import BuildRequest
from buildbot.sourcestamp import SourceStamp

class FakeSlaveBuilder:
    slave = None

class FakeBuildStatus:
    def __init__(self):
        self.names = []

    def addStepWithName(self, name):
        self.names.append(name)
        return FakeStepStatus()

    def getProperties(self):
        return Properties()

    def setSourceStamp(self, ss):
        self.ss = ss

    def setReason(self, reason):
        self.reason = reason

    def setBlamelist(self, bl):
        self.bl = bl

    def setProgress(self, p):
        self.progress = p


class FakeStepStatus:
    txt = None
    def setText(self, txt):
        self.txt = txt

    def setProgress(self, sp):
        pass


class TestShellCommandProperties(unittest.TestCase):
    def testCommand(self):
        f = BuildFactory()
        f.addStep(SetProperty(command=["echo", "value"], property="propname"))
        f.addStep(ShellCommand(command=["echo", WithProperties("%(propname)s")]))

        ss = SourceStamp()

        req = BuildRequest("Testing", ss, None)

        b = f.newBuild([req])
        b.build_status = FakeBuildStatus()
        b.slavebuilder = FakeSlaveBuilder()

        # This shouldn't raise an exception
        b.setupBuild(None)

class TestSetProperty(unittest.TestCase):
    def testGoodStep(self):
        f = BuildFactory()
        f.addStep(SetProperty(command=["echo", "value"], property="propname"))

        ss = SourceStamp()

        req = BuildRequest("Testing", ss, None)

        b = f.newBuild([req])
        b.build_status = FakeBuildStatus()
        b.slavebuilder = FakeSlaveBuilder()

        # This shouldn't raise an exception
        b.setupBuild(None)

    def testErrorBothSet(self):
        self.assertRaises(AssertionError, SetProperty, command=["echo", "value"], property="propname", extract_fn=lambda x:{"propname": "hello"})

    def testErrorNoneSet(self):
        self.assertRaises(AssertionError, SetProperty, command=["echo", "value"])
