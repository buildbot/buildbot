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

from __future__ import absolute_import
from __future__ import print_function

from twisted.internet import defer
from twisted.internet import task
from twisted.trial import unittest

from buildbot import config
from buildbot.schedulers import timed
from buildbot.test.util import scheduler


class Periodic(scheduler.SchedulerMixin, unittest.TestCase):

    OBJECTID = 23
    SCHEDULERID = 3

    def setUp(self):
        self.setUpScheduler()

    def makeScheduler(self, firstBuildDuration=0, exp_branch=None, **kwargs):
        self.sched = sched = timed.Periodic(**kwargs)
        self.attachScheduler(self.sched, self.OBJECTID, self.SCHEDULERID)

        # add a Clock to help checking timing issues
        self.clock = sched._reactor = task.Clock()

        # keep track of builds in self.events
        self.events = []

        def addBuildsetForSourceStampsWithDefaults(reason, sourcestamps,
                                                   waited_for=False, properties=None, builderNames=None,
                                                   **kw):
            self.assertIn('Periodic scheduler named', reason)
            # TODO: check branch
            isFirst = (self.events == [])
            self.events.append('B@%d' % self.clock.seconds())
            if isFirst and firstBuildDuration:
                d = defer.Deferred()
                self.clock.callLater(firstBuildDuration, d.callback, None)
                return d
            return defer.succeed(None)
        sched.addBuildsetForSourceStampsWithDefaults = addBuildsetForSourceStampsWithDefaults

        # handle state locally
        self.state = {}

        def getState(k, default):
            return defer.succeed(self.state.get(k, default))
        sched.getState = getState

        def setState(k, v):
            self.state[k] = v
            return defer.succeed(None)
        sched.setState = setState

        return sched

    # tests

    def test_constructor_invalid(self):
        self.assertRaises(config.ConfigErrors,
                          lambda: timed.Periodic(name='test', builderNames=['test'],
                                                 periodicBuildTimer=-2))

    def test_constructor_no_reason(self):
        sched = self.makeScheduler(
            name='test', builderNames=['test'], periodicBuildTimer=10)
        self.assertEqual(
            sched.reason, "The Periodic scheduler named 'test' triggered this build")

    def test_constructor_reason(self):
        sched = self.makeScheduler(
            name='test', builderNames=['test'], periodicBuildTimer=10, reason="periodic")
        self.assertEqual(sched.reason, "periodic")

    def test_iterations_simple(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                                   periodicBuildTimer=13)

        sched.activate()
        self.clock.advance(0)  # let it trigger the first build
        while self.clock.seconds() < 30:
            self.clock.advance(1)
        self.assertEqual(self.events, ['B@0', 'B@13', 'B@26'])
        self.assertEqual(self.state.get('last_build'), 26)

        d = sched.deactivate()
        return d

    def test_iterations_simple_branch(self):
        sched = self.makeScheduler(exp_branch='newfeature',
                                   name='test', builderNames=['test'],
                                   periodicBuildTimer=13, branch='newfeature')

        sched.activate()
        self.clock.advance(0)  # let it trigger the first build
        while self.clock.seconds() < 30:
            self.clock.advance(1)
        self.assertEqual(self.events, ['B@0', 'B@13', 'B@26'])
        self.assertEqual(self.state.get('last_build'), 26)

        d = sched.deactivate()
        return d

    def test_iterations_long(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                                   periodicBuildTimer=10,
                                   firstBuildDuration=15)  # takes a while to start a build

        sched.activate()
        self.clock.advance(0)  # let it trigger the first (longer) build
        while self.clock.seconds() < 40:
            self.clock.advance(1)
        self.assertEqual(self.events, ['B@0', 'B@15', 'B@25', 'B@35'])
        self.assertEqual(self.state.get('last_build'), 35)

        d = sched.deactivate()
        return d

    def test_iterations_stop_while_starting_build(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                                   periodicBuildTimer=13,
                                   firstBuildDuration=6)  # takes a while to start a build

        sched.activate()
        self.clock.advance(0)  # let it trigger the first (longer) build
        self.clock.advance(3)  # get partway into that build

        d = sched.deactivate()  # begin stopping the service
        d.addCallback(
            lambda _: self.events.append('STOP@%d' % self.clock.seconds()))

        # run the clock out
        while self.clock.seconds() < 40:
            self.clock.advance(1)

        # note that the deactivate completes after the first build completes, and no
        # subsequent builds occur
        self.assertEqual(self.events, ['B@0', 'STOP@6'])
        self.assertEqual(self.state.get('last_build'), 0)

        return d

    def test_iterations_with_initial_state(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                                   periodicBuildTimer=13)
        # so next build should start in 6s
        self.state['last_build'] = self.clock.seconds() - 7

        sched.activate()
        self.clock.advance(0)  # let it trigger the first build
        while self.clock.seconds() < 30:
            self.clock.advance(1)
        self.assertEqual(self.events, ['B@6', 'B@19'])
        self.assertEqual(self.state.get('last_build'), 19)

        d = sched.deactivate()
        return d

    def test_getNextBuildTime_None(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                                   periodicBuildTimer=13)
        # given None, build right away
        d = sched.getNextBuildTime(None)
        d.addCallback(lambda t: self.assertEqual(t, 0))
        return d

    def test_getNextBuildTime_given(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                                   periodicBuildTimer=13)
        # given a time, add the periodicBuildTimer to it
        d = sched.getNextBuildTime(20)
        d.addCallback(lambda t: self.assertEqual(t, 33))
        return d

    @defer.inlineCallbacks
    def test_enabled_callback(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                                   periodicBuildTimer=13)
        expectedValue = not sched.enabled
        yield sched._enabledCallback(None, {'enabled': not sched.enabled})
        self.assertEqual(sched.enabled, expectedValue)
        expectedValue = not sched.enabled
        yield sched._enabledCallback(None, {'enabled': not sched.enabled})
        self.assertEqual(sched.enabled, expectedValue)

    @defer.inlineCallbacks
    def test_disabled_activate(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                                   periodicBuildTimer=13)
        yield sched._enabledCallback(None, {'enabled': not sched.enabled})
        self.assertEqual(sched.enabled, False)
        r = yield sched.activate()
        self.assertEqual(r, None)

    @defer.inlineCallbacks
    def test_disabled_deactivate(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                                   periodicBuildTimer=13)
        yield sched._enabledCallback(None, {'enabled': not sched.enabled})
        self.assertEqual(sched.enabled, False)
        r = yield sched.deactivate()
        self.assertEqual(r, None)

    @defer.inlineCallbacks
    def test_disabled_start_build(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                                   periodicBuildTimer=13)
        yield sched._enabledCallback(None, {'enabled': not sched.enabled})
        self.assertEqual(sched.enabled, False)
        r = yield sched.startBuild()
        self.assertEqual(r, None)
