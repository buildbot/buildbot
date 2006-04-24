# -*- test-case-name: buildbot.test.test_properties -*-

import os

from twisted.trial import unittest

from buildbot.sourcestamp import SourceStamp
from buildbot.process import base
from buildbot.process.step import ShellCommand, WithProperties
from buildbot.status import builder
from buildbot.slave.commands import rmdirRecursive

class MyBuildStep(ShellCommand):
    def _interpolateProperties(self, command):
        command = ["tar", "czf",
                   "build-%s.tar.gz" % self.getProperty("revision"),
                   "source"]
        return ShellCommand._interpolateProperties(self, command)


class FakeBuild:
    pass
class FakeBuilder:
    statusbag = None
    name = "fakebuilder"
class FakeSlave:
    slavename = "bot12"
class FakeSlaveBuilder:
    slave = FakeSlave()
    def getSlaveCommandVersion(self, command, oldversion=None):
        return "1.10"

class Interpolate(unittest.TestCase):
    def setUp(self):
        self.builder = FakeBuilder()
        self.builder_status = builder.BuilderStatus("fakebuilder")
        self.builder_status.basedir = "test_properties"
        self.builder_status.nextBuildNumber = 0
        rmdirRecursive(self.builder_status.basedir)
        os.mkdir(self.builder_status.basedir)
        self.build_status = self.builder_status.newBuild()
        req = base.BuildRequest("reason", SourceStamp(branch="branch2",
                                                      revision=1234))
        self.build = base.Build([req])
        self.build.setBuilder(self.builder)
        self.build.setupStatus(self.build_status)
        self.build.setupSlaveBuilder(FakeSlaveBuilder())

    def testWithProperties(self):
        self.build.setProperty("revision", 47)
        self.failUnlessEqual(self.build_status.getProperty("revision"), 47)
        c = ShellCommand(workdir=dir, build=self.build,
                         command=["tar", "czf",
                                  WithProperties("build-%s.tar.gz",
                                                 "revision"),
                                  "source"])
        cmd = c._interpolateProperties(c.command)
        self.failUnlessEqual(cmd,
                             ["tar", "czf", "build-47.tar.gz", "source"])

    def testWithPropertiesDict(self):
        self.build.setProperty("other", "foo")
        self.build.setProperty("missing", None)
        c = ShellCommand(workdir=dir, build=self.build,
                         command=["tar", "czf",
                                  WithProperties("build-%(other)s.tar.gz"),
                                  "source"])
        cmd = c._interpolateProperties(c.command)
        self.failUnlessEqual(cmd,
                             ["tar", "czf", "build-foo.tar.gz", "source"])

    def testWithPropertiesMissing(self):
        self.build.setProperty("missing", None)
        c = ShellCommand(workdir=dir, build=self.build,
                         command=["tar", "czf",
                                  WithProperties("build-%(missing)s.tar.gz"),
                                  "source"])
        cmd = c._interpolateProperties(c.command)
        self.failUnlessEqual(cmd,
                             ["tar", "czf", "build-.tar.gz", "source"])

    def testCustomBuildStep(self):
        c = MyBuildStep(workdir=dir, build=self.build)
        cmd = c._interpolateProperties(c.command)
        self.failUnlessEqual(cmd,
                             ["tar", "czf", "build-1234.tar.gz", "source"])

    def testSourceStamp(self):
        c = ShellCommand(workdir=dir, build=self.build,
                         command=["touch",
                                  WithProperties("%s-dir", "branch"),
                                  WithProperties("%s-rev", "revision"),
                                  ])
        cmd = c._interpolateProperties(c.command)
        self.failUnlessEqual(cmd,
                             ["touch", "branch2-dir", "1234-rev"])

    def testSlaveName(self):
        c = ShellCommand(workdir=dir, build=self.build,
                         command=["touch",
                                  WithProperties("%s-slave", "slavename"),
                                  ])
        cmd = c._interpolateProperties(c.command)
        self.failUnlessEqual(cmd,
                             ["touch", "bot12-slave"])


# we test got_revision in test_vc
