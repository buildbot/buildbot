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
                minute=[5], codebases={'cb':{'repository':'annoying'}})

        sched.startService()

        sched.trigger({'cb':
            dict(revision='myrev',
                branch='br', project='p', repository='r'),
            }, set_props=None)

        self.clock.advance(60*60) # Run for 1h

        self.db.buildsets.assertBuildset('?',
                dict(external_idstring=None,
                     properties=[
                         ('scheduler', ('test', 'Scheduler')),
                     ],
                     reason="The NightlyTriggerable scheduler named 'test' triggered this build",
                     sourcestampsetid=100),
                {'cb':
                 dict(branch='br', project='p', repository='r', codebase='cb',
                     revision='myrev', sourcestampsetid=100)
                })


    def test_timer_twoTriggers(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                minute=[5], codebases={'cb':{'repository':'annoying'}})

        sched.startService()

        sched.trigger({ 'cb':
            dict(revision='myrev1', branch='br', project='p', repository='r')
            } , set_props=None)
        sched.trigger({ 'cb':
            dict(revision='myrev2', branch='br', project='p', repository='r')
            } , set_props=None)

        self.clock.advance(60*60) # Run for 1h

        self.db.buildsets.assertBuildset('?',
                dict(external_idstring=None,
                     properties=[
                         ('scheduler', ('test', 'Scheduler')),
                     ],
                     reason="The NightlyTriggerable scheduler named 'test' triggered this build",
                     sourcestampsetid=100),
                {'cb':
                 dict(branch='br', project='p', repository='r', codebase='cb',
                     revision='myrev2', sourcestampsetid=100)
                })


    def test_timer_oneTrigger_then_noBuild(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                minute=[5], codebases={'cb':{'repository':'annoying'}})

        sched.startService()

        sched.trigger({ 'cb':
            dict(revision='myrev', branch='br', project='p', repository='r')
            } , set_props=None)

        self.clock.advance(60*60) # Run for 1h

        self.db.buildsets.assertBuildset('?',
                dict(external_idstring=None,
                     properties=[
                         ('scheduler', ('test', 'Scheduler')),
                     ],
                     reason="The NightlyTriggerable scheduler named 'test' triggered this build",
                     sourcestampsetid=100),
                {'cb':
                 dict(branch='br', project='p', repository='r', codebase='cb',
                     revision='myrev', sourcestampsetid=100)
                })

        self.db.buildsets.flushBuildsets()

        self.clock.advance(60*60) # Run for 1h

        self.db.buildsets.assertBuildsets(0)


    def test_timer_oneTriggers_then_oneTrigger(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                minute=[5], codebases={'cb':{'repository':'annoying'}})

        sched.startService()

        sched.trigger({ 'cb':
            dict(revision='myrev1', branch='br', project='p', repository='r')
            } , set_props=None)

        self.clock.advance(60*60) # Run for 1h

        self.db.buildsets.assertBuildset('?',
                dict(external_idstring=None,
                     properties=[
                         ('scheduler', ('test', 'Scheduler')),
                     ],
                     reason="The NightlyTriggerable scheduler named 'test' triggered this build",
                     sourcestampsetid=100),
                {'cb':
                 dict(branch='br', project='p', repository='r', codebase='cb',
                     revision='myrev1', sourcestampsetid=100)
                })
        self.db.buildsets.flushBuildsets()

        sched.trigger({ 'cb':
            dict(revision='myrev2', branch='br', project='p', repository='r')
            } , set_props=None)

        self.clock.advance(60*60) # Run for 1h

        self.db.buildsets.assertBuildset('?',
                dict(external_idstring=None,
                     properties=[
                         ('scheduler', ('test', 'Scheduler')),
                     ],
                     reason="The NightlyTriggerable scheduler named 'test' triggered this build",
                     sourcestampsetid=101),
                {'cb':
                 dict(branch='br', project='p', repository='r', codebase='cb',
                     revision='myrev2', sourcestampsetid=101)
                })

    def test_savedTrigger(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                minute=[5], codebases={'cb':{'repository':'annoying'}})
        self.db.insertTestData([
            fakedb.Object(id=self.SCHEDULERID, name='test', class_name='NightlyTriggerable'),
            fakedb.ObjectState(objectid=self.SCHEDULERID, name='lastTrigger',
                value_json='[ {"cb": {"project": "p", "repository": "r", "branch": "br", "revision": "myrev"}} , {} ]'),
        ])

        sched.startService()

        self.clock.advance(60*60) # Run for 1h

        self.db.buildsets.assertBuildset('?',
                dict(external_idstring=None,
                     properties=[
                         ('scheduler', ('test', 'Scheduler')),
                     ],
                     reason="The NightlyTriggerable scheduler named 'test' triggered this build",
                     sourcestampsetid=100),
                {'cb':
                 dict(branch='br', project='p', repository='r', codebase='cb',
                     revision='myrev', sourcestampsetid=100)
                })

    def test_saveTrigger(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                minute=[5], codebases={'cb':{'repository':'annoying'}})
        self.db.insertTestData([
            fakedb.Object(id=self.SCHEDULERID, name='test', class_name='NightlyTriggerable'),
        ])

        sched.startService()

        d = sched.trigger({'cb':
            dict(revision='myrev',
                branch='br', project='p', repository='r'),
            }, set_props=None)

        @d.addCallback
        def cb(_):
            self.db.state.assertState(self.SCHEDULERID, lastTrigger=[{'cb':
                dict(revision='myrev',
                    branch='br', project='p', repository='r'),
            }, {}])

        return d

    def test_saveTrigger_noTrigger(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                minute=[5], codebases={'cb':{'repository':'annoying'}})
        self.db.insertTestData([
            fakedb.Object(id=self.SCHEDULERID, name='test', class_name='NightlyTriggerable'),
        ])

        sched.startService()

        d = sched.trigger({'cb':
            dict(revision='myrev',
                branch='br', project='p', repository='r'),
            }, set_props=None)

        self.clock.advance(60*60) # Run for 1h

        @d.addCallback
        def cb(_):
            self.db.state.assertState(self.SCHEDULERID, lastTrigger=None)

        return d

    def test_triggerProperties(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                minute=[5], codebases={'cb':{'repository':'annoying'}})
        self.db.insertTestData([
            fakedb.Object(id=self.SCHEDULERID, name='test', class_name='NightlyTriggerable'),
        ])

        sched.startService()

        sched.trigger({'cb':
            dict(revision='myrev',
                branch='br', project='p', repository='r'),
            }, properties.Properties(testprop='test'))

        self.db.state.assertState(self.SCHEDULERID, lastTrigger=[{'cb':
            dict(revision='myrev',
                branch='br', project='p', repository='r'),
            }, {'testprop': ['test', 'TEST']}])

        self.clock.advance(60*60) # Run for 1h

        self.db.buildsets.assertBuildset('?',
                dict(external_idstring=None,
                     properties=[
                         ('scheduler', ('test', 'Scheduler')),
                         ('testprop', ('test', 'TEST')),
                     ],
                     reason="The NightlyTriggerable scheduler named 'test' triggered this build",
                     sourcestampsetid=100),
                {'cb':
                 dict(branch='br', project='p', repository='r', codebase='cb',
                     revision='myrev', sourcestampsetid=100)
                })

    def test_savedProperties(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                minute=[5], codebases={'cb':{'repository':'annoying'}})
        self.db.insertTestData([
            fakedb.Object(id=self.SCHEDULERID, name='test', class_name='NightlyTriggerable'),
            fakedb.ObjectState(objectid=self.SCHEDULERID, name='lastTrigger',
                value_json='[ {"cb": {"project": "p", "repository": "r", "branch": "br", "revision": "myrev"}} , {"testprop": ["test", "TEST"]} ]'),
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
                     sourcestampsetid=100),
                {'cb':
                 dict(branch='br', project='p', repository='r', codebase='cb',
                     revision='myrev', sourcestampsetid=100)
                })
