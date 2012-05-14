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
from buildbot.process import properties
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
            fakedb.SourceStampSet(id=1091),
            fakedb.SourceStamp(id=91, sourcestampsetid=1091, revision='myrev',
                codebase='cb', branch='br', project='p', repository='r'),
        ])

        sched.startService()

        sched.trigger(91, set_props=None)

        self.clock.advance(60*60) # Run for 1h

        self.db.buildsets.assertBuildset('?',
                dict(external_idstring=None,
                     properties=[
                         ('scheduler', ('test', 'Scheduler')),
                     ],
                     reason="The NightlyTriggerable scheduler named 'test' triggered this build",
                     sourcestampsetid=1091),
                {'cb':
                 dict(branch='br', project='p', repository='r', codebase='cb',
                     revision='myrev', sourcestampsetid=1091)
                })


    def test_timer_twoTriggers(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                minute=[5])
        self.db.insertTestData([
            fakedb.SourceStampSet(id=1091),
            fakedb.SourceStampSet(id=1092),
            fakedb.SourceStamp(id=91, sourcestampsetid=1091, revision='myrev1',
                codebase='cb', branch='br', project='p', repository='r'),
            fakedb.SourceStamp(id=92, sourcestampsetid=1092, revision='myrev2',
                codebase='cb', branch='br', project='p', repository='r'),
        ])

        sched.startService()

        sched.trigger(91, set_props=None)
        sched.trigger(92, set_props=None)

        self.clock.advance(60*60) # Run for 1h

        self.db.buildsets.assertBuildset('?',
                dict(external_idstring=None,
                     properties=[
                         ('scheduler', ('test', 'Scheduler')),
                     ],
                     reason="The NightlyTriggerable scheduler named 'test' triggered this build",
                     sourcestampsetid=1092),
                {'cb':
                 dict(branch='br', project='p', repository='r', codebase='cb',
                     revision='myrev2', sourcestampsetid=1092)
                })


    def test_timer_oneTrigger_then_noBuild(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                minute=[5])
        self.db.insertTestData([
            fakedb.SourceStampSet(id=1091),
            fakedb.SourceStamp(id=91, sourcestampsetid=1091, revision='myrev',
                codebase='cb', branch='br', project='p', repository='r'),
        ])

        sched.startService()

        sched.trigger(91, set_props=None)

        self.clock.advance(60*60) # Run for 1h

        self.db.buildsets.assertBuildset('?',
                dict(external_idstring=None,
                     properties=[
                         ('scheduler', ('test', 'Scheduler')),
                     ],
                     reason="The NightlyTriggerable scheduler named 'test' triggered this build",
                     sourcestampsetid=1091),
                {'cb':
                 dict(branch='br', project='p', repository='r', codebase='cb',
                     revision='myrev', sourcestampsetid=1091)
                })

        self.db.buildsets.flushBuildsets()

        self.clock.advance(60*60) # Run for 1h

        self.db.buildsets.assertBuildsets(0)


    def test_timer_oneTriggers_then_oneTrigger(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                minute=[5])
        self.db.insertTestData([
            fakedb.SourceStampSet(id=1091),
            fakedb.SourceStamp(id=91, sourcestampsetid=1091, revision='myrev1',
                codebase='cb', branch='br', project='p', repository='r'),
            fakedb.SourceStampSet(id=1092),
            fakedb.SourceStamp(id=92, sourcestampsetid=1092, revision='myrev2',
                codebase='cb', branch='br', project='p', repository='r'),
        ])

        sched.startService()

        sched.trigger(91, set_props=None)

        self.clock.advance(60*60) # Run for 1h

        self.db.buildsets.assertBuildset('?',
                dict(external_idstring=None,
                     properties=[
                         ('scheduler', ('test', 'Scheduler')),
                     ],
                     reason="The NightlyTriggerable scheduler named 'test' triggered this build",
                     sourcestampsetid=1091),
                {'cb':
                 dict(branch='br', project='p', repository='r', codebase='cb',
                     revision='myrev1', sourcestampsetid=1091)
                })
        self.db.buildsets.flushBuildsets()

        sched.trigger(92, set_props=None)

        self.clock.advance(60*60) # Run for 1h

        self.db.buildsets.assertBuildset('?',
                dict(external_idstring=None,
                     properties=[
                         ('scheduler', ('test', 'Scheduler')),
                     ],
                     reason="The NightlyTriggerable scheduler named 'test' triggered this build",
                     sourcestampsetid=1092),
                {'cb':
                 dict(branch='br', project='p', repository='r', codebase='cb',
                     revision='myrev2', sourcestampsetid=1092)
                })

    def test_savedTrigger(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                minute=[5])
        self.db.insertTestData([
            fakedb.SourceStampSet(id=1091),
            fakedb.SourceStamp(id=91, sourcestampsetid=1091, revision='myrev',
               codebase='cb', branch='br', project='p', repository='r'),
            fakedb.Object(id=self.SCHEDULERID, name='test', class_name='NightlyTriggerable'),
            fakedb.ObjectState(objectid=self.SCHEDULERID, name='lastTrigger', value_json='[ 91, {} ]'),
        ])

        sched.startService()

        self.clock.advance(60*60) # Run for 1h

        self.db.buildsets.assertBuildset('?',
                dict(external_idstring=None,
                     properties=[
                         ('scheduler', ('test', 'Scheduler')),
                     ],
                     reason="The NightlyTriggerable scheduler named 'test' triggered this build",
                     sourcestampsetid=1091),
                {'cb':
                 dict(branch='br', project='p', repository='r', codebase='cb',
                     revision='myrev', sourcestampsetid=1091)
                })

    def test_saveTrigger(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                minute=[5])
        self.db.insertTestData([
            fakedb.SourceStampSet(id=1091),
            fakedb.SourceStamp(id=91, sourcestampsetid=1091, revision='myrev',
                codebase='cb', branch='br', project='p', repository='r'),
            fakedb.Object(id=self.SCHEDULERID, name='test', class_name='NightlyTriggerable'),
        ])

        sched.startService()

        d = sched.trigger(91)

        @d.addCallback
        def cb(_):
            self.db.state.assertState(self.SCHEDULERID, lastTrigger=[91, {}])

        return d

    def test_saveTrigger_noTrigger(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                minute=[5])
        self.db.insertTestData([
            fakedb.SourceStampSet(id=1091),
            fakedb.SourceStamp(id=91, sourcestampsetid=1091, revision='myrev',
                codebase='cb', branch='br', project='p', repository='r'),
            fakedb.Object(id=self.SCHEDULERID, name='test', class_name='NightlyTriggerable'),
        ])

        sched.startService()

        d = sched.trigger(91)

        self.clock.advance(60*60) # Run for 1h

        @d.addCallback
        def cb(_):
            self.db.state.assertState(self.SCHEDULERID, lastTrigger=None)

        return d

    def test_triggerProperties(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                minute=[5])
        self.db.insertTestData([
            fakedb.SourceStampSet(id=1091),
            fakedb.SourceStamp(id=91, sourcestampsetid=1091, revision='myrev',
                codebase='cb', branch='br', project='p', repository='r'),
            fakedb.Object(id=self.SCHEDULERID, name='test', class_name='NightlyTriggerable'),
        ])

        sched.startService()

        sched.trigger(91, properties.Properties(testprop='test'))

        self.db.state.assertState(self.SCHEDULERID, lastTrigger=[91, {'testprop': ['test', 'TEST']}])

        self.clock.advance(60*60) # Run for 1h

        self.db.buildsets.assertBuildset('?',
                dict(external_idstring=None,
                     properties=[
                         ('scheduler', ('test', 'Scheduler')),
                         ('testprop', ('test', 'TEST')),
                     ],
                     reason="The NightlyTriggerable scheduler named 'test' triggered this build",
                     sourcestampsetid=1091),
                {'cb':
                 dict(branch='br', project='p', repository='r', codebase='cb',
                     revision='myrev', sourcestampsetid=1091)
                })

    def test_savedProperties(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                minute=[5])
        self.db.insertTestData([
            fakedb.SourceStampSet(id=1091),
            fakedb.SourceStamp(id=91, sourcestampsetid=1091, revision='myrev',
               codebase='cb', branch='br', project='p', repository='r'),
            fakedb.Object(id=self.SCHEDULERID, name='test', class_name='NightlyTriggerable'),
            fakedb.ObjectState(objectid=self.SCHEDULERID, name='lastTrigger', value_json='[ 91, {"testprop": ["test", "TEST"]}]'),
        ])

        sched.startService()

        self.clock.advance(60*60) # Run for 1h

        self.db.buildsets.assertBuildset('?',
                dict(external_idstring=None,
                     properties=[
                         ('scheduler', ('test', 'Scheduler')),
                         ('testprop', ('test', 'TEST')),
                     ],
                     reason="The NightlyTriggerable scheduler named 'test' triggered this build",
                     sourcestampsetid=1091),
                {'cb':
                 dict(branch='br', project='p', repository='r', codebase='cb',
                     revision='myrev', sourcestampsetid=1091)
                })
