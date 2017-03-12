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

import datetime

from twisted.internet import task
from twisted.trial import unittest

from buildbot.process import properties
from buildbot.schedulers import timed
from buildbot.test.fake import fakedb
from buildbot.test.util import scheduler


class NightlyTriggerable(scheduler.SchedulerMixin, unittest.TestCase):

    try:
        datetime.datetime.fromtimestamp(1)
    except OSError:
        skip = ("Python 3.6 bug on Windows: "
                "https://bugs.python.org/issue29097")

    SCHEDULERID = 327
    OBJECTID = 1327

    def makeScheduler(self, firstBuildDuration=0, **kwargs):
        sched = self.attachScheduler(timed.NightlyTriggerable(**kwargs),
                                     self.OBJECTID, self.SCHEDULERID,
                                     overrideBuildsetMethods=True,
                                     createBuilderDB=True)

        # add a Clock to help checking timing issues
        self.clock = sched._reactor = task.Clock()

        return sched

    def setUp(self):
        self.setUpScheduler()

    def tearDown(self):
        self.tearDownScheduler()

    # utilities

    def assertBuildsetAdded(self, sourcestamps={}, properties={}):
        properties['scheduler'] = ('test', u'Scheduler')
        self.assertEqual(self.addBuildsetCalls, [
            ('addBuildsetForSourceStampsWithDefaults', dict(
                builderNames=None,  # uses the default
                properties=properties,
                reason=u"The NightlyTriggerable scheduler named 'test' "
                       u"triggered this build",
                sourcestamps=sourcestamps,
                waited_for=False)),
        ])
        self.addBuildsetCalls = []

    def assertNoBuildsetAdded(self):
        self.assertEqual(self.addBuildsetCalls, [])

    # tests

    def test_constructor_no_reason(self):
        sched = self.makeScheduler(name='test', builderNames=['test'])
        self.assertEqual(
            sched.reason, "The NightlyTriggerable scheduler named 'test' triggered this build")

    def test_constructor_reason(self):
        sched = self.makeScheduler(
            name='test', builderNames=['test'], reason="hourlytriggerable")
        self.assertEqual(sched.reason, "hourlytriggerable")

    def test_constructor_month(self):
        sched = self.makeScheduler(
            name='test', builderNames=['test'], month='1')
        self.assertEqual(sched.month, "1")

    def test_timer_noBuilds(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                                   minute=[5])

        sched.activate()
        self.clock.advance(60 * 60)  # Run for 1h

        self.assertEqual(self.addBuildsetCalls, [])

    def test_timer_oneTrigger(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                                   minute=[5], codebases={'cb': {'repository': 'annoying'}})

        sched.activate()

        sched.trigger(False, [
            dict(revision='myrev', branch='br', project='p',
                 repository='r', codebase='cb'),
        ], set_props=None)

        self.clock.advance(60 * 60)  # Run for 1h

        self.assertBuildsetAdded(sourcestamps=[
            dict(codebase='cb', branch='br', project='p', repository='r',
                 revision='myrev'),
        ])

    def test_timer_twoTriggers(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                                   minute=[5], codebases={'cb': {'repository': 'annoying'}})

        sched.activate()

        sched.trigger(False, [
            dict(codebase='cb', revision='myrev1', branch='br', project='p',
                 repository='r')
        ], set_props=None)
        sched.trigger(False, [
            dict(codebase='cb', revision='myrev2', branch='br', project='p',
                 repository='r')
        ], set_props=None)

        self.clock.advance(60 * 60)  # Run for 1h

        self.assertBuildsetAdded(sourcestamps=[
            dict(codebase='cb', branch='br', project='p', repository='r',
                 # builds the second trigger's revision
                 revision='myrev2'),
        ])

    def test_timer_oneTrigger_then_noBuild(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                                   minute=[5], codebases={'cb': {'repository': 'annoying'}})

        sched.activate()

        sched.trigger(False, [
            dict(codebase='cb', revision='myrev', branch='br', project='p',
                 repository='r')
        ], set_props=None)

        self.clock.advance(60 * 60)  # Run for 1h

        self.assertBuildsetAdded(sourcestamps=[
            dict(codebase='cb', branch='br', project='p', repository='r',
                 revision='myrev'),
        ])

        self.clock.advance(60 * 60)  # Run for 1h

        # no trigger, so the second did not build
        self.assertNoBuildsetAdded()

    def test_timer_oneTriggers_then_oneTrigger(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                                   minute=[5], codebases={'cb': {'repository': 'annoying'}})

        sched.activate()

        sched.trigger(False, [
            dict(codebase='cb', revision='myrev1', branch='br', project='p',
                 repository='r')
        ], set_props=None)

        self.clock.advance(60 * 60)  # Run for 1h

        self.assertBuildsetAdded(sourcestamps=[
            dict(codebase='cb', branch='br', project='p', repository='r',
                 revision='myrev1'),
        ])

        sched.trigger(False, [
            dict(codebase='cb', revision='myrev2', branch='br', project='p',
                 repository='r')
        ], set_props=None)

        self.clock.advance(60 * 60)  # Run for 1h

        self.assertBuildsetAdded(sourcestamps=[
            dict(codebase='cb', branch='br', project='p', repository='r',
                 revision='myrev2'),
        ])

    def test_savedTrigger(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                                   minute=[5], codebases={'cb': {'repository': 'annoying'}})
        self.db.insertTestData([
            fakedb.Object(
                id=self.SCHEDULERID, name='test', class_name='NightlyTriggerable'),
            fakedb.ObjectState(objectid=self.SCHEDULERID, name='lastTrigger',
                               value_json='[ [ {"codebase": "cb", "project": "p", "repository": "r", "branch": "br", "revision": "myrev"} ], {}, null, null ]'),
        ])

        sched.activate()

        self.clock.advance(60 * 60)  # Run for 1h

        self.assertBuildsetAdded(sourcestamps=[
            dict(codebase='cb', branch='br', project='p', repository='r',
                 revision='myrev'),
        ])

    def test_savedTrigger_dict(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                                   minute=[5], codebases={'cb': {'repository': 'annoying'}})
        self.db.insertTestData([
            fakedb.Object(
                id=self.SCHEDULERID, name='test', class_name='NightlyTriggerable'),
            fakedb.ObjectState(objectid=self.SCHEDULERID, name='lastTrigger',
                               value_json='[ { "cb": {"codebase": "cb", "project": "p", "repository": "r", "branch": "br", "revision": "myrev"} }, {}, null, null ]'),
        ])

        sched.activate()

        self.clock.advance(60 * 60)  # Run for 1h

        self.assertBuildsetAdded(sourcestamps=[
            dict(codebase='cb', branch='br', project='p', repository='r',
                 revision='myrev'),
        ])

    def test_saveTrigger(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                                   minute=[5], codebases={'cb': {'repository': 'annoying'}})
        self.db.insertTestData([
            fakedb.Object(
                id=self.SCHEDULERID, name='test', class_name='NightlyTriggerable'),
        ])

        sched.activate()

        (idsDeferred, d) = sched.trigger(False, [
            dict(codebase='cb', revision='myrev', branch='br', project='p',
                 repository='r'),
        ], set_props=None)

        @d.addCallback
        def cb(_):
            self.db.state.assertState(self.SCHEDULERID, lastTrigger=[[
                dict(codebase='cb', revision='myrev',
                     branch='br', project='p', repository='r'),
            ], {}, None, None])

        return d

    def test_saveTrigger_noTrigger(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                                   minute=[5], codebases={'cb': {'repository': 'annoying'}})
        self.db.insertTestData([
            fakedb.Object(
                id=self.SCHEDULERID, name='test', class_name='NightlyTriggerable'),
        ])

        sched.activate()

        (idsDeferre, d) = sched.trigger(False, [
            dict(codebase='cb', revision='myrev', branch='br', project='p',
                 repository='r'),
        ], set_props=None)

        self.clock.advance(60 * 60)  # Run for 1h

        @d.addCallback
        def cb(_):
            self.db.state.assertState(self.SCHEDULERID, lastTrigger=None)

        return d

    def test_triggerProperties(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                                   minute=[5], codebases={'cb': {'repository': 'annoying'}})
        self.db.insertTestData([
            fakedb.Object(
                id=self.SCHEDULERID, name='test', class_name='NightlyTriggerable'),
        ])

        sched.activate()

        sched.trigger(False, [
            dict(codebase='cb', revision='myrev', branch='br', project='p',
                 repository='r'),
        ], properties.Properties(testprop='test'))

        self.db.state.assertState(self.SCHEDULERID, lastTrigger=[[
            dict(codebase='cb', revision='myrev',
                 branch='br', project='p', repository='r'),
        ], {'testprop': ['test', 'TEST']}, None, None])

        self.clock.advance(60 * 60)  # Run for 1h

        self.assertBuildsetAdded(
            properties=dict(testprop=('test', 'TEST')),
            sourcestamps=[
                dict(codebase='cb', branch='br', project='p', repository='r',
                     revision='myrev'),
            ])

    def test_savedProperties(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                                   minute=[5], codebases={'cb': {'repository': 'annoying'}})
        self.db.insertTestData([
            fakedb.Object(
                id=self.SCHEDULERID, name='test', class_name='NightlyTriggerable'),
            fakedb.ObjectState(objectid=self.SCHEDULERID, name='lastTrigger',
                               value_json='[ [ {"codebase": "cb", "project": "p", "repository": "r", "branch": "br", "revision": "myrev"} ], {"testprop": ["test", "TEST"]}, null, null ]'),
        ])

        sched.activate()

        self.clock.advance(60 * 60)  # Run for 1h

        self.assertBuildsetAdded(
            properties={'testprop': (u'test', u'TEST')},
            sourcestamps=[
                dict(codebase='cb', branch='br', project='p', repository='r',
                     revision='myrev'),
            ])
