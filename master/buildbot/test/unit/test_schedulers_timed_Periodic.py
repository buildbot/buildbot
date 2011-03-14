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
        self.assertRaises(AssertionError,
                lambda : timed.Periodic(name='test', builderNames=[ 'test' ],
                                        periodicBuildTimer=-2))

    def test_iterations_simple(self):
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

    def test_iterations_simple_branch(self):
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

    def test_iterations_long(self):
        sched = self.makeScheduler(name='test', builderNames=[ 'test' ],
                        periodicBuildTimer=10,
                        firstBuildDuration=15) # takes a while to start a build

        sched.startService()
        self.clock.advance(0) # let it trigger the first (longer) build
        while self.clock.seconds() < 40:
            self.clock.advance(1)
        self.assertEqual(self.events, [ 'B@0', 'B@15', 'B@25', 'B@35' ])
        self.assertEqual(self.state.get('last_build'), 35)

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

    def test_iterations_with_initial_state(self):
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

    def test_getNextBuildTime_None(self):
        sched = self.makeScheduler(name='test', builderNames=[ 'test' ],
                        periodicBuildTimer=13)
        # given None, build right away
        d = sched.getNextBuildTime(None)
        d.addCallback(lambda t : self.assertEqual(t, 0))
        return d

    def test_getNextBuildTime_given(self):
        sched = self.makeScheduler(name='test', builderNames=[ 'test' ],
                        periodicBuildTimer=13)
        # given a time, add the periodicBuildTimer to it
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
