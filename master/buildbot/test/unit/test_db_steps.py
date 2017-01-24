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
from future.builtins import range

import time

from twisted.internet import defer
from twisted.internet import task
from twisted.trial import unittest

from buildbot.db import steps
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import connector_component
from buildbot.test.util import interfaces
from buildbot.test.util import validation
from buildbot.util import epoch2datetime

TIME1 = 1304262222
TIME2 = 1304262223
TIME3 = 1304262224
TIME4 = 1304262235


class Tests(interfaces.InterfaceTests):

    # common sample data

    backgroundData = [
        fakedb.Worker(id=47, name='linux'),
        fakedb.Buildset(id=20),
        fakedb.Builder(id=88, name='b1'),
        fakedb.BuildRequest(id=41, buildsetid=20, builderid=88),
        fakedb.Master(id=88),
        fakedb.Build(id=30, buildrequestid=41, number=7, masterid=88,
                     builderid=88, workerid=47),
        fakedb.Build(id=31, buildrequestid=41, number=8, masterid=88,
                     builderid=88, workerid=47),
    ]
    stepRows = [
        fakedb.Step(id=70, number=0, name='one', buildid=30,
                    started_at=TIME1, complete_at=TIME2,
                    state_string=u'test', results=0),
        fakedb.Step(id=71, number=1, name='two', buildid=30,
                    started_at=TIME2, complete_at=TIME3,
                    state_string=u'test', results=2,
                    urls_json=u'["http://url"]',
                    hidden=1),
        fakedb.Step(id=72, number=2, name='three', buildid=30,
                    started_at=TIME3),
        fakedb.Step(id=73, number=0, name='wrong-build', buildid=31),
    ]
    stepDicts = [
        {'id': 70, 'buildid': 30, 'number': 0, 'name': u'one',
         'results': 0,
         'started_at': epoch2datetime(TIME1),
         'complete_at': epoch2datetime(TIME2),
         'state_string': u'test',
         'urls': [],
         'hidden': False},
        {'id': 71, 'buildid': 30, 'number': 1, 'name': u'two',
         'results': 2,
         'started_at': epoch2datetime(TIME2),
         'complete_at': epoch2datetime(TIME3),
         'state_string': u'test',
         'urls': [u'http://url'],
         'hidden': True},
        {'id': 72, 'buildid': 30, 'number': 2, 'name': u'three',
         'results': None,
         'started_at': epoch2datetime(TIME3),
         'complete_at': None,
         'state_string': u'',
         'urls': [],
         'hidden': False},
    ]

    # signature tests

    def test_signature_getStep(self):
        @self.assertArgSpecMatches(self.db.steps.getStep)
        def getStep(self, stepid=None, buildid=None, number=None, name=None):
            pass

    def test_signature_getSteps(self):
        @self.assertArgSpecMatches(self.db.steps.getSteps)
        def getSteps(self, buildid):
            pass

    def test_signature_addStep(self):
        @self.assertArgSpecMatches(self.db.steps.addStep)
        def addStep(self, buildid, name, state_string):
            pass

    def test_signature_startStep(self):
        @self.assertArgSpecMatches(self.db.steps.startStep)
        def addStep(self, stepid):
            pass

    def test_signature_setStepStateString(self):
        @self.assertArgSpecMatches(self.db.steps.setStepStateString)
        def setStepStateString(self, stepid, state_string):
            pass

    def test_signature_finishStep(self):
        @self.assertArgSpecMatches(self.db.steps.finishStep)
        def finishStep(self, stepid, results, hidden):
            pass

    # method tests

    @defer.inlineCallbacks
    def test_getStep(self):
        yield self.insertTestData(self.backgroundData + [self.stepRows[0]])
        stepdict = yield self.db.steps.getStep(70)
        validation.verifyDbDict(self, 'stepdict', stepdict)
        self.assertEqual(stepdict, self.stepDicts[0])

    @defer.inlineCallbacks
    def test_getStep_missing(self):
        stepdict = yield self.db.steps.getStep(50)
        self.assertEqual(stepdict, None)

    @defer.inlineCallbacks
    def test_getStep_number(self):
        yield self.insertTestData(self.backgroundData + [self.stepRows[1]])
        stepdict = yield self.db.steps.getStep(buildid=30, number=1)
        validation.verifyDbDict(self, 'stepdict', stepdict)
        self.assertEqual(stepdict['id'], 71)

    @defer.inlineCallbacks
    def test_getStep_number_missing(self):
        yield self.insertTestData(self.backgroundData + [self.stepRows[1]])
        stepdict = yield self.db.steps.getStep(buildid=30, number=9)
        self.assertEqual(stepdict, None)

    @defer.inlineCallbacks
    def test_getStep_name(self):
        yield self.insertTestData(self.backgroundData + [self.stepRows[2]])
        stepdict = yield self.db.steps.getStep(buildid=30,
                                               name='three')
        validation.verifyDbDict(self, 'stepdict', stepdict)
        self.assertEqual(stepdict['id'], 72)

    @defer.inlineCallbacks
    def test_getStep_name_missing(self):
        yield self.insertTestData(self.backgroundData + [self.stepRows[2]])
        stepdict = yield self.db.steps.getStep(buildid=30, name='five')
        self.assertEqual(stepdict, None)

    def test_getStep_invalid(self):
        d = self.db.steps.getStep(buildid=30)
        self.assertFailure(d, RuntimeError)

    @defer.inlineCallbacks
    def test_getSteps(self):
        yield self.insertTestData(self.backgroundData + self.stepRows)
        stepdicts = yield self.db.steps.getSteps(buildid=30)
        [validation.verifyDbDict(self, 'stepdict', stepdict)
         for stepdict in stepdicts]
        self.assertEqual(stepdicts, self.stepDicts[:3])

    @defer.inlineCallbacks
    def test_getSteps_none(self):
        yield self.insertTestData(self.backgroundData + self.stepRows)
        stepdicts = yield self.db.steps.getSteps(buildid=33)
        self.assertEqual(stepdicts, [])

    @defer.inlineCallbacks
    def test_addStep_getStep(self):
        clock = task.Clock()
        clock.advance(TIME1)
        yield self.insertTestData(self.backgroundData)
        stepid, number, name = yield self.db.steps.addStep(buildid=30,
                                                           name=u'new', state_string=u'new')
        yield self.db.steps.startStep(stepid=stepid, _reactor=clock)
        self.assertEqual((number, name), (0, 'new'))
        stepdict = yield self.db.steps.getStep(stepid=stepid)
        validation.verifyDbDict(self, 'stepdict', stepdict)
        self.assertEqual(stepdict, {
            'id': stepid,
            'buildid': 30,
            'name': u'new',
            'number': 0,
            'started_at': epoch2datetime(TIME1),
            'complete_at': None,
            'results': None,
            'state_string': u'new',
            'urls': [],
            'hidden': False})

    @defer.inlineCallbacks
    def test_addStep_getStep_existing_step(self):
        clock = task.Clock()
        clock.advance(TIME1)
        yield self.insertTestData(self.backgroundData + [self.stepRows[0]])
        stepid, number, name = yield self.db.steps.addStep(
            buildid=30, name=u'new', state_string=u'new')
        yield self.db.steps.startStep(stepid=stepid, _reactor=clock)
        self.assertEqual((number, name), (1, 'new'))
        stepdict = yield self.db.steps.getStep(stepid=stepid)
        validation.verifyDbDict(self, 'stepdict', stepdict)
        self.assertEqual(stepdict['number'], number)
        self.assertEqual(stepdict['name'], name)

    @defer.inlineCallbacks
    def test_addStep_getStep_name_collisions(self):
        clock = task.Clock()
        clock.advance(TIME1)
        yield self.insertTestData(self.backgroundData + [
            fakedb.Step(id=73, number=0, name=u'new', buildid=30),
            fakedb.Step(id=74, number=1, name=u'new_1', buildid=30),
            fakedb.Step(id=75, number=2, name=u'new_2', buildid=30),
            fakedb.Step(id=76, number=3, name=u'new_step', buildid=30),
        ])
        stepid, number, name = yield self.db.steps.addStep(
            buildid=30, name=u'new', state_string=u'new')
        yield self.db.steps.startStep(stepid=stepid, _reactor=clock)
        self.assertEqual((number, name), (4, u'new_3'))
        stepdict = yield self.db.steps.getStep(stepid=stepid)
        validation.verifyDbDict(self, 'stepdict', stepdict)
        self.assertEqual(stepdict['number'], number)
        self.assertEqual(stepdict['name'], name)

    @defer.inlineCallbacks
    def test_setStepStateString(self):
        yield self.insertTestData(self.backgroundData + [self.stepRows[2]])
        yield self.db.steps.setStepStateString(stepid=72,
                                               state_string=u'aaa')
        stepdict = yield self.db.steps.getStep(stepid=72)
        self.assertEqual(stepdict['state_string'], u'aaa')

    @defer.inlineCallbacks
    def test_addURL(self):
        yield self.insertTestData(self.backgroundData + [self.stepRows[2]])
        yield self.db.steps.addURL(stepid=72, name=u'foo', url=u'bar')

        stepdict = yield self.db.steps.getStep(stepid=72)
        self.assertEqual(stepdict['urls'], [{'name': u'foo', 'url': u'bar'}])

    @defer.inlineCallbacks
    def test_addURL_race(self):
        yield self.insertTestData(self.backgroundData + [self.stepRows[2]])
        yield defer.gatherResults([
            # only a tiny sleep is required to see the problem.
            self.db.steps.addURL(stepid=72, name=u'foo', url=u'bar',
                                 _racehook=lambda: time.sleep(.01)),
            self.db.steps.addURL(stepid=72, name=u'foo2', url=u'bar2')])

        stepdict = yield self.db.steps.getStep(stepid=72)

        def urlKey(url):
            return url['name']

        # order is not guaranteed though
        self.assertEqual(sorted(stepdict['urls'], key=urlKey),
                         sorted([{'name': u'foo', 'url': u'bar'},
                                 {'name': u'foo2', 'url': u'bar2'}],
                                key=urlKey))

    @defer.inlineCallbacks
    def test_finishStep(self):
        clock = task.Clock()
        clock.advance(TIME2)
        yield self.insertTestData(self.backgroundData + [self.stepRows[2]])
        yield self.db.steps.finishStep(stepid=72, results=11, hidden=False,
                                       _reactor=clock)
        stepdict = yield self.db.steps.getStep(stepid=72)
        self.assertEqual(stepdict['results'], 11)
        self.assertEqual(stepdict['complete_at'], epoch2datetime(TIME2))
        self.assertEqual(stepdict['hidden'], False)

    @defer.inlineCallbacks
    def test_finishStep_hidden(self):
        yield self.insertTestData(self.backgroundData + [self.stepRows[2]])
        yield self.db.steps.finishStep(stepid=72, results=11, hidden=True)
        stepdict = yield self.db.steps.getStep(stepid=72)
        self.assertEqual(stepdict['hidden'], True)


class RealTests(Tests):

    # the fake connector doesn't deal with this edge case

    @defer.inlineCallbacks
    def test_addStep_getStep_name_collisions_too_long(self):
        clock = task.Clock()
        clock.advance(TIME1)
        yield self.insertTestData(self.backgroundData + [
            fakedb.Step(id=73, number=0, name=u'a' * 49, buildid=30),
            fakedb.Step(id=74, number=1, name=u'a' * 48 + '_1', buildid=30),
        ])
        stepid, number, name = yield self.db.steps.addStep(
            buildid=30, name=u'a' * 49, state_string=u'new')
        yield self.db.steps.startStep(stepid=stepid, _reactor=clock)
        self.assertEqual((number, name), (2, u'a' * 48 + '_2'))
        stepdict = yield self.db.steps.getStep(stepid=stepid)
        validation.verifyDbDict(self, 'stepdict', stepdict)
        self.assertEqual(stepdict['number'], number)
        self.assertEqual(stepdict['name'], name)

    @defer.inlineCallbacks
    def test_addStep_getStep_name_collisions_too_long_extra_digits(self):
        clock = task.Clock()
        clock.advance(TIME1)
        yield self.insertTestData(self.backgroundData + [
            fakedb.Step(id=73, number=0, name=u'a' * 50, buildid=30),
        ] + [fakedb.Step(id=73 + i, number=i, name=u'a' * 48 + ('_%d' % i), buildid=30)
             for i in range(1, 10)
             ] + [fakedb.Step(id=73 + i, number=i, name=u'a' * 47 + ('_%d' % i), buildid=30)
                  for i in range(10, 100)
                  ])
        stepid, number, name = yield self.db.steps.addStep(
            buildid=30, name=u'a' * 50, state_string=u'new')
        yield self.db.steps.startStep(stepid=stepid, _reactor=clock)
        self.assertEqual((number, name), (100, u'a' * 46 + '_100'))
        stepdict = yield self.db.steps.getStep(stepid=stepid)
        validation.verifyDbDict(self, 'stepdict', stepdict)
        self.assertEqual(stepdict['number'], number)
        self.assertEqual(stepdict['name'], name)


class TestFakeDB(unittest.TestCase, Tests):

    def setUp(self):
        self.master = fakemaster.make_master(wantDb=True, testcase=self)
        self.db = self.master.db
        self.db.checkForeignKeys = True
        self.insertTestData = self.db.insertTestData


class TestRealDB(unittest.TestCase,
                 connector_component.ConnectorComponentMixin,
                 RealTests):

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['steps', 'builds', 'builders', 'masters',
                         'buildrequests', 'buildsets', 'workers'])

        @d.addCallback
        def finish_setup(_):
            self.db.steps = steps.StepsConnectorComponent(self.db)
        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()
