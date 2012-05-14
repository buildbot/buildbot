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

import mock
from twisted.trial import unittest
from twisted.internet import defer, task
from twisted.python import log
from buildbot.schedulers import timed
from buildbot.test.util import scheduler
from buildbot.changes import filter

class Nightly(scheduler.SchedulerMixin, unittest.TestCase):

    SCHEDULERID = 132

    def makeScheduler(self, firstBuildDuration=0, **kwargs):
        sched = self.attachScheduler(timed.Nightly(**kwargs),
                self.SCHEDULERID)

        # add a Clock to help checking timing issues
        self.clock = sched._reactor = task.Clock()

        # keep track of builds in self.events
        self.events = []
        def addBuildsetForLatest(reason='', external_idstring='',
                branch=None, repository='', project=''):
            self.assertIn('scheduler named', reason)
            isFirst = (self.events == [])
            self.events.append('B(%s)@%d' % (branch,self.clock.seconds()))
            if isFirst and firstBuildDuration:
                d = defer.Deferred()
                self.clock.callLater(firstBuildDuration, d.callback, None)
                return d
            else:
                return defer.succeed(None)
        sched.addBuildsetForLatest = addBuildsetForLatest

        def addBuildsetForChanges(reason='', external_idstring='', changeids=[]):
            self.events.append('B%s@%d' % (`changeids`.replace(' ',''),
                                           self.clock.seconds()))
            return defer.succeed(None)
        sched.addBuildsetForChanges = addBuildsetForChanges

        # see self.assertConsumingChanges
        self.consumingChanges = None
        def startConsumingChanges(**kwargs):
            self.consumingChanges = kwargs
            return defer.succeed(None)
        sched.startConsumingChanges = startConsumingChanges

        return sched

    def setUp(self):
        self.setUpScheduler()

    def tearDown(self):
        self.tearDownScheduler()

    def assertConsumingChanges(self, **kwargs):
        self.assertEqual(self.consumingChanges, kwargs)

    ## Tests

    def test_constructor_change_filter(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                branch=None, change_filter=filter.ChangeFilter(category_re="fo+o"))
        assert sched.change_filter

    def test_constructor_no_branch(self):
        self.assertRaises(AssertionError,
            lambda : self.makeScheduler(name='test', builderNames=['test'],
                change_filter=filter.ChangeFilter(category_re="fo+o")))

    ## end-to-end tests: let's see the scheduler in action

    def test_iterations_simple(self):
        # note that Nightly works in local time, but the task.Clock() always
        # starts at midnight UTC, so be careful not to use times that are
        # timezone dependent -- stick to minutes-past-the-half-hour, as some
        # timezones are multiples of 30 minutes off from UTC
        sched = self.makeScheduler(name='test', builderNames=[ 'test' ], branch=None,
                        minute=[10, 20, 21, 40, 50, 51])

        # add a change classification
        self.db.schedulers.fakeClassifications(self.SCHEDULERID,
                                                            { 19 : True })

        sched.startService()

        # check that the classification has been flushed, since this
        # invocation has not requested onlyIfChanged
        self.db.schedulers.assertClassifications(self.SCHEDULERID, {})

        self.clock.advance(0) # let it get set up
        while self.clock.seconds() < 30*60: # run for 30 minutes
            self.clock.advance(60)
        self.assertEqual(self.events, [ 'B(None)@600', 'B(None)@1200', 'B(None)@1260' ])
        self.db.state.assertStateByClass('test', 'Nightly', last_build=1260)

        d = sched.stopService()
        return d

    def test_iterations_simple_with_branch(self):
        # see timezone warning above
        sched = self.makeScheduler(name='test', builderNames=[ 'test' ],
                branch='master', minute=[5, 35])

        sched.startService()

        self.clock.advance(0)
        while self.clock.seconds() < 10*60: # run for 10 minutes
            self.clock.advance(60)
        self.assertEqual(self.events, [ 'B(master)@300' ])
        self.db.state.assertStateByClass('test', 'Nightly', last_build=300)

        d = sched.stopService()
        return d

    def do_test_iterations_onlyIfChanged(self, *changes_at):
        fII = mock.Mock(name='fII')
        sched = self.makeScheduler(name='test', builderNames=[ 'test' ], branch=None,
                        minute=[5, 25, 45], onlyIfChanged=True,
                        fileIsImportant=fII)

        sched.startService()

        # check that the scheduler has started to consume changes
        self.assertConsumingChanges(fileIsImportant=fII, change_filter=None,
                                    onlyImportant=False)

        # manually run the clock forward through a half-hour, allowing any
        # excitement to take place
        changes_at = list(changes_at)
        self.clock.advance(0) # let it trigger the first build
        while self.clock.seconds() < 30*60:
            # inject any new changes..
            while changes_at and self.clock.seconds() >= changes_at[0][0]:
                when, newchange, important = changes_at.pop(0)
                self.sched.gotChange(newchange, important).addErrback(log.err)
            # and advance the clock by a minute
            self.clock.advance(60)

    def test_iterations_onlyIfChanged_no_changes(self):
        self.do_test_iterations_onlyIfChanged()
        self.assertEqual(self.events, [])
        self.db.state.assertStateByClass('test', 'Nightly', last_build=1500)
        return self.sched.stopService()

    def test_iterations_onlyIfChanged_unimp_changes(self):
        self.do_test_iterations_onlyIfChanged(
                (60, mock.Mock(), False),
                (600, mock.Mock(), False))
        self.assertEqual(self.events, [])
        self.db.state.assertStateByClass('test', 'Nightly', last_build=1500)
        return self.sched.stopService()

    def test_iterations_onlyIfChanged_off_branch_changes(self):
        self.do_test_iterations_onlyIfChanged(
                (60, self.makeFakeChange(branch='testing'), True),
                (1700, self.makeFakeChange(branch='staging'), True))
        self.assertEqual(self.events, [])
        self.db.state.assertStateByClass('test', 'Nightly', last_build=1500)
        return self.sched.stopService()

    def test_iterations_onlyIfChanged_mixed_changes(self):
        self.do_test_iterations_onlyIfChanged(
                (120, self.makeFakeChange(number=3, branch=None), False),
                (130, self.makeFakeChange(number=4, branch='offbranch'), True),
                (1200, self.makeFakeChange(number=5, branch=None), True),
                (1201, self.makeFakeChange(number=6, branch=None), False),
                (1202, self.makeFakeChange(number=7, branch='offbranch'), True))
        # note that the changeid list includes the unimportant changes, but not the
        # off-branch changes, and note that no build took place at 300s, as no important
        # changes had yet arrived
        self.assertEqual(self.events, [ 'B[3,5,6]@1500' ])
        self.db.state.assertStateByClass('test', 'Nightly', last_build=1500)
        return self.sched.stopService()
