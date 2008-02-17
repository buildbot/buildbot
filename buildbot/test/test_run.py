# -*- test-case-name: buildbot.test.test_run -*-

from twisted.trial import unittest
from twisted.internet import reactor, defer
import os

from buildbot import master, interfaces
from buildbot.sourcestamp import SourceStamp
from buildbot.changes import changes
from buildbot.status import builder
from buildbot.process.base import BuildRequest

from buildbot.test.runutils import RunMixin, TestFlagMixin, rmtree

config_base = """
from buildbot.process import factory
from buildbot.steps import dummy
from buildbot.buildslave import BuildSlave
s = factory.s

f1 = factory.QuickBuildFactory('fakerep', 'cvsmodule', configure=None)

f2 = factory.BuildFactory([
    s(dummy.Dummy, timeout=1),
    s(dummy.RemoteDummy, timeout=2),
    ])

BuildmasterConfig = c = {}
c['slaves'] = [BuildSlave('bot1', 'sekrit')]
c['schedulers'] = []
c['builders'] = []
c['builders'].append({'name':'quick', 'slavename':'bot1',
                      'builddir': 'quickdir', 'factory': f1})
c['slavePortnum'] = 0
"""

config_run = config_base + """
from buildbot.scheduler import Scheduler
c['schedulers'] = [Scheduler('quick', None, 120, ['quick'])]
"""

config_can_build = config_base + """
from buildbot.buildslave import BuildSlave
c['slaves'] = [ BuildSlave('bot1', 'sekrit') ]

from buildbot.scheduler import Scheduler
c['schedulers'] = [Scheduler('dummy', None, 0.1, ['dummy'])]

c['builders'] = [{'name': 'dummy', 'slavename': 'bot1',
                  'builddir': 'dummy1', 'factory': f2}]
"""

config_cant_build = config_can_build + """
class MyBuildSlave(BuildSlave):
    def canStartBuild(self): return False
c['slaves'] = [ MyBuildSlave('bot1', 'sekrit') ]
"""

config_concurrency = config_base + """
from buildbot.buildslave import BuildSlave
c['slaves'] = [ BuildSlave('bot1', 'sekrit', max_builds=1) ]

from buildbot.scheduler import Scheduler
c['schedulers'] = [Scheduler('dummy', None, 0.1, ['dummy', 'dummy2'])]

c['builders'].append({'name': 'dummy', 'slavename': 'bot1',
                      'builddir': 'dummy', 'factory': f2})
c['builders'].append({'name': 'dummy2', 'slavename': 'bot1',
                      'builddir': 'dummy2', 'factory': f2})
"""

config_2 = config_base + """
c['builders'] = [{'name': 'dummy', 'slavename': 'bot1',
                  'builddir': 'dummy1', 'factory': f2},
                 {'name': 'testdummy', 'slavename': 'bot1',
                  'builddir': 'dummy2', 'factory': f2, 'category': 'test'}]
"""

config_3 = config_2 + """
c['builders'].append({'name': 'adummy', 'slavename': 'bot1',
                      'builddir': 'adummy3', 'factory': f2})
c['builders'].append({'name': 'bdummy', 'slavename': 'bot1',
                      'builddir': 'adummy4', 'factory': f2,
                      'category': 'test'})
"""

config_4 = config_base + """
c['builders'] = [{'name': 'dummy', 'slavename': 'bot1',
                  'builddir': 'dummy', 'factory': f2}]
"""

config_4_newbasedir = config_4 + """
c['builders'] = [{'name': 'dummy', 'slavename': 'bot1',
                  'builddir': 'dummy2', 'factory': f2}]
"""

config_4_newbuilder = config_4_newbasedir + """
c['builders'].append({'name': 'dummy2', 'slavename': 'bot1',
                      'builddir': 'dummy23', 'factory': f2})
"""

class Run(unittest.TestCase):
    def rmtree(self, d):
        rmtree(d)

    def testMaster(self):
        self.rmtree("basedir")
        os.mkdir("basedir")
        m = master.BuildMaster("basedir")
        m.loadConfig(config_run)
        m.readConfig = True
        m.startService()
        cm = m.change_svc
        c = changes.Change("bob", ["Makefile", "foo/bar.c"], "changed stuff")
        cm.addChange(c)
        # verify that the Scheduler is now waiting
        s = m.allSchedulers()[0]
        self.failUnless(s.timer)
        # halting the service will also stop the timer
        d = defer.maybeDeferred(m.stopService)
        return d

class CanStartBuild(RunMixin, unittest.TestCase):
    def rmtree(self, d):
        rmtree(d)

    def testCanStartBuild(self):
        return self.do_test(config_can_build, True)

    def testCantStartBuild(self):
        return self.do_test(config_cant_build, False)

    def do_test(self, config, builder_should_run):
        self.master.loadConfig(config)
        self.master.readConfig = True
        self.master.startService()
        d = self.connectSlave()

        # send a change
        cm = self.master.change_svc
        c = changes.Change("bob", ["Makefile", "foo/bar.c"], "changed stuff")
        cm.addChange(c)

        d.addCallback(self._do_test1, builder_should_run)

        return d

    def _do_test1(self, res, builder_should_run):
        # delay a little bit. Note that relying upon timers is a bit fragile,
        # in this case we're hoping that our 0.5 second timer will land us
        # somewhere in the middle of the [0.1s, 3.1s] window (after the 0.1
        # second Scheduler fires, then during the 3-second build), so that
        # when we sample BuildSlave.state, we'll see BUILDING (or IDLE if the
        # slave was told to be unavailable). On a heavily loaded system, our
        # 0.5 second timer might not actually fire until after the build has
        # completed. In the long run, it would be good to change this test to
        # pass under those circumstances too.
        d = defer.Deferred()
        reactor.callLater(.5, d.callback, builder_should_run)
        d.addCallback(self._do_test2)
        return d

    def _do_test2(self, builder_should_run):
        b = self.master.botmaster.builders['dummy']
        self.failUnless(len(b.slaves) == 1)

        bs = b.slaves[0]
        from buildbot.process.builder import IDLE, BUILDING
        if builder_should_run:
            self.failUnlessEqual(bs.state, BUILDING)
        else:
            self.failUnlessEqual(bs.state, IDLE)


class ConcurrencyLimit(RunMixin, unittest.TestCase):

    def testConcurrencyLimit(self):
        d = self.master.loadConfig(config_concurrency)
        d.addCallback(lambda res: self.master.startService())
        d.addCallback(lambda res: self.connectSlave())

        def _send(res):
            # send a change. This will trigger both builders at the same
            # time, but since they share a slave, the max_builds=1 setting
            # will insure that only one of the two builds gets to run.
            cm = self.master.change_svc
            c = changes.Change("bob", ["Makefile", "foo/bar.c"],
                               "changed stuff")
            cm.addChange(c)
        d.addCallback(_send)

        def _delay(res):
            d1 = defer.Deferred()
            reactor.callLater(1, d1.callback, None)
            # this test depends upon this 1s delay landing us in the middle
            # of one of the builds.
            return d1
        d.addCallback(_delay)

        def _check(res):
            builders = [ self.master.botmaster.builders[bn]
                         for bn in ('dummy', 'dummy2') ]
            for builder in builders:
                self.failUnless(len(builder.slaves) == 1)

            from buildbot.process.builder import BUILDING
            building_bs = [ builder
                            for builder in builders
                            if builder.slaves[0].state == BUILDING ]
            # assert that only one build is running right now. If the
            # max_builds= weren't in effect, this would be 2.
            self.failUnlessEqual(len(building_bs), 1)
        d.addCallback(_check)

        return d


class Ping(RunMixin, unittest.TestCase):
    def testPing(self):
        self.master.loadConfig(config_2)
        self.master.readConfig = True
        self.master.startService()

        d = self.connectSlave()
        d.addCallback(self._testPing_1)
        return d

    def _testPing_1(self, res):
        d = interfaces.IControl(self.master).getBuilder("dummy").ping(1)
        d.addCallback(self._testPing_2)
        return d

    def _testPing_2(self, res):
        pass

class BuilderNames(unittest.TestCase):

    def testGetBuilderNames(self):
        os.mkdir("bnames")
        m = master.BuildMaster("bnames")
        s = m.getStatus()

        m.loadConfig(config_3)
        m.readConfig = True

        self.failUnlessEqual(s.getBuilderNames(),
                             ["dummy", "testdummy", "adummy", "bdummy"])
        self.failUnlessEqual(s.getBuilderNames(categories=['test']),
                             ["testdummy", "bdummy"])

class Disconnect(RunMixin, unittest.TestCase):

    def setUp(self):
        RunMixin.setUp(self)
        
        # verify that disconnecting the slave during a build properly
        # terminates the build
        m = self.master
        s = self.status
        c = self.control

        m.loadConfig(config_2)
        m.readConfig = True
        m.startService()

        self.failUnlessEqual(s.getBuilderNames(), ["dummy", "testdummy"])
        self.s1 = s1 = s.getBuilder("dummy")
        self.failUnlessEqual(s1.getName(), "dummy")
        self.failUnlessEqual(s1.getState(), ("offline", []))
        self.failUnlessEqual(s1.getCurrentBuilds(), [])
        self.failUnlessEqual(s1.getLastFinishedBuild(), None)
        self.failUnlessEqual(s1.getBuild(-1), None)

        d = self.connectSlave()
        d.addCallback(self._disconnectSetup_1)
        return d

    def _disconnectSetup_1(self, res):
        self.failUnlessEqual(self.s1.getState(), ("idle", []))


    def verifyDisconnect(self, bs):
        self.failUnless(bs.isFinished())

        step1 = bs.getSteps()[0]
        self.failUnlessEqual(step1.getText(), ["delay", "interrupted"])
        self.failUnlessEqual(step1.getResults()[0], builder.FAILURE)

        self.failUnlessEqual(bs.getResults(), builder.FAILURE)

    def verifyDisconnect2(self, bs):
        self.failUnless(bs.isFinished())

        step1 = bs.getSteps()[1]
        self.failUnlessEqual(step1.getText(), ["remote", "delay", "2 secs",
                                               "failed", "slave", "lost"])
        self.failUnlessEqual(step1.getResults()[0], builder.FAILURE)

        self.failUnlessEqual(bs.getResults(), builder.FAILURE)

    def submitBuild(self):
        ss = SourceStamp()
        br = BuildRequest("forced build", ss, "dummy")
        self.control.getBuilder("dummy").requestBuild(br)
        d = defer.Deferred()
        def _started(bc):
            br.unsubscribe(_started)
            d.callback(bc)
        br.subscribe(_started)
        return d

    def testIdle2(self):
        # now suppose the slave goes missing
        self.disappearSlave(allowReconnect=False)

        # forcing a build will work: the build detect that the slave is no
        # longer available and will be re-queued. Wait 5 seconds, then check
        # to make sure the build is still in the 'waiting for a slave' queue.
        self.control.getBuilder("dummy").original.START_BUILD_TIMEOUT = 1
        req = BuildRequest("forced build", SourceStamp())
        self.failUnlessEqual(req.startCount, 0)
        self.control.getBuilder("dummy").requestBuild(req)
        # this should ping the slave, which doesn't respond, and then give up
        # after a second. The BuildRequest will be re-queued, and its
        # .startCount will be incremented.
        d = defer.Deferred()
        d.addCallback(self._testIdle2_1, req)
        reactor.callLater(3, d.callback, None)
        return d
    testIdle2.timeout = 5

    def _testIdle2_1(self, res, req):
        self.failUnlessEqual(req.startCount, 1)
        cancelled = req.cancel()
        self.failUnless(cancelled)


    def testBuild1(self):
        # this next sequence is timing-dependent. The dummy build takes at
        # least 3 seconds to complete, and this batch of commands must
        # complete within that time.
        #
        d = self.submitBuild()
        d.addCallback(self._testBuild1_1)
        return d

    def _testBuild1_1(self, bc):
        bs = bc.getStatus()
        # now kill the slave before it gets to start the first step
        d = self.shutdownAllSlaves() # dies before it gets started
        d.addCallback(self._testBuild1_2, bs)
        return d  # TODO: this used to have a 5-second timeout

    def _testBuild1_2(self, res, bs):
        # now examine the just-stopped build and make sure it is really
        # stopped. This is checking for bugs in which the slave-detach gets
        # missed or causes an exception which prevents the build from being
        # marked as "finished due to an error".
        d = bs.waitUntilFinished()
        d2 = self.master.botmaster.waitUntilBuilderDetached("dummy")
        dl = defer.DeferredList([d, d2])
        dl.addCallback(self._testBuild1_3, bs)
        return dl # TODO: this had a 5-second timeout too

    def _testBuild1_3(self, res, bs):
        self.failUnlessEqual(self.s1.getState()[0], "offline")
        self.verifyDisconnect(bs)


    def testBuild2(self):
        # this next sequence is timing-dependent
        d = self.submitBuild()
        d.addCallback(self._testBuild1_1)
        return d
    testBuild2.timeout = 30

    def _testBuild1_1(self, bc):
        bs = bc.getStatus()
        # shutdown the slave while it's running the first step
        reactor.callLater(0.5, self.shutdownAllSlaves)

        d = bs.waitUntilFinished()
        d.addCallback(self._testBuild2_2, bs)
        return d

    def _testBuild2_2(self, res, bs):
        # we hit here when the build has finished. The builder is still being
        # torn down, however, so spin for another second to allow the
        # callLater(0) in Builder.detached to fire.
        d = defer.Deferred()
        reactor.callLater(1, d.callback, None)
        d.addCallback(self._testBuild2_3, bs)
        return d

    def _testBuild2_3(self, res, bs):
        self.failUnlessEqual(self.s1.getState()[0], "offline")
        self.verifyDisconnect(bs)


    def testBuild3(self):
        # this next sequence is timing-dependent
        d = self.submitBuild()
        d.addCallback(self._testBuild3_1)
        return d
    testBuild3.timeout = 30

    def _testBuild3_1(self, bc):
        bs = bc.getStatus()
        # kill the slave while it's running the first step
        reactor.callLater(0.5, self.killSlave)
        d = bs.waitUntilFinished()
        d.addCallback(self._testBuild3_2, bs)
        return d

    def _testBuild3_2(self, res, bs):
        # the builder is still being torn down, so give it another second
        d = defer.Deferred()
        reactor.callLater(1, d.callback, None)
        d.addCallback(self._testBuild3_3, bs)
        return d

    def _testBuild3_3(self, res, bs):
        self.failUnlessEqual(self.s1.getState()[0], "offline")
        self.verifyDisconnect(bs)


    def testBuild4(self):
        # this next sequence is timing-dependent
        d = self.submitBuild()
        d.addCallback(self._testBuild4_1)
        return d
    testBuild4.timeout = 30

    def _testBuild4_1(self, bc):
        bs = bc.getStatus()
        # kill the slave while it's running the second (remote) step
        reactor.callLater(1.5, self.killSlave)
        d = bs.waitUntilFinished()
        d.addCallback(self._testBuild4_2, bs)
        return d

    def _testBuild4_2(self, res, bs):
        # at this point, the slave is in the process of being removed, so it
        # could either be 'idle' or 'offline'. I think there is a
        # reactor.callLater(0) standing between here and the offline state.
        #reactor.iterate() # TODO: remove the need for this

        self.failUnlessEqual(self.s1.getState()[0], "offline")
        self.verifyDisconnect2(bs)


    def testInterrupt(self):
        # this next sequence is timing-dependent
        d = self.submitBuild()
        d.addCallback(self._testInterrupt_1)
        return d
    testInterrupt.timeout = 30

    def _testInterrupt_1(self, bc):
        bs = bc.getStatus()
        # halt the build while it's running the first step
        reactor.callLater(0.5, bc.stopBuild, "bang go splat")
        d = bs.waitUntilFinished()
        d.addCallback(self._testInterrupt_2, bs)
        return d

    def _testInterrupt_2(self, res, bs):
        self.verifyDisconnect(bs)


    def testDisappear(self):
        bc = self.control.getBuilder("dummy")

        # ping should succeed
        d = bc.ping(1)
        d.addCallback(self._testDisappear_1, bc)
        return d

    def _testDisappear_1(self, res, bc):
        self.failUnlessEqual(res, True)

        # now, before any build is run, make the slave disappear
        self.disappearSlave(allowReconnect=False)

        # at this point, a ping to the slave should timeout
        d = bc.ping(1)
        d.addCallback(self. _testDisappear_2)
        return d
    def _testDisappear_2(self, res):
        self.failUnlessEqual(res, False)

    def testDuplicate(self):
        bc = self.control.getBuilder("dummy")
        bs = self.status.getBuilder("dummy")
        ss = bs.getSlaves()[0]

        self.failUnless(ss.isConnected())
        self.failUnlessEqual(ss.getAdmin(), "one")

        # now, before any build is run, make the first slave disappear
        self.disappearSlave(allowReconnect=False)

        d = self.master.botmaster.waitUntilBuilderDetached("dummy")
        # now let the new slave take over
        self.connectSlave2()
        d.addCallback(self._testDuplicate_1, ss)
        return d
    testDuplicate.timeout = 5

    def _testDuplicate_1(self, res, ss):
        d = self.master.botmaster.waitUntilBuilderAttached("dummy")
        d.addCallback(self._testDuplicate_2, ss)
        return d

    def _testDuplicate_2(self, res, ss):
        self.failUnless(ss.isConnected())
        self.failUnlessEqual(ss.getAdmin(), "two")


class Disconnect2(RunMixin, unittest.TestCase):

    def setUp(self):
        RunMixin.setUp(self)
        # verify that disconnecting the slave during a build properly
        # terminates the build
        m = self.master
        s = self.status
        c = self.control

        m.loadConfig(config_2)
        m.readConfig = True
        m.startService()

        self.failUnlessEqual(s.getBuilderNames(), ["dummy", "testdummy"])
        self.s1 = s1 = s.getBuilder("dummy")
        self.failUnlessEqual(s1.getName(), "dummy")
        self.failUnlessEqual(s1.getState(), ("offline", []))
        self.failUnlessEqual(s1.getCurrentBuilds(), [])
        self.failUnlessEqual(s1.getLastFinishedBuild(), None)
        self.failUnlessEqual(s1.getBuild(-1), None)

        d = self.connectSlaveFastTimeout()
        d.addCallback(self._setup_disconnect2_1)
        return d

    def _setup_disconnect2_1(self, res):
        self.failUnlessEqual(self.s1.getState(), ("idle", []))


    def testSlaveTimeout(self):
        # now suppose the slave goes missing. We want to find out when it
        # creates a new Broker, so we reach inside and mark it with the
        # well-known sigil of impending messy death.
        bd = self.slaves['bot1'].getServiceNamed("bot").builders["dummy"]
        broker = bd.remote.broker
        broker.redshirt = 1

        # make sure the keepalives will keep the connection up
        d = defer.Deferred()
        reactor.callLater(5, d.callback, None)
        d.addCallback(self._testSlaveTimeout_1)
        return d
    testSlaveTimeout.timeout = 20

    def _testSlaveTimeout_1(self, res):
        bd = self.slaves['bot1'].getServiceNamed("bot").builders["dummy"]
        if not bd.remote or not hasattr(bd.remote.broker, "redshirt"):
            self.fail("slave disconnected when it shouldn't have")

        d = self.master.botmaster.waitUntilBuilderDetached("dummy")
        # whoops! how careless of me.
        self.disappearSlave(allowReconnect=True)
        # the slave will realize the connection is lost within 2 seconds, and
        # reconnect.
        d.addCallback(self._testSlaveTimeout_2)
        return d

    def _testSlaveTimeout_2(self, res):
        # the ReconnectingPBClientFactory will attempt a reconnect in two
        # seconds.
        d = self.master.botmaster.waitUntilBuilderAttached("dummy")
        d.addCallback(self._testSlaveTimeout_3)
        return d

    def _testSlaveTimeout_3(self, res):
        # make sure it is a new connection (i.e. a new Broker)
        bd = self.slaves['bot1'].getServiceNamed("bot").builders["dummy"]
        self.failUnless(bd.remote, "hey, slave isn't really connected")
        self.failIf(hasattr(bd.remote.broker, "redshirt"),
                    "hey, slave's Broker is still marked for death")


class Basedir(RunMixin, unittest.TestCase):
    def testChangeBuilddir(self):
        m = self.master
        m.loadConfig(config_4)
        m.readConfig = True
        m.startService()
        
        d = self.connectSlave()
        d.addCallback(self._testChangeBuilddir_1)
        return d

    def _testChangeBuilddir_1(self, res):
        self.bot = bot = self.slaves['bot1'].bot
        self.builder = builder = bot.builders.get("dummy")
        self.failUnless(builder)
        self.failUnlessEqual(builder.builddir, "dummy")
        self.failUnlessEqual(builder.basedir,
                             os.path.join("slavebase-bot1", "dummy"))

        d = self.master.loadConfig(config_4_newbasedir)
        d.addCallback(self._testChangeBuilddir_2)
        return d

    def _testChangeBuilddir_2(self, res):
        bot = self.bot
        # this does NOT cause the builder to be replaced
        builder = bot.builders.get("dummy")
        self.failUnless(builder)
        self.failUnlessIdentical(self.builder, builder)
        # the basedir should be updated
        self.failUnlessEqual(builder.builddir, "dummy2")
        self.failUnlessEqual(builder.basedir,
                             os.path.join("slavebase-bot1", "dummy2"))

        # add a new builder, which causes the basedir list to be reloaded
        d = self.master.loadConfig(config_4_newbuilder)
        return d

class Triggers(RunMixin, TestFlagMixin, unittest.TestCase):
    config_trigger = config_base + """
from buildbot.scheduler import Triggerable, Scheduler
from buildbot.steps.trigger import Trigger
from buildbot.steps.dummy import Dummy
from buildbot.test.runutils import SetTestFlagStep
c['schedulers'] = [
    Scheduler('triggerer', None, 0.1, ['triggerer']),
    Triggerable('triggeree', ['triggeree'])
]
triggerer = factory.BuildFactory([
    s(SetTestFlagStep, flagname='triggerer_started'),
    s(Trigger, flunkOnFailure=True, @ARGS@),
    s(SetTestFlagStep, flagname='triggerer_finished'),
    ])
triggeree = factory.BuildFactory([
    s(SetTestFlagStep, flagname='triggeree_started'),
    s(@DUMMYCLASS@),
    s(SetTestFlagStep, flagname='triggeree_finished'),
    ])
c['builders'] = [{'name': 'triggerer', 'slavename': 'bot1',
                  'builddir': 'triggerer', 'factory': triggerer},
                 {'name': 'triggeree', 'slavename': 'bot1',
                  'builddir': 'triggeree', 'factory': triggeree}]
"""

    def mkConfig(self, args, dummyclass="Dummy"):
        return self.config_trigger.replace("@ARGS@", args).replace("@DUMMYCLASS@", dummyclass)

    def setupTest(self, args, dummyclass, checkFn):
        self.clearFlags()
        m = self.master
        m.loadConfig(self.mkConfig(args, dummyclass))
        m.readConfig = True
        m.startService()

        c = changes.Change("bob", ["Makefile", "foo/bar.c"], "changed stuff")
        m.change_svc.addChange(c)

        d = self.connectSlave(builders=['triggerer', 'triggeree'])
        d.addCallback(self.startTimer, 0.5, checkFn)
        return d

    def startTimer(self, res, time, next_fn):
        d = defer.Deferred()
        reactor.callLater(time, d.callback, None)
        d.addCallback(next_fn)
        return d

    def testTriggerBuild(self):
        return self.setupTest("schedulers=['triggeree']",
                "Dummy",
                self._checkTriggerBuild)

    def _checkTriggerBuild(self, res):
        self.failIfFlagNotSet('triggerer_started')
        self.failIfFlagNotSet('triggeree_started')
        self.failIfFlagSet('triggeree_finished')
        self.failIfFlagNotSet('triggerer_finished')

    def testTriggerBuildWait(self):
        return self.setupTest("schedulers=['triggeree'], waitForFinish=1",
                "Dummy",
                self._checkTriggerBuildWait)

    def _checkTriggerBuildWait(self, res):
        self.failIfFlagNotSet('triggerer_started')
        self.failIfFlagNotSet('triggeree_started')
        self.failIfFlagSet('triggeree_finished')
        self.failIfFlagSet('triggerer_finished')

config_test_flag = config_base + """
from buildbot.scheduler import Scheduler
c['schedulers'] = [Scheduler('quick', None, 0.1, ['dummy'])]

from buildbot.test.runutils import SetTestFlagStep
f3 = factory.BuildFactory([
    s(SetTestFlagStep, flagname='foo', value='bar'),
    ])

c['builders'] = [{'name': 'dummy', 'slavename': 'bot1',
                  'builddir': 'dummy', 'factory': f3}]
"""

class TestFlag(RunMixin, TestFlagMixin, unittest.TestCase):
    """Test for the TestFlag functionality in runutils"""
    def testTestFlag(self):
        m = self.master
        m.loadConfig(config_test_flag)
        m.readConfig = True
        m.startService()

        c = changes.Change("bob", ["Makefile", "foo/bar.c"], "changed stuff")
        m.change_svc.addChange(c)

        d = self.connectSlave()
        d.addCallback(self._testTestFlag_1)
        return d

    def _testTestFlag_1(self, res):
        d = defer.Deferred()
        reactor.callLater(0.5, d.callback, None)
        d.addCallback(self._testTestFlag_2)
        return d

    def _testTestFlag_2(self, res):
        self.failUnlessEqual(self.getFlag('foo'), 'bar')

# TODO: test everything, from Change submission to Scheduler to Build to
# Status. Use all the status types. Specifically I want to catch recurrences
# of the bug where I forgot to make Waterfall inherit from StatusReceiver
# such that buildSetSubmitted failed.

