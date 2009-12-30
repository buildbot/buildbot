# -*- test-case-name: buildbot.test.test_slaves -*-

# Portions copyright Canonical Ltd. 2009

from twisted.trial import unittest
from twisted.internet import defer, reactor
from twisted.python import log, runtime, failure

from buildbot.buildslave import AbstractLatentBuildSlave
from buildbot.test.runutils import RunMixin
from buildbot.sourcestamp import SourceStamp
from buildbot.process.base import BuildRequest
from buildbot.status.builder import SUCCESS
from buildbot.status import mail
from buildbot.slave import bot

config_1 = """
from buildbot.process import factory
from buildbot.steps import dummy
from buildbot.buildslave import BuildSlave
from buildbot.config import BuilderConfig
s = factory.s

BuildmasterConfig = c = {}
c['slaves'] = [BuildSlave('bot1', 'sekrit'), BuildSlave('bot2', 'sekrit'),
               BuildSlave('bot3', 'sekrit')]
c['schedulers'] = []
c['slavePortnum'] = 0
c['schedulers'] = []

f1 = factory.BuildFactory([s(dummy.RemoteDummy, timeout=1)])
f2 = factory.BuildFactory([s(dummy.RemoteDummy, timeout=2)])
f3 = factory.BuildFactory([s(dummy.RemoteDummy, timeout=3)])
f4 = factory.BuildFactory([s(dummy.RemoteDummy, timeout=5)])

c['builders'] = [
    BuilderConfig(name='b1', slavenames=['bot1', 'bot2', 'bot3'], factory=f1),
]
"""

config_2 = config_1 + """

c['builders'] = [
    BuilderConfig(name='b1', slavenames=['bot1', 'bot2', 'bot3'], factory=f2),
]

"""

config_busyness = config_1 + """
c['builders'] = [
    BuilderConfig(name='b1', slavenames=['bot1', ], factory=f3),
    BuilderConfig(name='b2', slavenames=['bot1', ], factory=f4),
]
"""

class Slave(RunMixin, unittest.TestCase):

    def setUp(self):
        RunMixin.setUp(self)
        self.master.loadConfig(config_1)
        self.master.startService()
        d = self.connectSlave(["b1"])
        d.addCallback(lambda res: self.connectSlave(["b1"], "bot2"))
        return d

    def doBuild(self, buildername):
        br = BuildRequest("forced", SourceStamp(), 'test_builder')
        d = br.waitUntilFinished()
        self.control.getBuilder(buildername).requestBuild(br)
        return d

    def testSequence(self):
        # make sure both slaves appear in the list.
        attached_slaves = [c for c in self.master.botmaster.slaves.values()
                           if c.slave]
        self.failUnlessEqual(len(attached_slaves), 2)
        b = self.master.botmaster.builders["b1"]
        self.failUnlessEqual(len(b.slaves), 2)

        # since the current scheduling algorithm is simple and does not
        # rotate or attempt any sort of load-balancing, two builds in
        # sequence should both use the first slave. This may change later if
        # we move to a more sophisticated scheme.
        b.CHOOSE_SLAVES_RANDOMLY = False

        d = self.doBuild("b1")
        d.addCallback(self._testSequence_1)
        return d
    def _testSequence_1(self, res):
        self.failUnlessEqual(res.getResults(), SUCCESS)
        self.failUnlessEqual(res.getSlavename(), "bot1")

        d = self.doBuild("b1")
        d.addCallback(self._testSequence_2)
        return d
    def _testSequence_2(self, res):
        self.failUnlessEqual(res.getSlavename(), "bot1")


    def testSimultaneous(self):
        # make sure we can actually run two builds at the same time
        d1 = self.doBuild("b1")
        d2 = self.doBuild("b1")
        d1.addCallback(self._testSimultaneous_1, d2)
        return d1
    def _testSimultaneous_1(self, res, d2):
        self.failUnlessEqual(res.getResults(), SUCCESS)
        b1_slavename = res.getSlavename()
        d2.addCallback(self._testSimultaneous_2, b1_slavename)
        return d2
    def _testSimultaneous_2(self, res, b1_slavename):
        self.failUnlessEqual(res.getResults(), SUCCESS)
        b2_slavename = res.getSlavename()
        # make sure the two builds were run by different slaves
        slavenames = [b1_slavename, b2_slavename]
        slavenames.sort()
        self.failUnlessEqual(slavenames, ["bot1", "bot2"])

    def testFallback1(self):
        # detach the first slave, verify that a build is run using the second
        # slave instead
        d = self.shutdownSlave("bot1", "b1")
        d.addCallback(self._testFallback1_1)
        return d
    def _testFallback1_1(self, res):
        attached_slaves = [c for c in self.master.botmaster.slaves.values()
                           if c.slave]
        self.failUnlessEqual(len(attached_slaves), 1)
        self.failUnlessEqual(len(self.master.botmaster.builders["b1"].slaves),
                             1)
        d = self.doBuild("b1")
        d.addCallback(self._testFallback1_2)
        return d
    def _testFallback1_2(self, res):
        self.failUnlessEqual(res.getResults(), SUCCESS)
        self.failUnlessEqual(res.getSlavename(), "bot2")

    def testFallback2(self):
        # Disable the first slave, so that a slaveping will timeout. Then
        # start a build, and verify that the non-failing (second) one is
        # claimed for the build, and that the failing one is removed from the
        # list.

        b1 = self.master.botmaster.builders["b1"]
        # reduce the ping time so we'll failover faster
        assert b1.CHOOSE_SLAVES_RANDOMLY
        b1.CHOOSE_SLAVES_RANDOMLY = False
        self.disappearSlave("bot1", "b1", allowReconnect=False)
        d = self.doBuild("b1")
        self.killSlave("bot1", "b1")
        d.addCallback(self._testFallback2_1)
        return d
    def _testFallback2_1(self, res):
        self.failUnlessEqual(res.getResults(), SUCCESS)
        self.failUnlessEqual(res.getSlavename(), "bot2")
        b1slaves = self.master.botmaster.builders["b1"].slaves
        self.failUnlessEqual(len(b1slaves), 1, "whoops: %s" % (b1slaves,))
        self.failUnlessEqual(b1slaves[0].slave.slavename, "bot2")


    def notFinished(self, brs):
        # utility method
        builds = brs.getBuilds()
        self.failIf(len(builds) > 1)
        if builds:
            self.failIf(builds[0].isFinished())

    def testDontClaimPingingSlave(self):
        # have two slaves connect for the same builder. Do something to the
        # first one so that slavepings are delayed (but do not fail
        # outright).
        timers = []
        self.slaves['bot1'].debugOpts["stallPings"] = (10, timers)
        br = BuildRequest("forced", SourceStamp(), 'test_builder')
        d1 = br.waitUntilFinished()
        self.master.botmaster.builders["b1"].CHOOSE_SLAVES_RANDOMLY = False
        self.control.getBuilder("b1").requestBuild(br)
        s1 = br.status # this is a BuildRequestStatus
        # give it a chance to start pinging
        d2 = defer.Deferred()
        d2.addCallback(self._testDontClaimPingingSlave_1, d1, s1, timers)
        reactor.callLater(1, d2.callback, None)
        return d2
    def _testDontClaimPingingSlave_1(self, res, d1, s1, timers):
        # now the first build is running (waiting on the ping), so start the
        # second build. This should claim the second slave, not the first,
        # because the first is busy doing the ping.
        self.notFinished(s1)
        d3 = self.doBuild("b1")
        d3.addCallback(self._testDontClaimPingingSlave_2, d1, s1, timers)
        return d3
    def _testDontClaimPingingSlave_2(self, res, d1, s1, timers):
        self.failUnlessEqual(res.getSlavename(), "bot2")
        self.notFinished(s1)
        # now let the ping complete
        self.failUnlessEqual(len(timers), 1)
        timers[0].reset(0)
        d1.addCallback(self._testDontClaimPingingSlave_3)
        return d1
    def _testDontClaimPingingSlave_3(self, res):
        self.failUnlessEqual(res.getSlavename(), "bot1")

class FakeLatentBuildSlave(AbstractLatentBuildSlave):

    testcase = None
    stop_wait = None
    start_message = None
    stopped = testing_substantiation_timeout = False

    def start_instance(self):
        # responsible for starting instance that will try to connect with
        # this master
        # simulate having to do some work.
        d = defer.Deferred()
        if not self.testing_substantiation_timeout:
            reactor.callLater(0, self._start_instance, d)
        return d

    def _start_instance(self, d):
        self.testcase.connectOneSlave(self.slavename)
        d.callback(self.start_message)

    def stop_instance(self, fast=False):
        # responsible for shutting down instance
        # we're going to emulate dropping off the net.

        # simulate this by replacing the slave Broker's .dataReceived method
        # with one that just throws away all data.
        self.fast_stop_request = fast
        if self.slavename not in self.testcase.slaves:
            assert self.testing_substantiation_timeout
            self.stopped = True
            return defer.succeed(None)
        d = defer.Deferred()
        if self.stop_wait is None:
            self._stop_instance(d)
        else:
            reactor.callLater(self.stop_wait, self._stop_instance, d)
        return d

    def _stop_instance(self, d):
        try:
            s = self.testcase.slaves.pop(self.slavename)
        except KeyError:
            pass
        else:
            def discard(data):
                pass
            bot = s.getServiceNamed("bot")
            for buildername in self.slavebuilders:
                remote = bot.builders[buildername].remote
                if remote is None:
                    continue
                broker = remote.broker
                broker.dataReceived = discard # seal its ears
                broker.transport.write = discard # and take away its voice
            # also discourage it from reconnecting once the connection goes away
            s.bf.continueTrying = False
            # stop the service for cleanliness
            s.stopService()
        d.callback(None)

latent_config = """
from buildbot.process import factory
from buildbot.steps import dummy
from buildbot.buildslave import BuildSlave
from buildbot.test.test_slaves import FakeLatentBuildSlave
from buildbot.config import BuilderConfig
s = factory.s

BuildmasterConfig = c = {}
c['slaves'] = [FakeLatentBuildSlave('bot1', 'sekrit',
                                   ),
               FakeLatentBuildSlave('bot2', 'sekrit',
                                   ),
               BuildSlave('bot3', 'sekrit')]
c['schedulers'] = []
c['slavePortnum'] = 0
c['schedulers'] = []

f1 = factory.BuildFactory([s(dummy.RemoteDummy, timeout=1)])
f2 = factory.BuildFactory([s(dummy.RemoteDummy, timeout=2)])
f3 = factory.BuildFactory([s(dummy.RemoteDummy, timeout=3)])
f4 = factory.BuildFactory([s(dummy.RemoteDummy, timeout=5)])

c['builders'] = [
    BuilderConfig(name='b1', slavenames=['bot1', 'bot2', 'bot3'], factory=f1),
]
"""


class LatentSlave(RunMixin, unittest.TestCase):

    def setUp(self):
        # debugging
        #import twisted.internet.base
        #twisted.internet.base.DelayedCall.debug = True
        # debugging
        RunMixin.setUp(self)
        self.master.loadConfig(latent_config)
        self.master.startService()
        self.bot1 = self.master.botmaster.slaves['bot1']
        self.bot2 = self.master.botmaster.slaves['bot2']
        self.bot3 = self.master.botmaster.slaves['bot3']
        self.bot1.testcase = self
        self.bot2.testcase = self
        self.b1 = self.master.botmaster.builders['b1']

    def doBuild(self, buildername):
        br = BuildRequest("forced", SourceStamp(), 'test_builder')
        d = br.waitUntilFinished()
        self.control.getBuilder(buildername).requestBuild(br)
        return d

    def testSequence(self):
        # make sure both slaves appear in the builder.  This is automatically,
        # without any attaching.
        self.assertEqual(len(self.b1.slaves), 2)
        slavenames = [sb.slave.slavename for sb in self.b1.slaves]
        slavenames.sort()
        self.assertEqual(slavenames,
                         ['bot1', 'bot2'])
        # These have not substantiated
        self.assertEqual([sb.slave.substantiated for sb in self.b1.slaves],
                         [False, False])
        self.assertEqual([sb.slave.slave for sb in self.b1.slaves],
                         [None, None])
        # we can mix and match latent slaves and normal slaves.  ATM, they
        # are treated identically in terms of selecting slaves.
        d = self.connectSlave(builders=['b1'], slavename='bot3')
        d.addCallback(self._testSequence_1)
        return d
    def _testSequence_1(self, res):
        # now we have all three slaves.  Two are latent slaves, and one is a
        # standard slave.
        slavenames = [sb.slave.slavename for sb in self.b1.slaves]
        slavenames.sort()
        self.assertEqual(slavenames,
                         ['bot1', 'bot2', 'bot3'])
        # Now it's time to try a build on one of the latent slaves,
        # substantiating it.
        # since the current scheduling algorithm is simple and does not
        # rotate or attempt any sort of load-balancing, two builds in
        # sequence should both use the first slave. This may change later if
        # we move to a more sophisticated scheme.
        self.b1.CHOOSE_SLAVES_RANDOMLY = False

        self.build_deferred = self.doBuild("b1")
        # now there's an event waiting for the slave to substantiate.
        e = self.b1.builder_status.getEvent(-1)
        self.assertEqual(e.text, ['substantiating'])
        # the substantiation_deferred is an internal stash of a deferred
        # that we'll grab so we can find the point at which the slave is
        # substantiated but the build has not yet started.
        d = self.bot1.substantiation_deferred
        self.assertNotIdentical(d, None)
        d.addCallback(self._testSequence_2)
        return d
    def _testSequence_2(self, res):
        # bot 1 is substantiated.
        self.assertNotIdentical(self.bot1.slave, None)
        self.failUnless(self.bot1.substantiated)
        # the event has announced it's success
        e = self.b1.builder_status.getEvent(-1)
        self.assertEqual(e.text, ['substantiate', 'success'])
        self.assertNotIdentical(e.finished, None)
        # now we'll wait for the build to complete
        d = self.build_deferred
        del self.build_deferred
        d.addCallback(self._testSequence_3)
        return d
    def _testSequence_3(self, res):
        # build was a success!
        self.failUnlessEqual(res.getResults(), SUCCESS)
        self.failUnlessEqual(res.getSlavename(), "bot1")
        # bot1 is substantiated now.  bot2 has not.
        self.failUnless(self.bot1.substantiated)
        self.failIf(self.bot2.substantiated)
        # bot1 is waiting a bit to see if there will be another build before
        # it shuts down the instance ("insubstantiates")
        self.build_wait_timer = self.bot1.build_wait_timer
        self.assertNotIdentical(self.build_wait_timer, None)
        self.failUnless(self.build_wait_timer.active())
        self.assertApproximates(
            self.bot1.build_wait_timeout,
            self.build_wait_timer.time - runtime.seconds(),
            2)
        # now we'll do another build
        d = self.doBuild("b1")
        # the slave is already substantiated, so no event is created
        e = self.b1.builder_status.getEvent(-1)
        self.assertNotEqual(e.text, ['substantiating'])
        # wait for the next build
        d.addCallback(self._testSequence_4)
        return d
    def _testSequence_4(self, res):
        # build was a success!
        self.failUnlessEqual(res.getResults(), SUCCESS)
        self.failUnlessEqual(res.getSlavename(), "bot1")
        # bot1 is still waiting, but with a new timer
        self.assertNotIdentical(self.bot1.build_wait_timer, None)
        self.assertNotIdentical(self.build_wait_timer,
                                self.bot1.build_wait_timer)
        self.assertApproximates(
            self.bot1.build_wait_timeout,
            self.bot1.build_wait_timer.time - runtime.seconds(),
            2)
        del self.build_wait_timer
        # We'll set the timer to fire sooner, and wait for it to fire.
        self.bot1.build_wait_timer.reset(0)
        d = defer.Deferred()
        reactor.callLater(1, d.callback, None)
        d.addCallback(self._testSequence_5)
        return d
    def _testSequence_5(self, res):
        # slave is insubstantiated
        self.assertIdentical(self.bot1.slave, None)
        self.failIf(self.bot1.substantiated)
        # Now we'll start up another build, to show that the shutdown left
        # things in such a state that we can restart.
        d = self.doBuild("b1")
        # the bot can return an informative message on success that the event
        # will render.  Let's use a mechanism of our test latent bot to
        # demonstrate that.
        self.bot1.start_message = ['[instance id]', '[start-up time]']
        # here's our event again:
        self.e = self.b1.builder_status.getEvent(-1)
        self.assertEqual(self.e.text, ['substantiating'])
        d.addCallback(self._testSequence_6)
        return d
    def _testSequence_6(self, res):
        # build was a success!
        self.failUnlessEqual(res.getResults(), SUCCESS)
        self.failUnlessEqual(res.getSlavename(), "bot1")
        # the event has announced it's success.  (Just imagine that
        # [instance id] and [start-up time] were actually valuable
        # information.)
        e = self.e
        del self.e
        self.assertEqual(
            e.text,
            ['substantiate', 'success', '[instance id]', '[start-up time]'])
        # Now we need to clean up the timer.  We could just cancel it, but
        # we'll go through the full dance once more time to show we can.
        # We'll set the timer to fire sooner, and wait for it to fire.
        # Also, we'll set the build_slave to take a little bit longer to shut
        # down, to see that it doesn't affect anything.
        self.bot1.stop_wait = 2
        self.bot1.build_wait_timer.reset(0)
        d = defer.Deferred()
        reactor.callLater(1, d.callback, None)
        d.addCallback(self._testSequence_7)
        return d
    def _testSequence_7(self, res):
        # slave is insubstantiated
        self.assertIdentical(self.bot1.slave, None)
        self.assertNot(self.bot1.substantiated)
        # the remote is still not cleaned out.  We'll wait for it.
        d = defer.Deferred()
        reactor.callLater(1, d.callback, None)
        return d

    def testNeverSubstantiated(self):
        # When a substantiation is requested, the slave may never appear.
        # This is a serious problem, and recovering from it is not really
        # handled well right now (in part because a way to handle it is not
        # clear).  However, at the least, the status event will show a
        # failure, and the slave will be told to insubstantiate, and to be
        # removed from the botmaster as anavailable slave.
        # This tells our test bot to never start, and to not complain about
        # being told to stop without ever starting
        self.bot1.testing_substantiation_timeout = True
        # normally (by default) we have 20 minutes to try and connect to the
        # remote
        self.assertEqual(self.bot1.missing_timeout, 20*60)
        # for testing purposes, we'll put that down to a tenth of a second!
        self.bot1.missing_timeout = 0.1
        # since the current scheduling algorithm is simple and does not
        # rotate or attempt any sort of load-balancing, two builds in
        # sequence should both use the first slave. This may change later if
        # we move to a more sophisticated scheme.
        self.b1.CHOOSE_SLAVES_RANDOMLY = False
        # start a build
        self.build_deferred = self.doBuild('b1')
        # the event tells us we are instantiating, as usual
        e = self.b1.builder_status.getEvent(-1)
        self.assertEqual(e.text, ['substantiating'])
        # we'll see in a moment that the test flag we have to show that the
        # bot was told to insubstantiate has been fired.  Here, we just verify
        # that it is ready to be fired.
        self.failIf(self.bot1.stopped)
        # That substantiation is going to fail.  Let's wait for it.
        d = self.bot1.substantiation_deferred
        self.assertNotIdentical(d, None)
        d.addCallbacks(self._testNeverSubstantiated_BadSuccess,
                       self._testNeverSubstantiated_1)
        return d
    def _testNeverSubstantiated_BadSuccess(self, res):
        self.fail('we should not have succeeded here.')
    def _testNeverSubstantiated_1(self, res):
        # ok, we failed.
        self.assertIdentical(self.bot1.slave, None)
        self.failIf(self.bot1.substantiated)
        self.failUnless(isinstance(res, failure.Failure))
        self.assertIdentical(self.bot1.substantiation_deferred, None)
        # our event informs us of this
        e1 = self.b1.builder_status.getEvent(-3)
        self.assertEqual(e1.text, ['substantiate', 'failed'])
        self.assertNotIdentical(e1.finished, None)
        # the slave is no longer available to build.  The events show it...
        e2 = self.b1.builder_status.getEvent(-2)
        self.assertEqual(e2.text, ['removing', 'latent', 'bot1'])
        e3 = self.b1.builder_status.getEvent(-1)
        self.assertEqual(e3.text, ['disconnect', 'bot1'])
        # ...and the builder shows it.
        self.assertEqual(['bot2'],
                         [sb.slave.slavename for sb in self.b1.slaves])
        # ideally, we would retry the build, but that infrastructure (which
        # would be used for other situations in the builder as well) does not
        # yet exist.  Therefore the build never completes one way or the
        # other, just as if a normal slave detached.

    def testServiceStop(self):
        # if the slave has an instance when it is stopped, the slave should
        # be told to shut down.
        self.b1.CHOOSE_SLAVES_RANDOMLY = False
        d = self.doBuild("b1")
        d.addCallback(self._testServiceStop_1)
        return d
    def _testServiceStop_1(self, res):
        # build was a success!
        self.failUnlessEqual(res.getResults(), SUCCESS)
        self.failUnlessEqual(res.getSlavename(), "bot1")
        # bot 1 is substantiated.
        self.assertNotIdentical(self.bot1.slave, None)
        self.failUnless(self.bot1.substantiated)
        # now let's stop the bot.
        d = self.bot1.stopService()
        d.addCallback(self._testServiceStop_2)
        return d
    def _testServiceStop_2(self, res):
        # bot 1 is NOT substantiated.
        self.assertIdentical(self.bot1.slave, None)
        self.failIf(self.bot1.substantiated)

    def testPing(self):
        # While a latent slave pings normally when it is substantiated, (as
        # happens behind the scene when a build is request), when
        # it is insubstantial, the ping is a no-op success.
        self.assertIdentical(self.bot1.slave, None)
        self.failIf(self.bot1.substantiated)
        d = self.connectSlave(builders=['b1'], slavename='bot3')
        d.addCallback(self._testPing_1)
        return d
    def _testPing_1(self, res):
        slavenames = [sb.slave.slavename for sb in self.b1.slaves]
        slavenames.sort()
        self.assertEqual(slavenames,
                         ['bot1', 'bot2', 'bot3'])
        d = self.control.getBuilder('b1').ping()
        d.addCallback(self._testPing_2)
        return d
    def _testPing_2(self, res):
        # all three pings were successful
        self.assert_(res)
        # but neither bot1 not bot2 substantiated.
        self.assertIdentical(self.bot1.slave, None)
        self.failIf(self.bot1.substantiated)
        self.assertIdentical(self.bot2.slave, None)
        self.failIf(self.bot2.substantiated)


class SlaveBusyness(RunMixin, unittest.TestCase):

    def setUp(self):
        RunMixin.setUp(self)
        self.master.loadConfig(config_busyness)
        self.master.startService()
        d = self.connectSlave(["b1", "b2"])
        return d

    def doBuild(self, buildername):
        br = BuildRequest("forced", SourceStamp(), 'test_builder')
        d = br.waitUntilFinished()
        self.control.getBuilder(buildername).requestBuild(br)
        return d

    def getRunningBuilds(self):
        return len(self.status.getSlave("bot1").getRunningBuilds())

    def testSlaveNotBusy(self):
        self.failUnlessEqual(self.getRunningBuilds(), 0)
        # now kick a build, wait for it to finish, then check again
        d = self.doBuild("b1")
        d.addCallback(self._testSlaveNotBusy_1)
        return d

    def _testSlaveNotBusy_1(self, res):
        self.failUnlessEqual(self.getRunningBuilds(), 0)

    def testSlaveBusyOneBuild(self):
        d1 = self.doBuild("b1")
        d2 = defer.Deferred()
        reactor.callLater(.5, d2.callback, None)
        d2.addCallback(self._testSlaveBusyOneBuild_1)
        d1.addCallback(self._testSlaveBusyOneBuild_finished_1)
        return defer.DeferredList([d1,d2])

    def _testSlaveBusyOneBuild_1(self, res):
        self.failUnlessEqual(self.getRunningBuilds(), 1)

    def _testSlaveBusyOneBuild_finished_1(self, res):
        self.failUnlessEqual(self.getRunningBuilds(), 0)

    def testSlaveBusyTwoBuilds(self):
        d1 = self.doBuild("b1")
        d2 = self.doBuild("b2")
        d3 = defer.Deferred()
        reactor.callLater(.5, d3.callback, None)
        d3.addCallback(self._testSlaveBusyTwoBuilds_1)
        d1.addCallback(self._testSlaveBusyTwoBuilds_finished_1, d2)
        return defer.DeferredList([d1,d3])

    def _testSlaveBusyTwoBuilds_1(self, res):
        self.failUnlessEqual(self.getRunningBuilds(), 2)

    def _testSlaveBusyTwoBuilds_finished_1(self, res, d2):
        self.failUnlessEqual(self.getRunningBuilds(), 1)
        d2.addCallback(self._testSlaveBusyTwoBuilds_finished_2)
        return d2

    def _testSlaveBusyTwoBuilds_finished_2(self, res):
        self.failUnlessEqual(self.getRunningBuilds(), 0)

    def testSlaveDisconnect(self):
        d1 = self.doBuild("b1")
        d2 = defer.Deferred()
        reactor.callLater(.5, d2.callback, None)
        d2.addCallback(self._testSlaveDisconnect_1)
        d1.addCallback(self._testSlaveDisconnect_finished_1)
        return defer.DeferredList([d1, d2])

    def _testSlaveDisconnect_1(self, res):
        self.failUnlessEqual(self.getRunningBuilds(), 1)
        return self.shutdownAllSlaves()

    def _testSlaveDisconnect_finished_1(self, res):
        self.failUnlessEqual(self.getRunningBuilds(), 0)

config_3 = """
from buildbot.process import factory
from buildbot.steps import dummy
from buildbot.buildslave import BuildSlave
from buildbot.config import BuilderConfig
s = factory.s

BuildmasterConfig = c = {}
c['slaves'] = [BuildSlave('bot1', 'sekrit')]
c['schedulers'] = []
c['slavePortnum'] = 0
c['schedulers'] = []

f1 = factory.BuildFactory([s(dummy.Wait, handle='one')])
f2 = factory.BuildFactory([s(dummy.Wait, handle='two')])
f3 = factory.BuildFactory([s(dummy.Wait, handle='three')])

c['builders'] = [
    BuilderConfig(name='b1', slavename='bot1', factory=f1),
]
"""

config_4 = config_3 + """
c['builders'] = [
    BuilderConfig(name='b1', slavename='bot1', factory=f2),
]
"""

config_5 = config_3 + """
c['builders'] = [
    BuilderConfig(name='b1', slavename='bot1', factory=f3),
]
"""

from buildbot.slave.commands import waitCommandRegistry

class Reconfig(RunMixin, unittest.TestCase):

    def setUp(self):
        RunMixin.setUp(self)
        self.master.loadConfig(config_3)
        self.master.startService()
        d = self.connectSlave(["b1"])
        return d

    def _one_started(self):
        log.msg("testReconfig._one_started")
        self.build1_started = True
        self.d1.callback(None)
        return self.d2

    def _two_started(self):
        log.msg("testReconfig._two_started")
        self.build2_started = True
        self.d3.callback(None)
        return self.d4

    def _three_started(self):
        log.msg("testReconfig._three_started")
        self.build3_started = True
        self.d5.callback(None)
        return self.d6

    def testReconfig(self):
        # reconfiguring a Builder should not interrupt any running Builds. No
        # queued BuildRequests should be lost. The next Build started should
        # use the new process.
        slave1 = self.slaves['bot1']
        bot1 = slave1.getServiceNamed('bot')
        sb1 = bot1.builders['b1']
        self.failUnless(isinstance(sb1, bot.SlaveBuilder))
        self.failUnless(sb1.running)
        b1 = self.master.botmaster.builders['b1']
        self.orig_b1 = b1

        self.d1 = d1 = defer.Deferred()
        self.d2 = d2 = defer.Deferred()
        self.d3, self.d4 = defer.Deferred(), defer.Deferred()
        self.d5, self.d6 = defer.Deferred(), defer.Deferred()
        self.build1_started = False
        self.build2_started = False
        self.build3_started = False
        waitCommandRegistry[("one","build1")] = self._one_started
        waitCommandRegistry[("two","build2")] = self._two_started
        waitCommandRegistry[("three","build3")] = self._three_started

        # use different branches to make sure these cannot be merged
        br1 = BuildRequest("build1", SourceStamp(branch="1"), 'test_builder')
        b1.submitBuildRequest(br1)
        br2 = BuildRequest("build2", SourceStamp(branch="2"), 'test_builder')
        b1.submitBuildRequest(br2)
        br3 = BuildRequest("build3", SourceStamp(branch="3"), 'test_builder')
        b1.submitBuildRequest(br3)
        self.requests = (br1, br2, br3)
        # all three are now in the queue

        # wait until the first one has started
        d1.addCallback(self._testReconfig_2)
        return d1

    def _testReconfig_2(self, res):
        log.msg("_testReconfig_2")
        # confirm that it is building
        brs = self.requests[0].status.getBuilds()
        self.failUnlessEqual(len(brs), 1)
        self.build1 = brs[0]
        self.failUnlessEqual(self.build1.getCurrentStep().getName(), "wait")
        # br1 is building, br2 and br3 are in the queue (in that order). Now
        # we reconfigure the Builder.
        self.failUnless(self.build1_started)
        d = self.master.loadConfig(config_4)
        d.addCallback(self._testReconfig_3)
        return d

    def _testReconfig_3(self, res):
        log.msg("_testReconfig_3")
        # now check to see that br1 is still building, and that br2 and br3
        # are in the queue of the new builder
        b1 = self.master.botmaster.builders['b1']
        self.failIfIdentical(b1, self.orig_b1)
        self.failIf(self.build1.isFinished())
        self.failUnlessEqual(self.build1.getCurrentStep().getName(), "wait")
        self.failUnlessEqual(len(b1.buildable), 2)
        self.failUnless(self.requests[1] in b1.buildable)
        self.failUnless(self.requests[2] in b1.buildable)

        # allow br1 to finish, and make sure its status is delivered normally
        d = self.requests[0].waitUntilFinished()
        d.addCallback(self._testReconfig_4)
        self.d2.callback(None)
        return d

    def _testReconfig_4(self, bs):
        log.msg("_testReconfig_4")
        self.failUnlessEqual(bs.getReason(), "build1")
        self.failUnless(bs.isFinished())
        self.failUnlessEqual(bs.getResults(), SUCCESS)

        # at this point, the first build has finished, and there is a pending
        # call to start the second build. Once that pending call fires, there
        # is a network roundtrip before the 'wait' RemoteCommand is delivered
        # to the slave. We need to wait for both events to happen before we
        # can check to make sure it is using the correct process. Just wait a
        # full second.
        d = defer.Deferred()
        d.addCallback(self._testReconfig_5)
        reactor.callLater(1, d.callback, None)
        return d

    def _testReconfig_5(self, res):
        log.msg("_testReconfig_5")
        # at this point the next build ought to be running
        b1 = self.master.botmaster.builders['b1']
        self.failUnlessEqual(len(b1.buildable), 1)
        self.failUnless(self.requests[2] in b1.buildable)
        self.failUnlessEqual(len(b1.building), 1)
        # and it ought to be using the new process
        self.failUnless(self.build2_started)

        # now, while the second build is running, change the config multiple
        # times.

        d = self.master.loadConfig(config_3)
        d.addCallback(lambda res: self.master.loadConfig(config_4))
        d.addCallback(lambda res: self.master.loadConfig(config_5))
        def _done(res):
            # then once that's done, allow the second build to finish and
            # wait for it to complete
            da = self.requests[1].waitUntilFinished()
            self.d4.callback(None)
            return da
        d.addCallback(_done)
        def _done2(res):
            # and once *that*'s done, wait another second to let the third
            # build start
            db = defer.Deferred()
            reactor.callLater(1, db.callback, None)
            return db
        d.addCallback(_done2)
        d.addCallback(self._testReconfig_6)
        return d

    def _testReconfig_6(self, res):
        log.msg("_testReconfig_6")
        # now check to see that the third build is running
        self.failUnless(self.build3_started)

        # we're done



class Slave2(RunMixin, unittest.TestCase):

    revision = 0

    def setUp(self):
        RunMixin.setUp(self)
        self.master.loadConfig(config_1)
        self.master.startService()

    def doBuild(self, buildername, reason="forced"):
        # we need to prevent these builds from being merged, so we create
        # each of them with a different revision specifier. The revision is
        # ignored because our build process does not have a source checkout
        # step.
        self.revision += 1
        br = BuildRequest(reason, SourceStamp(revision=self.revision),
                                                            'test_builder')
        d = br.waitUntilFinished()
        self.control.getBuilder(buildername).requestBuild(br)
        return d

    def testFirstComeFirstServed(self):
        # submit three builds, then connect a slave which fails the
        # slaveping. The first build will claim the slave, do the slaveping,
        # give up, and re-queue the build. Verify that the build gets
        # re-queued in front of all other builds. This may be tricky, because
        # the other builds may attempt to claim the just-failed slave.

        d1 = self.doBuild("b1", "first")
        d2 = self.doBuild("b1", "second")
        #buildable = self.master.botmaster.builders["b1"].buildable
        #print [b.reason for b in buildable]

        # specifically, I want the poor build to get precedence over any
        # others that were waiting. To test this, we need more builds than
        # slaves.

        # now connect a broken slave. The first build started as soon as it
        # connects, so by the time we get to our _1 method, the ill-fated
        # build has already started.
        d = self.connectSlave(["b1"], opts={"failPingOnce": True})
        d.addCallback(self._testFirstComeFirstServed_1, d1, d2)
        return d
    def _testFirstComeFirstServed_1(self, res, d1, d2):
        # the master has send the slaveping. When this is received, it will
        # fail, causing the master to hang up on the slave. When it
        # reconnects, it should find the first build at the front of the
        # queue. If we simply wait for both builds to complete, then look at
        # the status logs, we should see that the builds ran in the correct
        # order.

        d = defer.DeferredList([d1,d2])
        d.addCallback(self._testFirstComeFirstServed_2)
        return d
    def _testFirstComeFirstServed_2(self, res):
        b = self.status.getBuilder("b1")
        builds = b.getBuild(0), b.getBuild(1)
        reasons = [build.getReason() for build in builds]
        self.failUnlessEqual(reasons, ["first", "second"])

config_multi_builders = config_1 + """
c['builders'] = [
    BuilderConfig(name='dummy', factory=f2,
                  slavenames=['bot1', 'bot2', 'bot3']),
    BuilderConfig(name='dummy2', factory=f2,
                  slavenames=['bot1', 'bot2', 'bot3']),
    BuilderConfig(name='dummy3', factory=f2,
                  slavenames=['bot1', 'bot2', 'bot3']),
]
"""

config_mail_missing = config_1 + """
c['slaves'] = [BuildSlave('bot1', 'sekrit', notify_on_missing='admin',
                          missing_timeout=1)]
c['builders'] = [
    BuilderConfig(name='dummy', slavename='bot1', factory=f1),
]
c['projectName'] = 'myproject'
c['projectURL'] = 'myURL'
"""

class FakeMailer(mail.MailNotifier):
    def sendMessage(self, m, recipients):
        self.messages.append((m,recipients))
        return defer.succeed(None)

class BuildSlave(RunMixin, unittest.TestCase):
    def test_track_builders(self):
        self.master.loadConfig(config_multi_builders)
        self.master.readConfig = True
        self.master.startService()
        d = self.connectSlave()

        def _check(res):
            b = self.master.botmaster.builders['dummy']
            self.failUnless(len(b.slaves) == 1) # just bot1

            bs = b.slaves[0].slave
            self.failUnless(len(bs.slavebuilders) == 3)
            self.failUnless(b in [sb.builder for sb in
                                  bs.slavebuilders.values()])

        d.addCallback(_check)
        return d

    def test_mail_on_missing(self):
        self.master.loadConfig(config_mail_missing)
        self.master.readConfig = True
        self.master.startService()
        fm = FakeMailer("buildbot@example.org")
        fm.messages = []
        fm.setServiceParent(self.master)
        self.master.statusTargets.append(fm)

        d = self.connectSlave()
        d.addCallback(self.stall, 1)
        d.addCallback(lambda res: self.shutdownSlave("bot1", "dummy"))
        def _not_yet(res):
            self.failIf(fm.messages)
        d.addCallback(_not_yet)
        # we reconnect right away, so the timer shouldn't fire
        d.addCallback(lambda res: self.connectSlave())
        d.addCallback(self.stall, 3)
        d.addCallback(_not_yet)
        d.addCallback(lambda res: self.shutdownSlave("bot1", "dummy"))
        d.addCallback(_not_yet)
        # now we let it sit disconnected for long enough for the timer to
        # fire
        d.addCallback(self.stall, 3)
        def _check(res):
            self.failUnlessEqual(len(fm.messages), 1)
            msg,recips = fm.messages[0]
            self.failUnlessEqual(recips, ["admin"])
            body = msg.as_string()
            self.failUnlessIn("To: admin", body)
            self.failUnlessIn("Subject: Buildbot: buildslave bot1 was lost",
                              body)
            self.failUnlessIn("From: buildbot@example.org", body)
            self.failUnlessIn("working for 'myproject'", body)
            self.failUnlessIn("has noticed that the buildslave named bot1 went away",
                              body)
            self.failUnlessIn("was 'one'", body)
            self.failUnlessIn("myURL", body)
        d.addCallback(_check)
        return d

    def stall(self, result, delay=1):
        d = defer.Deferred()
        reactor.callLater(delay, d.callback, result)
        return d
