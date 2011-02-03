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

import time
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

    ## detailed getNextBuildTime tests

    @defer.deferredGenerator
    def do_getNextBuildTime_test(self, sched, *expectations):
        for lastActuated, expected in expectations:
            # convert from tuples to epoch time (in local timezone)
            lastActuated_ep, expected_ep = [
                   time.mktime(t + (0,) * (8 - len(t)) + (-1,))
                   for t in (lastActuated, expected) ]
            wfd = defer.waitForDeferred(sched.getNextBuildTime(lastActuated_ep))
            yield wfd
            got_ep = wfd.getResult()
            self.assertEqual(got_ep, expected_ep,
                "%s -> %s != %s" % (lastActuated, time.localtime(got_ep), expected))

    def test_getNextBuildTime_hourly(self):
        sched = self.makeScheduler(name='test', builderNames=['test'], branch=None)
        return self.do_getNextBuildTime_test(sched,
            ((2011, 1, 1,  3,  0,  0), (2011, 1, 1,  4,  0,  0)),
            ((2011, 1, 1,  3, 15,  0), (2011, 1, 1,  4,  0,  0)),
            ((2011, 1, 1,  3, 15,  1), (2011, 1, 1,  4,  0,  0)),
            ((2011, 1, 1,  3, 59,  1), (2011, 1, 1,  4,  0,  0)),
            ((2011, 1, 1,  3, 59, 59), (2011, 1, 1,  4,  0,  0)),
            ((2011, 1, 1, 23, 22, 22), (2011, 1, 2,  0,  0,  0)),
            ((2011, 1, 1, 23, 59,  0), (2011, 1, 2,  0,  0,  0)),
        )

    def test_getNextBuildTime_minutes_single(self):
        # basically the same as .._hourly
        sched = self.makeScheduler(name='test', builderNames=['test'], branch=None,
                minute=4)
        return self.do_getNextBuildTime_test(sched,
            ((2011, 1, 1,  3,  0,  0), (2011, 1, 1,  3,  4,  0)),
            ((2011, 1, 1,  3, 15,  0), (2011, 1, 1,  4,  4,  0)),
        )

    def test_getNextBuildTime_minutes_multiple(self):
        sched = self.makeScheduler(name='test', builderNames=['test'], branch=None,
                minute=[4, 34])
        return self.do_getNextBuildTime_test(sched,
            ((2011, 1, 1,  3,  0,  0), (2011, 1, 1,  3,  4,  0)),
            ((2011, 1, 1,  3, 15,  0), (2011, 1, 1,  3, 34,  0)),
            ((2011, 1, 1,  3, 34,  0), (2011, 1, 1,  4,  4,  0)),
            ((2011, 1, 1,  3, 59,  1), (2011, 1, 1,  4,  4,  0)),
        )

    def test_getNextBuildTime_minutes_star(self):
        sched = self.makeScheduler(name='test', builderNames=['test'], branch=None,
                minute='*')
        return self.do_getNextBuildTime_test(sched,
            ((2011, 1, 1,  3, 11, 30), (2011, 1, 1,  3, 12,  0)),
            ((2011, 1, 1,  3, 12,  0), (2011, 1, 1,  3, 13,  0)),
            ((2011, 1, 1,  3, 59,  0), (2011, 1, 1,  4,  0,  0)),
        )

    def test_getNextBuildTime_hours_single(self):
        sched = self.makeScheduler(name='test', builderNames=['test'], branch=None,
                hour=4)
        return self.do_getNextBuildTime_test(sched,
            ((2011, 1, 1,  3,  0), (2011, 1, 1,  4,  0)),
            ((2011, 1, 1, 13,  0), (2011, 1, 2,  4,  0)),
        )

    def test_getNextBuildTime_hours_multiple(self):
        sched = self.makeScheduler(name='test', builderNames=['test'], branch=None,
                hour=[7, 19])
        return self.do_getNextBuildTime_test(sched,
            ((2011, 1, 1,  3,  0), (2011, 1, 1,  7,  0)),
            ((2011, 1, 1,  7,  1), (2011, 1, 1, 19,  0)),
            ((2011, 1, 1, 18, 59), (2011, 1, 1, 19,  0)),
            ((2011, 1, 1, 19, 59), (2011, 1, 2,  7,  0)),
        )

    def test_getNextBuildTime_hours_minutes(self):
        sched = self.makeScheduler(name='test', builderNames=['test'], branch=None,
                hour=13, minute=19)
        return self.do_getNextBuildTime_test(sched,
            ((2011, 1, 1,  3, 11), (2011, 1, 1, 13, 19)),
            ((2011, 1, 1, 13, 19), (2011, 1, 2, 13, 19)),
            ((2011, 1, 1, 23, 59), (2011, 1, 2, 13, 19)),
        )

    def test_getNextBuildTime_month_single(self):
        sched = self.makeScheduler(name='test', builderNames=['test'], branch=None,
                month=3)
        return self.do_getNextBuildTime_test(sched,
            ((2011, 2, 27,  3, 11), (2011, 3, 1,  0,  0)),
            ((2011, 3,  1,  1, 11), (2011, 3, 1,  2,  0)), # still hourly!
        )

    def test_getNextBuildTime_month_multiple(self):
        sched = self.makeScheduler(name='test', builderNames=['test'], branch=None,
                month=[4, 6])
        return self.do_getNextBuildTime_test(sched,
            ((2011, 3, 30,  3, 11), (2011, 4, 1,  0,  0)),
            ((2011, 4,  1,  1, 11), (2011, 4, 1,  2,  0)), # still hourly!
            ((2011, 5, 29,  3, 11), (2011, 6, 1,  0,  0)),
        )

    def test_getNextBuildTime_month_dayOfMonth(self):
        sched = self.makeScheduler(name='test', builderNames=['test'], branch=None,
                month=[3, 6], dayOfMonth=[15])
        return self.do_getNextBuildTime_test(sched,
            ((2011, 2, 12,  3, 11), (2011, 3, 15,  0,  0)),
            ((2011, 3, 12,  3, 11), (2011, 3, 15,  0,  0)),
        )

    def test_getNextBuildTime_dayOfMonth_single(self):
        sched = self.makeScheduler(name='test', builderNames=['test'], branch=None,
                dayOfMonth=10)
        return self.do_getNextBuildTime_test(sched,
            ((2011,  1,  9,  3,  0), (2011,  1, 10,  0,  0)),
            ((2011,  1, 10,  3,  0), (2011,  1, 10,  4,  0)), # still hourly!
            ((2011,  1, 30,  3,  0), (2011,  2, 10,  0,  0)),
            ((2011, 12, 30, 11,  0), (2012,  1, 10,  0,  0)),
        )

    def test_getNextBuildTime_dayOfMonth_multiple(self):
        sched = self.makeScheduler(name='test', builderNames=['test'], branch=None,
                dayOfMonth=[10, 20, 30])
        return self.do_getNextBuildTime_test(sched,
            ((2011,  1,  9, 22,  0), (2011,  1, 10,  0,  0)),
            ((2011,  1, 19, 22,  0), (2011,  1, 20,  0,  0)),
            ((2011,  1, 29, 22,  0), (2011,  1, 30,  0,  0)),
            ((2011,  2, 29, 22,  0), (2011,  3, 10,  0,  0)), # no Feb 30!
        )

    def test_getNextBuildTime_dayOfMonth_hours_minutes(self):
        sched = self.makeScheduler(name='test', builderNames=['test'], branch=None,
                dayOfMonth=15, hour=20, minute=30)
        return self.do_getNextBuildTime_test(sched,
            ((2011,  1, 13, 22, 19), (2011,  1, 15, 20, 30)),
            ((2011,  1, 15, 19, 19), (2011,  1, 15, 20, 30)),
            ((2011,  1, 15, 20, 29), (2011,  1, 15, 20, 30)),
        )

    def test_getNextBuildTime_dayOfWeek_single(self):
        sched = self.makeScheduler(name='test', builderNames=['test'], branch=None,
                dayOfWeek=1) # Tuesday (2011-1-1 was a Saturday)
        return self.do_getNextBuildTime_test(sched,
            ((2011,  1,  3, 22, 19), (2011,  1,  4,  0,  0)),
            ((2011,  1,  4, 19, 19), (2011,  1,  4, 20,  0)), # still hourly!
        )

    def test_getNextBuildTime_dayOfWeek_multiple_hours(self):
        sched = self.makeScheduler(name='test', builderNames=['test'], branch=None,
                dayOfWeek=[1,3], hour=1) # Tuesday, Thursday (2011-1-1 was a Saturday)
        return self.do_getNextBuildTime_test(sched,
            ((2011,  1,  3, 22, 19), (2011,  1,  4,  1,  0)),
            ((2011,  1,  4, 22, 19), (2011,  1,  6,  1,  0)),
        )

    def test_getNextBuildTime_dayOfWeek_dayOfMonth(self):
        sched = self.makeScheduler(name='test', builderNames=['test'], branch=None,
                dayOfWeek=[1,4], dayOfMonth=5, hour=1)
        return self.do_getNextBuildTime_test(sched,
            ((2011,  1,  3, 22, 19), (2011,  1,  4,  1,  0)), # Tues
            ((2011,  1,  4, 22, 19), (2011,  1,  5,  1,  0)), # 5th
            ((2011,  1,  5, 22, 19), (2011,  1,  7,  1,  0)), # Thurs
        )

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
        self.db.schedulers.assertState(self.SCHEDULERID, {'last_build': 1260})

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
        self.db.schedulers.assertState(self.SCHEDULERID, {'last_build': 300})

        d = sched.stopService()
        return d

    def do_test_iterations_onlyIfChanged(self, *changes_at):
        fII = mock.Mock(name='fII')
        sched = self.makeScheduler(name='test', builderNames=[ 'test' ], branch=None,
                        minute=[5, 25, 45], onlyIfChanged=True,
                        fileIsImportant=fII)

        sched.startService()

        # check that the scheduler has started to consume changes
        self.assertConsumingChanges(fileIsImportant=fII, change_filter=None)

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
        self.db.schedulers.assertState(self.SCHEDULERID, {'last_build': 1500})
        return self.sched.stopService()

    def test_iterations_onlyIfChanged_unimp_changes(self):
        self.do_test_iterations_onlyIfChanged(
                (60, mock.Mock(), False),
                (600, mock.Mock(), False))
        self.assertEqual(self.events, [])
        self.db.schedulers.assertState(self.SCHEDULERID, {'last_build': 1500})
        return self.sched.stopService()

    def test_iterations_onlyIfChanged_off_branch_changes(self):
        self.do_test_iterations_onlyIfChanged(
                (60, self.makeFakeChange(branch='testing'), True),
                (1700, self.makeFakeChange(branch='staging'), True))
        self.assertEqual(self.events, [])
        self.db.schedulers.assertState(self.SCHEDULERID, {'last_build': 1500})
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
        self.db.schedulers.assertState(self.SCHEDULERID, {'last_build': 1500})
        return self.sched.stopService()
