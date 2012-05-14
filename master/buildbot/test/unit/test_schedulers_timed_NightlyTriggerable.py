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
from twisted.internet import task
from buildbot.schedulers import timed
from buildbot.test.fake import fakedb
from buildbot.test.util import scheduler

class NightlyTriggerable(scheduler.SchedulerMixin, unittest.TestCase):

    SCHEDULERID = 1327

    def makeScheduler(self, firstBuildDuration=0, **kwargs):
        sched = self.attachScheduler(timed.NightlyTriggerable(**kwargs),
                self.SCHEDULERID)

        # add a Clock to help checking timing issues
        self.clock = sched._reactor = task.Clock()

        # keep track of builds in self.events
        #self.events = []
        #def addBuildsetForLatest(reason='', external_idstring='',
        #        branch=None, repository='', project=''):
        #    self.assertIn('scheduler named', reason)
        #    isFirst = (self.events == [])
        #    self.events.append('B(%s)@%d' % (branch,self.clock.seconds()))
        #    if isFirst and firstBuildDuration:
        #        d = defer.Deferred()
        #        self.clock.callLater(firstBuildDuration, d.callback, None)
        #        return d
        #    else:
        #        return defer.succeed(None)
        #sched.addBuildsetForLatest = addBuildsetForLatest

        #def addBuildsetForChanges(reason='', external_idstring='', changeids=[]):
        #    self.events.append('B%s@%d' % (`changeids`.replace(' ',''),
        #                                   self.clock.seconds()))
        #    return defer.succeed(None)
        #sched.addBuildsetForChanges = addBuildsetForChanges

        return sched

    def setUp(self):
        self.setUpScheduler()

    def tearDown(self):
        self.tearDownScheduler()


    def test_timer_noBuilds(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                minute=[5])

        sched.startService()
        self.clock.advance(60*60) # Run for 1h

        self.db.buildsets.assertBuildsets(0)


    def test_timer_oneTrigger(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                minute=[5])
        self.db.insertTestData([
            fakedb.SourceStamp(id=91, revision='myrev', branch='br',
                project='p', repository='r'),
        ])

        sched.startService()

        sched.trigger(91, set_props=None)

        self.clock.advance(60*60) # Run for 1h

        self.db.buildsets.assertBuildset('?',
                dict(external_idstring=None,
                    properties=[('scheduler', ('test', 'Scheduler'))],
                    reason="The NightlyTriggerable scheduler named 'test' triggered this build"),
                dict(branch='br', project='p', repository='r',
                    revision='myrev'))


    def test_timer_twoTriggers(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                minute=[5])
        self.db.insertTestData([
            fakedb.SourceStamp(id=91, revision='myrev1', branch='br',
                project='p', repository='r'),
        ])
        self.db.insertTestData([
            fakedb.SourceStamp(id=92, revision='myrev2', branch='br',
                project='p', repository='r'),
        ])

        sched.startService()

        sched.trigger(91, set_props=None)
        sched.trigger(92, set_props=None)

        self.clock.advance(60*60) # Run for 1h

        self.db.buildsets.assertBuildset('?',
                dict(external_idstring=None,
                    properties=[('scheduler', ('test', 'Scheduler'))],
                    reason="The NightlyTriggerable scheduler named 'test' triggered this build"),
                dict(branch='br', project='p', repository='r',
                    revision='myrev2'))


    def test_timer_oneTrigger_then_noBuild(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                minute=[5])
        self.db.insertTestData([
            fakedb.SourceStamp(id=91, revision='myrev', branch='br',
                project='p', repository='r'),
        ])

        sched.startService()

        sched.trigger(91, set_props=None)

        self.clock.advance(60*60) # Run for 1h

        self.db.buildsets.assertBuildset('?',
                dict(external_idstring=None,
                    properties=[('scheduler', ('test', 'Scheduler'))],
                    reason="The NightlyTriggerable scheduler named 'test' triggered this build"),
                dict(branch='br', project='p', repository='r',
                    revision='myrev'))

        self.db.buildsets.flushBuildsets()

        self.clock.advance(60*60) # Run for 1h

        self.db.buildsets.assertBuildsets(0)


    def test_timer_oneTriggers_then_oneTrigger(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                minute=[5])
        self.db.insertTestData([
            fakedb.SourceStamp(id=91, revision='myrev1', branch='br',
                project='p', repository='r'),
        ])
        self.db.insertTestData([
            fakedb.SourceStamp(id=92, revision='myrev2', branch='br',
                project='p', repository='r'),
        ])

        sched.startService()

        sched.trigger(91, set_props=None)

        self.clock.advance(60*60) # Run for 1h

        self.db.buildsets.assertBuildset('?',
                dict(external_idstring=None,
                    properties=[('scheduler', ('test', 'Scheduler'))],
                    reason="The NightlyTriggerable scheduler named 'test' triggered this build"),
                dict(branch='br', project='p', repository='r',
                    revision='myrev1'))
        self.db.buildsets.flushBuildsets()

        sched.trigger(92, set_props=None)

        self.clock.advance(60*60) # Run for 1h

        self.db.buildsets.assertBuildset('?',
                dict(external_idstring=None,
                    properties=[('scheduler', ('test', 'Scheduler'))],
                    reason="The NightlyTriggerable scheduler named 'test' triggered this build"),
                dict(branch='br', project='p', repository='r',
                    revision='myrev2'))
