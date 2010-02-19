# -*- test-case-name: buildbot.test.test_run -*-

from twisted.trial import unittest
from twisted.internet import defer
import os

from buildbot import interfaces
from buildbot.sourcestamp import SourceStamp
from buildbot.changes import changes
from buildbot.status import builder
from buildbot.process.builder import IDLE, BUILDING
from buildbot.eventual import fireEventually, flushEventualQueue

from buildbot.test.runutils import MasterMixin, TestFlagMixin, StallMixin
from buildbot.test.pollmixin import PollMixin
from buildbot.slave.commands import waitCommandRegistry


config_base = """
from buildbot.process import factory
from buildbot.steps import dummy
from buildbot.buildslave import BuildSlave
from buildbot.config import BuilderConfig
s = factory.s

f1 = factory.QuickBuildFactory('fakerep', 'cvsmodule', configure=None)

f2 = factory.BuildFactory([
    dummy.Dummy(timeout=1),
    dummy.RemoteDummy(timeout=2),
    ])

f3 = factory.BuildFactory([dummy.Wait('f3')])
f4 = factory.BuildFactory([dummy.Wait('f4')])

BuildmasterConfig = c = {}
c['slaves'] = [BuildSlave('bot1', 'sekrit')]
c['schedulers'] = []
c['builders'] = [
    BuilderConfig(name='quick', slavename='bot1', factory=f1,
        builddir='quickdir', slavebuilddir='slavequickdir'),
]
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
c['schedulers'] = [Scheduler('dummy', None, None, ['dummy'])]

c['builders'] = [
    BuilderConfig(name='dummy', slavename='bot1',
                  factory=f3, builddir='dummy1'),
]
"""

config_graceful_shutdown_idle = config_base + """
from buildbot.buildslave import BuildSlave
c['slaves'] = [ BuildSlave('bot1', 'sekrit', max_builds=2) ]

from buildbot.scheduler import Scheduler
c['schedulers'] = [Scheduler('dummy', None, None, ['dummy'])]

c['builders'].append({'name': 'dummy', 'slavename': 'bot1',
                      'builddir': 'dummy', 'factory': f3})
"""

config_graceful_shutdown_busy = config_base + """
from buildbot.buildslave import BuildSlave
c['slaves'] = [ BuildSlave('bot1', 'sekrit', max_builds=2) ]

from buildbot.scheduler import Scheduler
c['schedulers'] = [Scheduler('dummy', None, None, ['dummy', 'dummy2'])]

c['builders'].append({'name': 'dummy', 'slavename': 'bot1',
                      'builddir': 'dummy', 'factory': f3})
c['builders'].append({'name': 'dummy2', 'slavename': 'bot1',
                      'builddir': 'dummy2', 'factory': f4})
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
c['schedulers'] = [Scheduler('dummy', None, None, ['dummy', 'dummy2'])]

c['builders'] = c['builders'] + [
    BuilderConfig(name='dummy', slavename='bot1', factory=f3),
    BuilderConfig(name='dummy2', slavename='bot1', factory=f4),
]
"""

config_2 = config_base + """
c['builders'] = [
    BuilderConfig(name='dummy', slavename='bot1',
                  builddir='dummy1', factory=f2),
    BuilderConfig(name='test dummy', slavename='bot1',
                  factory=f2, category='test'),
]
"""

config_3 = config_2 + """
c['builders'] = c['builders'] + [
    BuilderConfig(name='adummy', slavename='bot1',
                  builddir='adummy3', factory=f2),
    BuilderConfig(name='bdummy', slavename='bot1',
                  builddir='adummy4', factory=f2,
                  category='test'),
]
"""

config_4 = config_base + """
c['builders'] = [
    BuilderConfig(name='dummy', slavename='bot1',
                  slavebuilddir='sdummy', factory=f2),
]
"""

config_4_newbasedir = config_4 + """
c['builders'] = [
    BuilderConfig(name='dummy', slavename='bot1',
                  builddir='dummy2', factory=f2),
]
"""

config_4_newbuilder = config_4_newbasedir + """
c['builders'] = c['builders'] + [
    BuilderConfig(name='dummy2', slavename='bot1',
                  builddir='dummy23', factory=f2),
]
"""

class Run(MasterMixin, StallMixin, unittest.TestCase):
    def testMaster(self):
        self.basedir = "run/Run/Master"
        self.create_master()
        m = self.master
        d = m.loadConfig(config_run)
        def _then(ign):
            cm = m.change_svc
            c = changes.Change("bob", ["Makefile", "foo/bar.c"],
                               "changed stuff")
            cm.addChange(c)
            return flushEventualQueue()
        d.addCallback(_then)
        # needs time to finish. TODO: why is flushEventualQueue not sufficient?
        d.addCallback(self.stall, 1.0)
        # we used to check that the Scheduler is now waiting, but when its
        # state moved into the database, that became a nuisance
        def _check(ign):
            # verify that the Scheduler is now waiting
            s = m.allSchedulers()[0]
            sid = s.schedulerid
            state = m.db.runInteractionNow(lambda t:
                                         m.db.scheduler_get_state(sid, t))
            self.failUnlessEqual(state["last_processed"], 1)
        d.addCallback(_check)
        return d

class WaitMixin:
    # to use this, put a steps.dummy.Wait(handle="XYZ") in your test build
    # factory, prepare, then start the build with reason="ABC". Then use
    # something like this:
    #
    #  self.prepare_wait("XYZ", "ABC") # must be done before build starts
    #  d = run_one_build(self.control, buildername, ss, reason="ABC")
    #  d.addCallback(self.wait_until_step_reached, "XYZ", "ABC")
    #  def assert_is_in_step(ign):
    #      # now the build will be in the middle of the Wait step
    #      # you must release it to continue
    #      return self.release_build("XYZ", "ABC")
    #  d.addCallback(assert_is_in_step)
    #  d.addCallback(wait_for_build_to_finish)
    _wait_handles = None

    def prepare_wait(self, handle, reason):
        if self._wait_handles is None:
            self._wait_handles = {}
        h = (handle, reason)
        d1, d2 = defer.Deferred(), defer.Deferred()
        self._wait_handles[h] = (d1, d2)
        def _catch():
            d1.callback(None)
            return d2
        waitCommandRegistry[h] = _catch
    def wait_until_step_reached(self, ign, handle, reason):
        h = (handle, reason)
        d1, d2 = self._wait_handles[h]
        return d1
    def release_build(self, res, handle, reason):
        h = (handle, reason)
        d1, d2 = self._wait_handles[h]
        del self._wait_handles[h]
        d2.callback(None)
        return res
    def release_all_builds(self, res=None):
        for (d1,d2) in self._wait_handles.values():
            d2.callback(None)
        del self._wait_handles
        return res

class CanStartBuild(MasterMixin, StallMixin, WaitMixin, unittest.TestCase):
    def testCanStartBuild(self):
        self.basedir = "run/CanStartBuild/CanStartBuild"
        self.prepare_wait("f3", "scheduler")
        d = self.do_test(config_can_build)
        d.addCallback(self.wait_until_step_reached, "f3", "scheduler")
        d.addCallback(self._check, BUILDING)
        d.addCallback(self.release_build, "f3", "scheduler")
        d.addCallback(lambda bs: bs.waitUntilFinished())
        return d

    def testCantStartBuild(self):
        self.basedir = "run/CanStartBuild/CantStartBuild"
        d = self.do_test(config_cant_build)
        d.addCallback(self._check, IDLE)
        return d

    def do_test(self, config):
        self.create_master()
        d = self.master.loadConfig(config)
        d.addCallback(lambda ign: self.connectSlave())
        def _then(ign):
            # send a change
            cm = self.master.change_svc
            c = changes.Change("bob", ["Makefile", "foo/bar.c"],
                               "changed stuff")
            cm.addChange(c)
        d.addCallback(_then)
        return d

    def _check(self, ign, expected_state):
        b = self.master.botmaster.builders['dummy']
        self.failUnless(len(b.slaves) == 1)
        buildslave = b.slaves[0]
        self.failUnlessEqual(buildslave.state, expected_state)
        if buildslave.state == BUILDING:
            bs = self.master.status.getBuilder("dummy").getCurrentBuilds()[0]
            return bs
        return None


class FirstToFire(defer.Deferred):
    def __init__(self, *ds):
        defer.Deferred.__init__(self)
        # self.called
        for d in ds:
            d.addBoth(self._one_fired)
    def _one_fired(self, res):
        if not self.called:
            self.callback(res)
        return res

class ConcurrencyLimit(MasterMixin, WaitMixin, StallMixin, PollMixin,
                       unittest.TestCase):

    def testConcurrencyLimit(self):
        self.basedir = "run/ConcurrencyLimit/ConcurrencyLimit"
        self.create_master()
        self.prepare_wait("f3", "scheduler")
        self.prepare_wait("f4", "scheduler")
        d = self.master.loadConfig(config_concurrency)
        d.addCallback(lambda res: self.connectSlave())

        def _send(res):
            # send a change. This will trigger both builders at the same
            # time, but since they share a slave, the max_builds=1 setting
            # will insure that only one of the two builds gets to run.
            # TODO: setting max_builds=2 doesn't cause this to fail.
            # TODO: sometimes this errors out
            cm = self.master.change_svc
            c = changes.Change("bob", ["Makefile", "foo/bar.c"],
                               "changed stuff")
            cm.addChange(c)
            d1 = self.wait_until_step_reached(None, "f3", "scheduler")
            d2 = self.wait_until_step_reached(None, "f4", "scheduler")
            return FirstToFire(d1, d2)
        d.addCallback(_send)

        def _check(res):
            builders = [ self.master.botmaster.builders[bn]
                         for bn in ('dummy', 'dummy2') ]
            for builder in builders:
                self.failUnless(len(builder.slaves) == 1)

            building_bs = [ builder
                            for builder in builders
                            if builder.slaves[0].state == BUILDING ]
            # assert that only one build is running right now. If the
            # max_builds= weren't in effect, this would be 2.
            self.failUnlessEqual(len(building_bs), 1)
            self.release_all_builds()
        d.addCallback(_check)
        # this _wait approach sometimes fails, leaving a timer lying around
        # which fires after the master has shut down (causing an error). I
        # don't know why. I had to punt and add the stall().
        def _wait():
            s = self.master.status
            if s.getBuilder("dummy").getLastFinishedBuild() is None:
                return False
            if s.getBuilder("dummy2").getLastFinishedBuild() is None:
                return False
            return True
        d.addCallback(lambda ign: self.poll(_wait))
        d.addCallback(self.stall, 0.5)
        return d


class Ping(MasterMixin, unittest.TestCase):
    def testPing(self):
        self.basedir = "run/Ping/Ping"
        self.create_master()
        c = interfaces.IControl(self.master)
        d = self.master.loadConfig(config_2)
        d.addCallback(lambda ign: self.connectSlave())
        d.addCallback(lambda ign: c.getBuilder("dummy").ping())
        return d

class BuilderNames(MasterMixin, unittest.TestCase):

    def testGetBuilderNames(self):
        self.basedir = "run/BuilderNames/GetBuilderNames"
        self.create_master()
        s = self.master.getStatus()
        d = self.master.loadConfig(config_3)
        def _check(ign):
            self.failUnlessEqual(s.getBuilderNames(),
                                 ["dummy", "test dummy", "adummy", "bdummy"])
            self.failUnlessEqual(s.getBuilderNames(categories=['test']),
                                 ["test dummy", "bdummy"])
        d.addCallback(_check)
        return d

class Disconnect(MasterMixin, StallMixin, PollMixin, unittest.TestCase):
    # verify that disconnecting the slave during a build properly
    # terminates the build

    # there are several points at which we might lose the slave or otherwise
    # interrupt the build. We're interested in confirming that 1) the build
    # actually stops, 2) the build is flunked (results=FAILURE) or retried
    # (results=RETRY) as appropriate, 3) partially-dead buildslaves are
    # detected quickly when appropriate (the pre-build Ping).

    # we don't have full test coverage for this. An earlier version of this
    # test used fragile time-based events (i.e. start a build, wait 1.5
    # seconds, kill the slave, check the results). Those tests were removed.

    #  * before we submit a build: certain force-build methods will fail
    #    (i.e. an IRC/web command should be refused)
    #    [testIdle: disappearSlave(allowReconnect=False)]
    #  * after we submit a build, but before the build starts (i.e. while
    #    waiting in the scheduler)
    #  * during the build's initial ping
    #    [testBuild1: shutdownAllSlaves()]
    #  * during the local Dummy() command
    #    [XXXtestBuild2: shutdownAllSlaves()]
    #    [XXXtestBuild3: killSlave()]
    #    [XXXtestInterrupt: bc.stopBuild()]
    #  * during the RemoteDummy() command
    #    [XXXtestBuild4: killSlave()]

    def startup(self, use_fast_timeout=False):
        d = self.master.loadConfig(config_2)
        d.addCallback(self._earlycheck)
        if use_fast_timeout:
            d.addCallback(lambda ign: self.connectSlaveFastTimeout())
        else:
            d.addCallback(lambda ign: self.connectSlave())
        # TODO: replacing this stall with flushEventualQueue or
        # wait_until_idle fails, showing the slave state as "offline" instead
        # of "idle". Why? connectSlave() waits on
        # botmaster.waitUntilBuilderDetached(), so what more needs to happen?
        d.addCallback(self.stall, 0.5)
        d.addCallback(self._earlycheck2)
        return d

    def _earlycheck(self, ign):
        s = self.status
        self.failUnlessEqual(s.getBuilderNames(), ["dummy", "test dummy"])
        self.s1 = s1 = s.getBuilder("dummy")
        self.failUnlessEqual(s1.getName(), "dummy")
        self.failUnlessEqual(s1.getState(), ("offline", []))
        self.failUnlessEqual(s1.getCurrentBuilds(), [])
        self.failUnlessEqual(s1.getLastFinishedBuild(), None)
        self.failUnlessEqual(s1.getBuild(-1), None)

    def _earlycheck2(self, res):
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
        bss = self.control.submitBuildSet(["dummy"], ss, "forced build")
        brs = bss.getBuildRequests()[0]
        d = defer.Deferred()
        def _started(bc):
            brs.unsubscribe(_started)
            d.callback(bc)
        brs.subscribe(_started)
        return d

    def testIdle(self):
        # if the slave does not respond to a ping when the build starts, the
        # build will be put back in the queue (i.e. unclaimed)
        self.basedir = "run/Disconnect/idle"
        self.create_master()
        db = self.master.db
        d = self.startup()
        def _then(ign):
            self.disappearSlave(allowReconnect=False)
            # the slave is now frozen, and won't respond to a ping. We submit
            # a build request, and wait for it to be claimed (shouldn't take
            # long). The build should be stuck in the waiting-for-pong state.
            ss = SourceStamp()
            bss = self.control.submitBuildSet(["dummy"], ss, "forced build")
            brs = bss.getBuildRequests()[0]
            self.brid = brs.brid
        d.addCallback(_then)
        def _get_claim(ign=None):
            def _db(t):
                t.execute(db.quoteq("SELECT claimed_at FROM buildrequests"
                                    " WHERE id=?"),
                          (self.brid,))
                return t.fetchall()[0][0]
            claimed_at = db.runInteractionNow(_db)
            return claimed_at
        def _is_claimed():
            return bool(_get_claim() > 0)
        d.addCallback(lambda ign: self.poll(_is_claimed))
        # now we kill the slave, which drops the TCP connection and halts the
        # ping. The BuildRequest should be put back into the unclaimed state.
        d.addCallback(lambda ign: self.killSlave())
        d.addCallback(self.wait_until_idle)
        d.addCallback(_get_claim)
        d.addCallback(lambda claim: self.failUnlessEqual(claim, 0))
        return d
    testIdle.timeout = 10


    def testBuild1(self):
        # this next sequence is timing-dependent. The dummy build takes at
        # least 3 seconds to complete, and this batch of commands must
        # complete within that time.
        self.basedir = "run/Disconnect/Build1"
        self.create_master()
        d = self.startup()
        d.addCallback(lambda ign: self.submitBuild())
        d.addCallback(self._testBuild1_1)
        return d
    testBuild1.timeout = 10

    def _testBuild1_1(self, bs):
        # now kill the slave before it gets to start the first step
        d = self.shutdownAllSlaves() # dies before it gets started
        d.addCallback(self._testBuild1_2, bs)
        return d

    def _testBuild1_2(self, res, bs):
        # now examine the just-stopped build and make sure it is really
        # stopped. This is checking for bugs in which the slave-detach gets
        # missed or causes an exception which prevents the build from being
        # marked as "finished due to an error".
        d1 = bs.waitUntilFinished()
        d2 = self.master.botmaster.waitUntilBuilderDetached("dummy")
        d = defer.DeferredList([d1, d2])
        d.addCallback(self.wait_until_idle)
        def _done(res):
            self.failUnlessEqual(self.s1.getState()[0], "offline")
            self.verifyDisconnect(bs)
        d.addCallback(_done)
        d.addCallback(self.wait_until_idle)
        return d

    # other tests

    def testDisappear(self):
        self.basedir = "run/Disconnect/Disappear"
        self.create_master()
        d = self.startup()
        def _stash(ign):
            self.bc = self.control.getBuilder("dummy")
        d.addCallback(_stash)
        # ping should succeed
        d.addCallback(lambda ign: self.bc.ping())
        def _check1(pingres):
            self.failUnlessEqual(pingres, True)
            # now, before any build is run, make the slave disappear
            self.disappearSlave(allowReconnect=False)
            # initiate the ping and then kill the slave, to simulate a
            # disconnect.
            d2 = self.bc.ping()
            self.killSlave()
            return d2
        d.addCallback(_check1)
        def _check2(pingres):
            self.failUnlessEqual(pingres, False)
        d.addCallback(_check2)
        return d

    def testDuplicate(self):
        self.basedir = "run/Disconnect/Duplicate"
        self.create_master()
        d = self.startup()
        def _then(ign):
            bs = self.status.getBuilder("dummy")
            ss = self.ss = bs.getSlaves()[0]

            self.failUnless(ss.isConnected())
            self.failUnlessEqual(ss.getAdmin(), "one")

            # now, before any build is run, make the first slave disappear
            self.disappearSlave(allowReconnect=False)

            d2 = self.master.botmaster.waitUntilBuilderDetached("dummy")
            # now let the new slave take over
            self.connectSlave2()
            return d2
        d.addCallback(_then)
        d.addCallback(lambda ign:
                      self.master.botmaster.waitUntilBuilderAttached("dummy"))
        def _check(ign):
            self.failUnless(self.ss.isConnected())
            self.failUnlessEqual(self.ss.getAdmin(), "two")
        d.addCallback(_check)
        return d
    testDuplicate.timeout = 10


    def testSlaveTimeout(self):
        self.basedir = "run/Disconnect/SlaveTimeout"
        self.create_master()
        d = self.startup(use_fast_timeout=True)
        def _then(ign):
            # now suppose the slave goes missing. We want to find out when it
            # creates a new Broker, so we reach inside and mark the current
            # Broker with the well-known sigil of impending messy death.
            bd = self.slaves['bot1'].getServiceNamed("bot").builders["dummy"]
            broker = bd.remote.broker
            broker.redshirt = 1
        d.addCallback(_then)
        # now we wait for 5 seconds, to make sure the keepalives will keep
        # the connection up
        d.addCallback(self.stall, 5.0)
        def _then2(ign):
            bd = self.slaves['bot1'].getServiceNamed("bot").builders["dummy"]
            if not bd.remote or not hasattr(bd.remote.broker, "redshirt"):
                self.fail("slave disconnected when it shouldn't have")

            d = self.master.botmaster.waitUntilBuilderDetached("dummy")
            # whoops! how careless of me.
            self.disappearSlave(allowReconnect=True)
            # the slave will realize the connection is lost within 2 seconds,
            # then ReconnectingPBClientFactory will attempt a reconnect.
            return d
        d.addCallback(_then2)
        d.addCallback(lambda ign:
                      self.master.botmaster.waitUntilBuilderAttached("dummy"))
        def _then3(ign):
            # make sure it is a new connection (i.e. a new Broker)
            bd = self.slaves['bot1'].getServiceNamed("bot").builders["dummy"]
            self.failUnless(bd.remote, "hey, slave isn't really connected")
            self.failIf(hasattr(bd.remote.broker, "redshirt"),
                        "hey, slave's Broker is still marked for death")
        d.addCallback(_then3)
        return d
    testSlaveTimeout.timeout = 20


class Basedir(MasterMixin, unittest.TestCase):
    def testChangeBuilddir(self):
        self.basedir = "run/Basedir/ChangeBuilddir"
        self.slave_basedir = self.basedir
        self.create_master()
        m = self.master
        d = m.loadConfig(config_4)
        d.addCallback(lambda ign: self.connectSlave())
        d.addCallback(self._testChangeBuilddir_1)
        return d

    def _testChangeBuilddir_1(self, res):
        self.bot = bot = self.slaves['bot1'].bot
        self.builder = builder = bot.builders.get("dummy")
        self.failUnless(builder)
        # slavebuilddir value.
        self.failUnlessEqual(builder.builddir, "sdummy")
        self.failUnlessEqual(builder.basedir,
                             os.path.join(self.basedir, "slavebase-bot1", "sdummy"))

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
                             os.path.join(self.basedir, "slavebase-bot1", "dummy2"))

        # add a new builder, which causes the basedir list to be reloaded
        d = self.master.loadConfig(config_4_newbuilder)
        return d

class Triggers(MasterMixin, TestFlagMixin, StallMixin, PollMixin, unittest.TestCase):
    config_trigger = config_base + """
from buildbot.schedulers.basic import Scheduler
from buildbot.schedulers.triggerable import Triggerable
from buildbot.steps.trigger import Trigger
from buildbot.steps.dummy import Dummy
from buildbot.test.runutils import SetTestFlagStep
from buildbot.process.properties import WithProperties
c['schedulers'] = [
    Scheduler('triggerer', None, None, ['triggerer'], properties={'dyn':'dyn'}),
    Triggerable('triggeree', ['triggeree'])
]
triggerer = factory.BuildFactory()
triggerer.addSteps([
    SetTestFlagStep(flagname='triggerer_started'),
    Trigger(flunkOnFailure=True, @ARGS@),
    SetTestFlagStep(flagname='triggerer_finished'),
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
        c = self.config_trigger.replace("@ARGS@", args)
        return c.replace("@DUMMYCLASS@", dummyclass)

    def testTriggerBuild(self):
        self.basedir = "run/Triggers/TriggerBuild"
        self.create_master()
        self.clearFlags()
        config = self.mkConfig("schedulerNames=['triggeree']", "Dummy")
        d = self.master.loadConfig(config)
        c = changes.Change("bob", ["Makefile", "foo/bar.c"], "changed stuff")
        d.addCallback(lambda ign: self.master.change_svc.addChange(c))
        d.addCallback(lambda ign:
                      self.connectSlave(builders=['triggerer', 'triggeree']))
        d.addCallback(self.stall, 0.5)
        d.addCallback(self._checkTriggerBuild)
        d.addCallback(self.waitForBuildToFinish, "triggerer")
        d.addCallback(self.waitForBuildToFinish, "triggeree")
        d.addCallback(fireEventually)
        return d

    def _checkTriggerBuild(self, res):
        self.failIfFlagNotSet('triggerer_started')
        self.failIfFlagNotSet('triggeree_started')
        self.failIfFlagSet('triggeree_finished')
        self.failIfFlagNotSet('triggerer_finished')

    def waitForBuildToFinish(self, ign, builder):
        def check():
            bs = self.status.getBuilder(builder)
            b = bs.getBuild(-1)
            if not b or not b.isFinished():
                return False
            return True
        d = self.poll(check)
        d.addCallback(self.wait_until_idle)
        return d


    def testTriggerBuildWait(self):
        self.basedir = "run/Triggers/TriggerBuildWait"
        self.create_master()
        self.clearFlags()
        config = self.mkConfig("schedulerNames=['triggeree'], waitForFinish=1",
                               "Dummy")
        d = self.master.loadConfig(config)
        c = changes.Change("bob", ["Makefile", "foo/bar.c"], "changed stuff")
        d.addCallback(lambda ign: self.master.change_svc.addChange(c))
        d.addCallback(lambda ign:
                      self.connectSlave(builders=['triggerer', 'triggeree']))
        d.addCallback(self.stall, 0.5)
        d.addCallback(self._checkTriggerBuildWait)
        d.addCallback(self.waitForBuildToFinish, "triggerer")
        d.addCallback(self.waitForBuildToFinish, "triggeree")
        d.addCallback(fireEventually)
        return d

    def _checkTriggerBuildWait(self, res):
        self.failIfFlagNotSet('triggerer_started')
        self.failIfFlagNotSet('triggeree_started')
        self.failIfFlagSet('triggeree_finished')
        self.failIfFlagSet('triggerer_finished')

    def testProperties(self):
        self.basedir = "run/Triggers/Properties"
        self.create_master()
        self.clearFlags()
        config = self.mkConfig("schedulerNames=['triggeree'], set_properties={'lit' : 'lit'}, copy_properties=['dyn']",
                               "SetTestFlagStep, flagname='props', value=WithProperties('%(lit:-MISSING)s:%(dyn:-MISSING)s')")
        d = self.master.loadConfig(config)
        c = changes.Change("bob", ["Makefile", "foo/bar.c"], "changed stuff")
        d.addCallback(lambda ign: self.master.change_svc.addChange(c))
        d.addCallback(lambda ign:
                      self.connectSlave(builders=['triggerer', 'triggeree']))
        d.addCallback(self.stall, 0.5)
        d.addCallback(self._checkProperties)
        d.addCallback(self.waitForBuildToFinish, "triggerer")
        d.addCallback(self.waitForBuildToFinish, "triggeree")
        d.addCallback(fireEventually)
        return d

    def _checkProperties(self, res):
        self.assertEqual(self.getFlag("props"), "lit:dyn")

class PropertyPropagation(MasterMixin, PollMixin, TestFlagMixin, unittest.TestCase):
    def setupTest(self, config, builders, changeProps={}):
        self.clearFlags()
        self.create_master()
        c = changes.Change("bob", ["Makefile", "foo/bar.c"], "changed stuff",
                           properties=changeProps)
        d = self.master.loadConfig(config)
        d.addCallback(lambda ign: self.master.change_svc.addChange(c))
        d.addCallback(lambda ign: self.connectSlave(builders=builders))
        for b in builders:
            d.addCallback(self.waitForBuildToFinish, b)
        return d

    def waitForBuildToFinish(self, ign, builder):
        def check():
            bs = self.status.getBuilder(builder)
            b = bs.getBuild(-1)
            if not b or not b.isFinished():
                return False
            return True
        d = self.poll(check)
        d.addCallback(self.wait_until_idle)
        return d

    config_schprop = config_base + """
from buildbot.scheduler import Scheduler
from buildbot.steps.dummy import Dummy
from buildbot.test.runutils import SetTestFlagStep
from buildbot.process.properties import WithProperties
c['schedulers'] = [
    Scheduler('mysched', None, None, ['flagcolor'], properties={'color':'red'}),
]
factory = factory.BuildFactory([
    s(SetTestFlagStep, flagname='testresult',
      value=WithProperties('color=%(color)s sched=%(scheduler)s')),
    ])
c['builders'] = [{'name': 'flagcolor', 'slavename': 'bot1',
                  'builddir': 'test', 'factory': factory},
                ]
"""

    def testScheduler(self):
        self.basedir = "run/PropertyPropagation/Scheduler"
        d = self.setupTest(self.config_schprop, ['flagcolor'])
        def _check(res):
            self.failUnlessEqual(self.getFlag('testresult'),
                'color=red sched=mysched')
        d.addCallback(_check)
        return d

    config_changeprop = config_base + """
from buildbot.scheduler import Scheduler
from buildbot.steps.dummy import Dummy
from buildbot.test.runutils import SetTestFlagStep
from buildbot.process.properties import WithProperties
c['schedulers'] = [
    Scheduler('mysched', None, 0.1, ['flagcolor'], properties={'color':'red'}),
]
factory = factory.BuildFactory([
    s(SetTestFlagStep, flagname='testresult',
      value=WithProperties('color=%(color)s sched=%(scheduler)s prop1=%(prop1)s')),
    ])
c['builders'] = [{'name': 'flagcolor', 'slavename': 'bot1',
                  'builddir': 'test', 'factory': factory},
                ]
"""

    def testChangeProp(self):
        d = self.setupTest(self.config_changeprop, ['flagcolor'],
                           changeProps={'color': 'blue', 'prop1': 'prop1'})
        def _check(res):
            self.failUnlessEqual(self.getFlag('testresult'),
                'color=blue sched=mysched prop1=prop1')
        d.addCallback(_check)
        return d

    config_slaveprop = config_base + """
from buildbot.scheduler import Scheduler
from buildbot.steps.dummy import Dummy
from buildbot.test.runutils import SetTestFlagStep
from buildbot.process.properties import WithProperties
c['schedulers'] = [
    Scheduler('mysched', None, 0.1, ['flagcolor'])
]
c['slaves'] = [BuildSlave('bot1', 'sekrit', properties={'color':'orange'})]
factory = factory.BuildFactory([
    s(SetTestFlagStep, flagname='testresult',
      value=WithProperties('color=%(color)s slavename=%(slavename)s')),
    ])
c['builders'] = [{'name': 'flagcolor', 'slavename': 'bot1',
                  'builddir': 'test', 'factory': factory},
                ]
"""
    def testSlave(self):
        d = self.setupTest(self.config_slaveprop, ['flagcolor'])
        def _check(res):
            self.failUnlessEqual(self.getFlag('testresult'),
                'color=orange slavename=bot1')
        d.addCallback(_check)
        return d

    config_trigger = config_base + """
from buildbot.scheduler import Triggerable, Scheduler
from buildbot.steps.trigger import Trigger
from buildbot.steps.dummy import Dummy
from buildbot.test.runutils import SetTestFlagStep
from buildbot.process.properties import WithProperties
c['schedulers'] = [
    Scheduler('triggerer', None, 0.1, ['triggerer'],
        properties={'color':'mauve', 'pls_trigger':'triggeree'}),
    Triggerable('triggeree', ['triggeree'], properties={'color':'invisible'})
]
triggerer = factory.BuildFactory([
    s(SetTestFlagStep, flagname='testresult', value='wrongone'),
    s(Trigger, flunkOnFailure=True,
        schedulerNames=[WithProperties('%(pls_trigger)s')],
        set_properties={'color' : WithProperties('%(color)s')}),
    s(SetTestFlagStep, flagname='testresult', value='triggered'),
    ])
triggeree = factory.BuildFactory([
    s(SetTestFlagStep, flagname='testresult',
        value=WithProperties('sched=%(scheduler)s color=%(color)s')),
    ])
c['builders'] = [{'name': 'triggerer', 'slavename': 'bot1',
                  'builddir': 'triggerer', 'factory': triggerer},
                 {'name': 'triggeree', 'slavename': 'bot1',
                  'builddir': 'triggeree', 'factory': triggeree}]
"""
    def testTrigger(self):
        d = self.setupTest(self.config_trigger, ['triggerer', 'triggeree'])
        def _check(res):
            self.failUnlessEqual(self.getFlag('testresult'),
                'sched=triggeree color=mauve')
        d.addCallback(_check)
        return d


config_test_flag = config_base + """
from buildbot.scheduler import Scheduler
c['schedulers'] = [Scheduler('quick', None, None, ['dummy'])]

from buildbot.test.runutils import SetTestFlagStep
f3 = factory.BuildFactory([
    s(SetTestFlagStep, flagname='foo', value='bar'),
    ])

c['builders'] = [{'name': 'dummy', 'slavename': 'bot1',
                  'builddir': 'dummy', 'factory': f3}]
"""

class TestFlag(MasterMixin, TestFlagMixin, unittest.TestCase):
    """Test for the TestFlag functionality in runutils"""
    def testTestFlag(self):
        self.basedir = 'run/Flag/TestFlag'
        self.create_master()
        d = self.master.loadConfig(config_test_flag)
        d.addCallback(lambda ign: self.connectSlave())

        def _addchange(ign):
            c = changes.Change("bob", ["Makefile", "foo/bar.c"], "changed")
            self.master.db.addChangeToDatabase(c)
            ss = SourceStamp(changes=[c])

            bss = self.control.submitBuildSet(['dummy'], ss, 'scheduler')
            brs = bss.getBuildRequests()[0]
            d1 = defer.Deferred()
            def _started(bc):
                brs.unsubscribe(_started)
                d1.callback(bc)
            brs.subscribe(_started)
            return d1
        d.addCallback(_addchange)
        def _check(res):
            self.failUnlessEqual(self.getFlag('foo'), 'bar')
        d.addCallback(_check)
        return d

# TODO: test everything, from Change submission to Scheduler to Build to
# Status. Use all the status types. Specifically I want to catch recurrences
# of the bug where I forgot to make Waterfall inherit from StatusReceiver
# such that buildSetSubmitted failed.

config_test_builder = config_base + """
from buildbot.scheduler import Scheduler
c['schedulers'] = [Scheduler('quick', 'dummy', None, ['dummy']),
                   Scheduler('quick2', 'dummy2', None, ['dummy2']),
                   Scheduler('quick3', 'dummy3', None, ['dummy3'])]

from buildbot.steps.shell import ShellCommand
f3 = factory.BuildFactory([
    s(ShellCommand, command="sleep 3", env={'blah':'blah'})
    ])

c['builders'] = [{'name': 'dummy', 'slavename': 'bot1', 'env': {'foo':'bar'},
                  'builddir': 'dummy', 'factory': f3}]

c['builders'].append({'name': 'dummy2', 'slavename': 'bot1',
                       'env': {'blah':'bar'}, 'builddir': 'dummy2',
                       'factory': f3})

f4 = factory.BuildFactory([
    s(ShellCommand, command="sleep 3")
    ])

c['builders'].append({'name': 'dummy3', 'slavename': 'bot1',
                       'env': {'blah':'bar'}, 'builddir': 'dummy3',
                       'factory': f4})
"""

class TestBuilder(MasterMixin, StallMixin, unittest.TestCase):
    def doBuilderEnvTest(self, branch, cb):
        self.create_master()
        d = self.master.loadConfig(config_test_builder)
        d.addCallback(lambda ign: self.connectSlave(builders=["dummy", "dummy2", "dummy3"]))

        def _addchange(ign):
            c = changes.Change("bob", ["Makefile", "foo/bar.c"], "changed", branch=branch)
            self.master.db.addChangeToDatabase(c)
            ss = SourceStamp(branch=branch, changes=[c])

            bss = self.control.submitBuildSet([branch], ss, 'scheduler')
            brs = bss.getBuildRequests()[0]
            d1 = defer.Deferred()
            def _started(bc):
                brs.unsubscribe(_started)
                d1.callback(bc)
            brs.subscribe(_started)
            return d1
        d.addCallback(_addchange)

        d.addCallback(cb)

        return d

    def waitUntilBuildFinished(self, build):
        return build.build_status.waitUntilFinished()

    def testBuilderEnv(self):
        self.basedir = "run/Builder/BuilderEnv"
        def _check(res):
            b = self.master.botmaster.builders['dummy']
            build = b.building[0]
            s = build.currentStep
            self.failUnless('foo' in s.cmd.args['env'])
            self.failUnlessEqual('bar', s.cmd.args['env']['foo'])
            self.failUnless('blah' in s.cmd.args['env'])
            self.failUnlessEqual('blah', s.cmd.args['env']['blah'])
        return self.doBuilderEnvTest("dummy", _check)

    def testBuilderEnvOverride(self):
        self.basedir = "run/Builder/BuilderEnvOverride"
        def _check(res):
            b = self.master.botmaster.builders['dummy2']
            build = b.building[0]
            s = build.currentStep
            self.failUnless('blah' in s.cmd.args['env'])
            self.failUnlessEqual('blah', s.cmd.args['env']['blah'])
        return self.doBuilderEnvTest("dummy2", _check)

    def testBuilderNoStepEnv(self):
        self.basedir = "run/Builder/BuilderNoStepEnv"
        def _check(res):
            b = self.master.botmaster.builders['dummy3']
            build = b.building[0]
            s = build.currentStep
            self.failUnless('blah' in s.cmd.args['env'])
            self.failUnlessEqual('bar', s.cmd.args['env']['blah'])
        return self.doBuilderEnvTest("dummy3", _check)


config_priority = """
from buildbot.process import factory
from buildbot.steps import dummy
from buildbot.buildslave import BuildSlave
from buildbot.scheduler import Scheduler

f1 = factory.BuildFactory([
    dummy.Dummy(timeout=1),
    ])

BuildmasterConfig = c = {}
c['slaves'] = [BuildSlave('bot1', 'sekrit')]
c['schedulers'] = []
c['builders'] = []
c['builders'].append({'name':'quick1', 'slavename':'bot1', 'builddir': 'quickdir1', 'factory': f1})
c['builders'].append({'name':'quick2', 'slavename':'bot1', 'builddir': 'quickdir2', 'factory': f1, 'category': 'special'})
c['slavePortnum'] = 0
"""

class BuildPrioritization(MasterMixin, unittest.TestCase):
    def getTime(self):
        return self.t[0]

    def addTime(self, n):
        self.t[0] += n

    def do_test(self, config):
        self.create_master()
        self.t = [0]
        self.master.db.getCurrentTime = self.getTime
        return self.master.loadConfig(config)

    def testSimplePriority(self):
        self.basedir = "run/BuildPrioritization/SimplePriority"
        d = self.do_test(config_priority)

        # Send 2 requests to alternating builders, with quick1 being submitted
        # before quick2
        ss = SourceStamp()
        self.addTime(1)
        self.control.submitBuildSet(['quick1'], ss, 'first')
        self.addTime(1)
        self.control.submitBuildSet(['quick2'], ss, 'second')

        def _check(ign):
            # The builders should be sorted properly
            builders = self.master.botmaster.builders.values()
            builders = self.master.botmaster._sort_builders(None, builders)
            self.failUnlessEqual([builder.name for builder in builders],
                    ["quick1", "quick2"])

        d.addCallback(_check)
        return d

    def testSimplePriorityReversed(self):
        self.basedir = "run/BuildPrioritization/SimplePriorityReversed"
        d = self.do_test(config_priority)

        # Send 2 requests to alternating builders, with quick1 being submitted
        # before quick2
        ss = SourceStamp()
        self.addTime(1)
        self.control.submitBuildSet(['quick2'], ss, 'first')
        self.addTime(1)
        self.control.submitBuildSet(['quick1'], ss, 'second')

        def _check(ign):
            # The builders should be sorted properly
            builders = self.master.botmaster.builders.values()
            builders = self.master.botmaster._sort_builders(None, builders)
            self.failUnlessEqual([builder.name for builder in builders],
                    ["quick2", "quick1"])

        d.addCallback(_check)
        return d

    def testComplexPriority(self):
        self.basedir = "run/BuildPrioritization/ComplexPriority"
        d = self.do_test(config_priority)

        # Send 10 requests to alternating builders, with quick1 being submitted
        # before quick2
        ss = SourceStamp()
        for i in range(10):
            self.addTime(1)
            if i % 2 == 0:
                self.control.submitBuildSet(['quick1'], ss, str(i))
            else:
                self.control.submitBuildSet(['quick2'], ss, str(i))

        def _check(ign):
            # The builds should be runnable in the proper order
            order = []
            while True:
                builders = self.master.botmaster.builders.values()
                builders = self.master.botmaster._sort_builders(None, builders)
                # Run the first builder
                buildable = builders[0].getBuildable()
                if not buildable:
                    break
                req = buildable[0]
                order.append(int(req.reason))
                self.master.db.retire_buildrequests([req.id], None)
            self.failUnlessEqual(order, range(10))

        d.addCallback(_check)
        return d

    def testCustomPriority(self):
        self.basedir = "run/BuildPrioritization/CustomPriority"
        d = self.do_test(config_priority + """
def prioritizeBuilders(botmaster, builders):
    def sortkey(builder):
        if builder.builder_status.category == "special":
            return 0, builder.getOldestRequestTime()
        else:
            return 1, builder.getOldestRequestTime()

    builders.sort(key=sortkey)
    return builders
c['prioritizeBuilders'] = prioritizeBuilders
""")

        # Send 10 requests to alternating builders, with quick1 being submitted
        # before quick2
        ss = SourceStamp()
        for i in range(10):
            self.addTime(1)
            if i % 2 == 0:
                self.control.submitBuildSet(['quick1'], ss, str(i))
            else:
                self.control.submitBuildSet(['quick2'], ss, str(i))

        def _check(ign):
            # The builds should be runnable in the proper order
            order = []
            while True:
                builders = self.master.botmaster.builders.values()
                builders = self.master.botmaster.prioritizeBuilders(None, builders)
                found = False
                # Run the first builder
                for builder in builders:
                    buildable = builder.getBuildable()
                    if not buildable:
                        continue
                    found = True
                    req = buildable[0]
                    order.append(int(req.reason))
                    self.master.db.retire_buildrequests([req.id], None)
                    break
                if not found:
                    break
            self.failUnlessEqual(order, [1,3,5,7,9,0,2,4,6,8])

        d.addCallback(_check)
        return d



# Test graceful shutdown when no builds are active, as well as
# canStartBuild after graceful shutdown is initiated
class GracefulShutdownIdle(MasterMixin, WaitMixin, unittest.TestCase):
    def testShutdown(self):
        self.basedir = "run/GracefulShutdownIdle/Shutdown"
        d = self.do_test(config_graceful_shutdown_idle)
        d.addCallback(self._do_shutdown)
        return d

    def _do_shutdown(self, res):
        bs = self.master.botmaster.builders['quick'].slaves[0]
        # Check that the slave is accepting builds once it's connected
        self.assertEquals(bs.slave.canStartBuild(), True)

        # Monkeypatch the slave's shutdown routine since the real shutdown
        # interrupts the test harness
        self.did_shutdown = False
        def _shutdown():
            self.did_shutdown = True
        bs.slave.shutdown = _shutdown

        # Start a graceful shutdown
        bs.slave.slave_status.setGraceful(True)
        # Check that the slave isn't accepting builds any more
        self.assertEquals(bs.slave.canStartBuild(), False)

        # Wait a little bit and then check that we (pretended to) shut down
        d = fireEventually()
        d.addCallback(self._check_shutdown)
        return d

    def _check_shutdown(self, res):
        self.assertEquals(self.did_shutdown, True)

    def do_test(self, config):
        self.create_master()
        d = self.master.loadConfig(config)
        d.addCallback(lambda ign: self.connectSlave())
        return d


class GracefulShutdownBusy(MasterMixin, WaitMixin, unittest.TestCase):
    def testShutdown(self):
        self.basedir = "run/GracefulShutdownBusy/Shutdown"
        self.prepare_wait("f3", "scheduler")
        self.prepare_wait("f4", "scheduler")
        d = self.do_test(config_graceful_shutdown_busy)

        def _wait(ign):
            d = defer.DeferredList([
                self.wait_until_step_reached(ign, "f3", "scheduler"),
                self.wait_until_step_reached(ign, "f4", "scheduler"),
                ])
            return d
        d.addCallback(_wait)

        # Start a graceful shutdown.  We should be in the middle of two builds
        def _shutdown(res):
            bs = self.master.botmaster.builders['dummy'].slaves[0]
            # Monkeypatch the slave's shutdown routine since the real shutdown
            # interrupts the test harness
            self.did_shutdown = False
            def _shutdown():
                self.did_shutdown = True
                return defer.succeed(None)
            bs.slave.shutdown = _shutdown
            # Start a graceful shutdown
            bs.slave.slave_status.setGraceful(True)

            builders = [ self.master.botmaster.builders[bn]
                         for bn in ('dummy', 'dummy2') ]
            for builder in builders:
                self.failUnless(len(builder.slaves) == 1)
            building_bs = [ builder
                            for builder in builders
                            if builder.slaves[0].state == BUILDING ]
            # assert that both builds are running right now.
            self.failUnlessEqual(len(building_bs), 2)

        d.addCallback(_shutdown)

        d.addCallback(self.release_all_builds)

        # Wait a little bit again, and then make sure that we are still running
        # the two builds, and haven't shutdown yet
        def _check(res):
            self.assertEquals(self.did_shutdown, False)
            builders = [ self.master.botmaster.builders[bn]
                         for bn in ('dummy', 'dummy2') ]
            for builder in builders:
                self.failUnless(len(builder.slaves) == 1)
            building_bs = [ builder
                            for builder in builders
                            if builder.slaves[0].state == BUILDING ]
            # assert that both builds are running right now.
            self.failUnlessEqual(len(building_bs), 2)
        d.addCallback(_check)

        # Wait for all the builds to finish
        def _wait_finish(res):
            builders = [ self.master.botmaster.builders[bn]
                         for bn in ('dummy', 'dummy2') ]
            builds = []
            for builder in builders:
                builds.append(builder.builder_status.currentBuilds[0].waitUntilFinished())
            dl = defer.DeferredList(builds)
            return dl
        d.addCallback(_wait_finish)

        d.addCallback(flushEventualQueue)

        # Wait a little bit after the builds finish, and then
        # check that the slave has shutdown
        def _check_shutdown(res):
            # assert that we shutdown the slave
            self.assertEquals(self.did_shutdown, True)
            builders = [ self.master.botmaster.builders[bn]
                         for bn in ('dummy', 'dummy2') ]
            building_bs = [ builder
                            for builder in builders
                            if builder.slaves[0].state == BUILDING ]
            # assert that no builds are running right now.
            self.failUnlessEqual(len(building_bs), 0)
        d.addCallback(_check_shutdown)

        return d

    def do_test(self, config):
        self.create_master()
        d = self.master.loadConfig(config)
        d.addCallback(lambda ign: self.connectSlave())
        def _then(ign):
            # send a change
            cm = self.master.change_svc
            c = changes.Change("bob", ["Makefile", "foo/bar.c"],
                               "changed stuff")
            cm.addChange(c)
        d.addCallback(_then)
        return d

