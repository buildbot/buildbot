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
from twisted.internet import task, defer
from buildbot.schedulers import timed
from buildbot import config

class Periodic(unittest.TestCase):

    def makeScheduler(self, firstBuildDuration=0, exp_branch=None, **kwargs):
        self.sched = sched = timed.Periodic(**kwargs)

        # add a Clock to help checking timing issues
        self.clock = sched._reactor = task.Clock()

        # keep track of builds in self.events
        self.events = []
        def addBuildsetForLatest(reason=None, branch=None):
            self.assertIn('Periodic scheduler named', reason)
            self.assertEqual(branch, exp_branch)
            isFirst = (self.events == [])
            self.events.append('B@%d' % self.clock.seconds())
            if isFirst and firstBuildDuration:
                d = defer.Deferred()
                self.clock.callLater(firstBuildDuration, d.callback, None)
                return d
            else:
                return defer.succeed(None)
        sched.addBuildsetForLatest = addBuildsetForLatest

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
        """
        When a L{timed.Periodic} is constructed with a negative timer, it
        raises a L{config.ConfigError}.
        """
        self.assertRaises(config.ConfigErrors,
                lambda : timed.Periodic(name='test', builderNames=[ 'test' ],
                                        periodicBuildTimer=-2))

    def test_iterations_simple(self):
        """
        When L{timed.Periodic} is started without saved state, it runs a build
        immediately and after every period, and the saves the time of the last
        build.
        """
        sched = self.makeScheduler(name='test', builderNames=[ 'test' ],
                        periodicBuildTimer=13)

        sched.startService()
        self.clock.advance(0) # let it trigger the first build
        while self.clock.seconds() < 30:
            self.clock.advance(1)
        self.assertEqual(self.events, [ 'B@0', 'B@13', 'B@26' ])
        self.assertEqual(self.state.get('last_build'), 26)

        d = sched.stopService()
        return d

    def test_iterations_simple_runAtStartIsFalse(self):
        """
        When L{timed.Periodic} is started without saved state and runAtStart,
        it runs a build after a period and after every period, and the saves the
        time of the last build.
        """
        sched = self.makeScheduler(name='test', builderNames=[ 'test' ],
                        periodicBuildTimer=13, runAtStart=False)

        sched.startService()
        self.clock.advance(0) # let it trigger the first build
        while self.clock.seconds() < 30:
            self.clock.advance(1)
        self.assertEqual(self.events, [ 'B@13', 'B@26' ])
        self.assertEqual(self.state.get('last_build'), 26)

        d = sched.stopService()
        return d

    def test_iterations_simple_branch(self):
        """
        When L{time.Periodic} is passed a C{branch} argument, this builds it
        starts are on that branch.
        """
        sched = self.makeScheduler(exp_branch='newfeature',
                name='test', builderNames=[ 'test' ],
                periodicBuildTimer=13, branch='newfeature')

        sched.startService()
        self.clock.advance(0) # let it trigger the first build
        while self.clock.seconds() < 30:
            self.clock.advance(1)
        self.assertEqual(self.events, [ 'B@0', 'B@13', 'B@26' ])
        self.assertEqual(self.state.get('last_build'), 26)

        d = sched.stopService()
        return d

    def test_iterations_scheduleAsLongAsPeriod(self):
        """
        When a scheduling a build takes as long as a period, the next
        build is scheduled immediately.
        """
        sched = self.makeScheduler(name='test', builderNames=[ 'test' ],
                        periodicBuildTimer=10,
                        firstBuildDuration=10) # takes a while to start a build

        sched.startService()
        self.clock.advance(0) # let it trigger the first (longer) build
        while self.clock.seconds() < 40:
            self.clock.advance(1)
        self.assertEqual(self.events, [ 'B@0', 'B@10', 'B@20', 'B@30', 'B@40' ])
        self.assertEqual(self.state.get('last_build'), 40)

        d = sched.stopService()
        return d

    def test_iterations_scheduleAsLongAsPeriod_runAtStartIsFalse(self):
        """
        If C{runAtStart} is L{True},
        when a scheduling a build takes as long as a period, the next
        build is scheduled immediately.
        """
        sched = self.makeScheduler(name='test', builderNames=[ 'test' ],
                        periodicBuildTimer=10, runAtStart=False,
                        firstBuildDuration=10) # takes a while to start a build

        sched.startService()
        self.clock.advance(0) # let it trigger the first (longer) build
        while self.clock.seconds() < 40:
            self.clock.advance(1)
        self.assertEqual(self.events, [ 'B@10', 'B@20', 'B@30', 'B@40' ])
        self.assertEqual(self.state.get('last_build'), 40)

        d = sched.stopService()
        return d

    def test_iterations_scheduleLongerThanPeriod(self):
        """
        When a scheduling a build takes longer than a period, the next
        build is scheduled immediately.
        """
        sched = self.makeScheduler(name='test', builderNames=[ 'test' ],
                        periodicBuildTimer=10,
                        firstBuildDuration=15) # takes a while to start a build

        sched.startService()
        self.clock.advance(0) # let it trigger the first (longer) build
        while self.clock.seconds() < 40:
            self.clock.advance(1)
        self.assertEqual(self.events, [ 'B@0', 'B@15', 'B@20', 'B@30', 'B@40' ])
        self.assertEqual(self.state.get('last_build'), 40)

        d = sched.stopService()
        return d

    def test_iterations_scheduleLongerThanPeriod_runAtStartIsFalse(self):
        """
        If C{runAtStart} is L{True},
        when a scheduling a build takes longer than a period, the next
        build is scheduled immediately.
        """
        sched = self.makeScheduler(name='test', builderNames=[ 'test' ],
                        periodicBuildTimer=10, runAtStart=False,
                        firstBuildDuration=15) # takes a while to start a build

        sched.startService()
        self.clock.advance(0) # let it trigger the first (longer) build
        while self.clock.seconds() < 40:
            self.clock.advance(1)
        self.assertEqual(self.events, [ 'B@10', 'B@25', 'B@30', 'B@40' ])
        self.assertEqual(self.state.get('last_build'), 40)

        d = sched.stopService()
        return d

    def test_iterations_stop_while_starting_build(self):
        sched = self.makeScheduler(name='test', builderNames=[ 'test' ],
                        periodicBuildTimer=13,
                        firstBuildDuration=6) # takes a while to start a build

        sched.startService()
        self.clock.advance(0) # let it trigger the first (longer) build
        self.clock.advance(3) # get partway into that build

        d = sched.stopService() # begin stopping the service
        d.addCallback(lambda _ : self.events.append('STOP@%d' % self.clock.seconds()))

        # run the clock out
        while self.clock.seconds() < 40:
            self.clock.advance(1)

        # note that the stopService completes after the first build completes, and no
        # subsequent builds occur
        self.assertEqual(self.events, [ 'B@0', 'STOP@6' ])
        self.assertEqual(self.state.get('last_build'), 0)

        return d

    def test_missedBuildDoesntDoubleBuild(self):
        """
        When L{timed.Periodic} misses a build, it doesn't start two builds to compensate.
        """
        sched = self.makeScheduler(name='test', builderNames=[ 'test' ],
                        periodicBuildTimer=13)

        sched.startService()
        self.clock.advance(0) # let it trigger the first build
        self.clock.advance(26) # skip a build
        while self.clock.seconds() < 40:
            self.clock.advance(1)
        self.assertEqual(self.events, [ 'B@0', 'B@26', 'B@39' ])
        self.assertEqual(self.state.get('last_build'), 39)

        d = sched.stopService()
        return d

    def test_iterations_with_initial_state(self):
        """
        When L{timed.Period} is started and the most recent build is less than one period
        in the past, a build started at the appropriate time.
        """
        sched = self.makeScheduler(name='test', builderNames=[ 'test' ],
                        periodicBuildTimer=13)
        self.state['last_build'] = self.clock.seconds() - 7 # so next build should start in 6s

        sched.startService()
        self.clock.advance(0) # let it trigger the first build
        while self.clock.seconds() < 30:
            self.clock.advance(1)
        self.assertEqual(self.events, [ 'B@6', 'B@19' ])
        self.assertEqual(self.state.get('last_build'), 19)

        d = sched.stopService()
        return d

    def test_iterations_with_initial_state_old(self):
        """
        If the most recent build is more than one period in the past
        when L{timed.Period} is started, a build is started immediately.
        """
        sched = self.makeScheduler(name='test', builderNames=[ 'test' ],
                        periodicBuildTimer=13)
        self.state['last_build'] = self.clock.seconds() - 30

        sched.startService()
        self.clock.advance(0) # let it trigger the first build
        while self.clock.seconds() < 30:
            self.clock.advance(1)
        self.assertEqual(self.events, [ 'B@0', 'B@13', 'B@26' ])
        self.assertEqual(self.state.get('last_build'), 26)

        d = sched.stopService()
        return d

    def test_iterations_with_initial_state_old_runAtAtStartIsFalse(self):
        """
        If the most recent build is more than one period in the past and
        C{runAtStart} is L{False}, when L{timed.Period} is started, a build is
        started after one period.
        """
        sched = self.makeScheduler(name='test', builderNames=[ 'test' ],
                        periodicBuildTimer=13, runAtStart=False)
        self.state['last_build'] = self.clock.seconds() - 30

        sched.startService()
        self.clock.advance(0) # let it trigger the first build
        while self.clock.seconds() < 30:
            self.clock.advance(1)
        self.assertEqual(self.events, [ 'B@13', 'B@26' ])
        self.assertEqual(self.state.get('last_build'), 26)

        d = sched.stopService()
        return d

    def test_iterations_withInitialState_exactlyOnePeriod(self):
        """
        If the most recent build is exactly one period in the past,
        when L{timed.Period} is started, a build is
        started immediately.
        """
        sched = self.makeScheduler(name='test', builderNames=[ 'test' ],
                        periodicBuildTimer=13)
        self.state['last_build'] = self.clock.seconds() - 13

        sched.startService()
        self.clock.advance(0) # let it trigger the first build
        while self.clock.seconds() < 30:
            self.clock.advance(1)
        self.assertEqual(self.events, [ 'B@0', 'B@13', 'B@26' ])
        self.assertEqual(self.state.get('last_build'), 26)

        d = sched.stopService()
        return d

    def test_iterations_withInitialState_exactlyOnePeriod_runAtAtStartIsFalse(self):
        """
        If the most recent build is exactly one period in the past and
        C{runAtStart} is L{False}, when L{timed.Period} is started, a build is
        started immediately.
        """
        sched = self.makeScheduler(name='test', builderNames=[ 'test' ],
                        periodicBuildTimer=13, runAtStart=False)
        self.state['last_build'] = self.clock.seconds() - 13

        sched.startService()
        self.clock.advance(0) # let it trigger the first build
        while self.clock.seconds() < 30:
            self.clock.advance(1)
        self.assertEqual(self.events, [ 'B@13', 'B@26' ])
        self.assertEqual(self.state.get('last_build'), 26)

        d = sched.stopService()
        return d

    def test_getNextBuildTime_None(self):
        """
        When there is no previous build time, then a build is scheduled immediately.
        """
        sched = self.makeScheduler(name='test', builderNames=[ 'test' ],
                        periodicBuildTimer=13)
        # given None, build right away
        d = sched.getNextBuildTime(None)
        d.addCallback(lambda t : self.assertEqual(t, 0))
        return d

    def test_getNextBuildTime_given(self):
        """
        When there is a previous build time, then the next scheduled build
        is one period later.
        """
        sched = self.makeScheduler(name='test', builderNames=[ 'test' ],
                        periodicBuildTimer=13)
        d = sched.getNextBuildTime(20)
        d.addCallback(lambda t : self.assertEqual(t, 33))
        return d

    def test_getPendingBuildTimes(self):
        sched = self.makeScheduler(name='test', builderNames=[ 'test' ],
                        periodicBuildTimer=13)
        self.state['last_build'] = self.clock.seconds() - 10 # so next build should start in 3s

        sched.startService()
        self.clock.advance(0) # let it schedule the first build
        self.assertEqual(sched.getPendingBuildTimes(), [ 3.0 ])

        d = sched.stopService()
        return d
