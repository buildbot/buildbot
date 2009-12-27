# -*- test-case-name: buildbot.test.test_properties -*-

import os

from twisted.trial import unittest

from buildbot.sourcestamp import SourceStamp
from buildbot.process import base
from buildbot.process.properties import WithProperties, Properties
from buildbot.status import builder
from buildbot.slave.commands import rmdirRecursive
from buildbot.test.runutils import RunMixin


class FakeBuild:
    pass
class FakeBuildMaster:
    properties = Properties(masterprop="master")
class FakeBotMaster:
    parent = FakeBuildMaster()
class FakeBuilder:
    statusbag = None
    name = "fakebuilder"
    botmaster = FakeBotMaster()
class FakeSlave:
    slavename = "bot12"
    properties = Properties(slavename="bot12")
class FakeSlaveBuilder:
    slave = FakeSlave()
    def getSlaveCommandVersion(self, command, oldversion=None):
        return "1.10"
class FakeScheduler:
    name = "fakescheduler"

class TestProperties(unittest.TestCase):
    def setUp(self):
        self.props = Properties()

    def testDictBehavior(self):
        self.props.setProperty("do-tests", 1, "scheduler")
        self.props.setProperty("do-install", 2, "scheduler")

        self.assert_(self.props.has_key('do-tests'))
        self.failUnlessEqual(self.props['do-tests'], 1)
        self.failUnlessEqual(self.props['do-install'], 2)
        self.assertRaises(KeyError, lambda : self.props['do-nothing'])
        self.failUnlessEqual(self.props.getProperty('do-install'), 2)

    def testUpdate(self):
        self.props.setProperty("x", 24, "old")
        newprops = { 'a' : 1, 'b' : 2 }
        self.props.update(newprops, "new")

        self.failUnlessEqual(self.props.getProperty('x'), 24)
        self.failUnlessEqual(self.props.getPropertySource('x'), 'old')
        self.failUnlessEqual(self.props.getProperty('a'), 1)
        self.failUnlessEqual(self.props.getPropertySource('a'), 'new')

    def testUpdateFromProperties(self):
        self.props.setProperty("x", 24, "old")
        newprops = Properties()
        newprops.setProperty('a', 1, "new")
        newprops.setProperty('b', 2, "new")
        self.props.updateFromProperties(newprops)

        self.failUnlessEqual(self.props.getProperty('x'), 24)
        self.failUnlessEqual(self.props.getPropertySource('x'), 'old')
        self.failUnlessEqual(self.props.getProperty('a'), 1)
        self.failUnlessEqual(self.props.getPropertySource('a'), 'new')

    # render() is pretty well tested by TestWithProperties

class TestWithProperties(unittest.TestCase):
    def setUp(self):
        self.props = Properties()

    def testBasic(self):
        # test basic substitution with WithProperties
        self.props.setProperty("revision", "47", "test")
        command = WithProperties("build-%s.tar.gz", "revision")
        self.failUnlessEqual(self.props.render(command),
                             "build-47.tar.gz")

    def testDict(self):
        # test dict-style substitution with WithProperties
        self.props.setProperty("other", "foo", "test")
        command = WithProperties("build-%(other)s.tar.gz")
        self.failUnlessEqual(self.props.render(command),
                             "build-foo.tar.gz")

    def testDictColonMinus(self):
        # test dict-style substitution with WithProperties
        self.props.setProperty("prop1", "foo", "test")
        command = WithProperties("build-%(prop1:-empty)s-%(prop2:-empty)s.tar.gz")
        self.failUnlessEqual(self.props.render(command),
                             "build-foo-empty.tar.gz")

    def testDictColonPlus(self):
        # test dict-style substitution with WithProperties
        self.props.setProperty("prop1", "foo", "test")
        command = WithProperties("build-%(prop1:+exists)s-%(prop2:+exists)s.tar.gz")
        self.failUnlessEqual(self.props.render(command),
                             "build-exists-.tar.gz")

    def testEmpty(self):
        # None should render as ''
        self.props.setProperty("empty", None, "test")
        command = WithProperties("build-%(empty)s.tar.gz")
        self.failUnlessEqual(self.props.render(command),
                             "build-.tar.gz")

    def testRecursiveList(self):
        self.props.setProperty("x", 10, "test")
        self.props.setProperty("y", 20, "test")
        command = [ WithProperties("%(x)s %(y)s"), "and",
                    WithProperties("%(y)s %(x)s") ]
        self.failUnlessEqual(self.props.render(command),
                             ["10 20", "and", "20 10"])

    def testRecursiveTuple(self):
        self.props.setProperty("x", 10, "test")
        self.props.setProperty("y", 20, "test")
        command = ( WithProperties("%(x)s %(y)s"), "and",
                    WithProperties("%(y)s %(x)s") )
        self.failUnlessEqual(self.props.render(command),
                             ("10 20", "and", "20 10"))

    def testRecursiveDict(self):
        self.props.setProperty("x", 10, "test")
        self.props.setProperty("y", 20, "test")
        command = { WithProperties("%(x)s %(y)s") : 
                    WithProperties("%(y)s %(x)s") }
        self.failUnlessEqual(self.props.render(command),
                             {"10 20" : "20 10"})

class BuildProperties(unittest.TestCase):
    """Test the properties that a build should have."""
    def setUp(self):
        self.builder = FakeBuilder()
        self.builder_status = builder.BuilderStatus("fakebuilder")
        self.builder_status.basedir = "test_properties"
        self.builder_status.nextBuildNumber = 5
        rmdirRecursive(self.builder_status.basedir)
        os.mkdir(self.builder_status.basedir)
        self.build_status = self.builder_status.newBuild()
        req = base.BuildRequest("reason", 
                    SourceStamp(branch="branch2", revision="1234"),
                    'test_builder',
                    properties=Properties(scheduler="fakescheduler"))
        self.build = base.Build([req])
        self.build.build_status = self.build_status
        self.build.setBuilder(self.builder)
        self.build.setupProperties()
        self.build.setupSlaveBuilder(FakeSlaveBuilder())

    def testProperties(self):
        self.failUnlessEqual(self.build.getProperty("scheduler"), "fakescheduler")
        self.failUnlessEqual(self.build.getProperty("branch"), "branch2")
        self.failUnlessEqual(self.build.getProperty("revision"), "1234")
        self.failUnlessEqual(self.build.getProperty("slavename"), "bot12")
        self.failUnlessEqual(self.build.getProperty("buildnumber"), 5)
        self.failUnlessEqual(self.build.getProperty("buildername"), "fakebuilder")
        self.failUnlessEqual(self.build.getProperty("masterprop"), "master")

run_config = """
from buildbot.process import factory
from buildbot.steps.shell import ShellCommand, WithProperties
from buildbot.buildslave import BuildSlave
from buildbot.config import BuilderConfig
s = factory.s

BuildmasterConfig = c = {}
c['slaves'] = [BuildSlave('bot1', 'sekrit', properties={'slprop':'slprop'})]
c['schedulers'] = []
c['slavePortnum'] = 0
c['properties'] = { 'global' : 'global' }

# Note: when run against twisted-1.3.0, this locks up about 5% of the time. I
# suspect that a command with no output that finishes quickly triggers a race
# condition in 1.3.0's process-reaping code. The 'touch' process becomes a
# zombie and the step never completes. To keep this from messing up the unit
# tests too badly, this step runs with a reduced timeout.

f1 = factory.BuildFactory([s(ShellCommand,
                             flunkOnFailure=True,
                             command=['touch',
                                      WithProperties('%s-%s-%s',
                                        'slavename', 'global', 'slprop'),
                                      ],
                             workdir='.',
                             timeout=10,
                             )])

c['builders'] = [
    BuilderConfig(name='full1', slavename='bot1', factory=f1, builddir='bd1'),
]

"""

class Run(RunMixin, unittest.TestCase):
    def testInterpolate(self):
        # run an actual build with a step that interpolates a build property
        d = self.master.loadConfig(run_config)
        d.addCallback(lambda res: self.master.startService())
        d.addCallback(lambda res: self.connectOneSlave("bot1"))
        d.addCallback(lambda res: self.requestBuild("full1"))
        d.addCallback(self.failUnlessBuildSucceeded)
        def _check_touch(res):
            f = os.path.join("slavebase-bot1", "bd1", "bot1-global-slprop")
            self.failUnless(os.path.exists(f))
            return res
        d.addCallback(_check_touch)
        return d

    SetProperty_base_config = """
from buildbot.process import factory
from buildbot.steps.shell import ShellCommand, SetProperty, WithProperties
from buildbot.buildslave import BuildSlave
from buildbot.config import BuilderConfig
s = factory.s

BuildmasterConfig = c = {}
c['slaves'] = [BuildSlave('bot1', 'sekrit')]
c['schedulers'] = []
c['slavePortnum'] = 0

f1 = factory.BuildFactory([
##STEPS##
])

c['builders'] = [
    BuilderConfig(name='full1', slavename='bot1', factory=f1, builddir='bd1'),
]
"""

    SetPropertySimple_config = SetProperty_base_config.replace("##STEPS##", """
        SetProperty(property='foo', command="echo foo"),
        SetProperty(property=WithProperties('wp'), command="echo wp"),
        SetProperty(property='bar', command="echo bar", strip=False),
    """)

    def testSetPropertySimple(self):
        d = self.master.loadConfig(self.SetPropertySimple_config)
        d.addCallback(lambda res: self.master.startService())
        d.addCallback(lambda res: self.connectOneSlave("bot1"))
        d.addCallback(lambda res: self.requestBuild("full1"))
        d.addCallback(self.failUnlessBuildSucceeded)
        def _check_props(bs):
            self.failUnlessEqual(bs.getProperty("foo"), "foo")
            self.failUnlessEqual(bs.getProperty("wp"), "wp")
            # (will this fail on some platforms, due to newline differences?)
            self.failUnlessEqual(bs.getProperty("bar"), "bar\n")
            return bs
        d.addCallback(_check_props)
        return d

    SetPropertyExtractFn_config = SetProperty_base_config.replace("##STEPS##", """
        SetProperty(
            extract_fn=lambda rc,stdout,stderr : {
                'foo' : stdout.strip(),
                'bar' : stderr.strip() },
            command="echo foo; echo bar >&2"),
    """)

    def testSetPropertyExtractFn(self):
        d = self.master.loadConfig(self.SetPropertyExtractFn_config)
        d.addCallback(lambda res: self.master.startService())
        d.addCallback(lambda res: self.connectOneSlave("bot1"))
        d.addCallback(lambda res: self.requestBuild("full1"))
        d.addCallback(self.failUnlessBuildSucceeded)
        def _check_props(bs):
            self.failUnlessEqual(bs.getProperty("foo"), "foo")
            self.failUnlessEqual(bs.getProperty("bar"), "bar")
            return bs
        d.addCallback(_check_props)
        return d

# we test got_revision in test_vc
