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

from buildbot.db import steps
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import connector_component
from buildbot.test.util import interfaces
from buildbot.test.util import validation
from buildbot.util import epoch2datetime
from twisted.internet import defer
from twisted.internet import task
from twisted.trial import unittest

TIME1 = 1304262222
TIME2 = 1304262223
TIME3 = 1304262224
TIME4 = 1304262235


class Tests(interfaces.InterfaceTests):

    # common sample data

    backgroundData = [
        fakedb.Buildslave(id=47, name='linux'),
        fakedb.Buildset(id=20),
        fakedb.Builder(id=88, name='b1'),
        fakedb.BuildRequest(id=41, buildsetid=20, buildername='b1'),
        fakedb.Master(id=88),
        fakedb.Build(id=30, buildrequestid=41, number=7, masterid=88,
                     builderid=88, buildslaveid=47),
        fakedb.Build(id=31, buildrequestid=41, number=8, masterid=88,
                     builderid=88, buildslaveid=47),
    ]
    stepRows = [
        fakedb.Step(id=70, number=0, name='one', buildid=30,
                    started_at=TIME1, complete_at=TIME2,
                    state_strings_json=u'["test"]', results=0),
        fakedb.Step(id=71, number=1, name='two', buildid=30,
                    started_at=TIME2, complete_at=TIME3,
                    state_strings_json=u'["test"]', results=2,
                    urls_json=u'["http://url"]'),
        fakedb.Step(id=72, number=2, name='three', buildid=30,
                    started_at=TIME3),
        fakedb.Step(id=73, number=0, name='wrong-build', buildid=31),
    ]
    stepDicts = [
        {'id': 70, 'buildid': 30, 'number': 0, 'name': u'one',
         'results': 0,
         'started_at': epoch2datetime(TIME1),
         'complete_at': epoch2datetime(TIME2),
         'state_strings': [u'test'],
         'urls': []},
        {'id': 71, 'buildid': 30, 'number': 1, 'name': u'two',
         'results': 2,
         'started_at': epoch2datetime(TIME2),
         'complete_at': epoch2datetime(TIME3),
         'state_strings': [u'test'],
         'urls': [u'http://url']},
        {'id': 72, 'buildid': 30, 'number': 2, 'name': u'three',
         'results': None,
         'started_at': epoch2datetime(TIME3),
         'complete_at': None,
         'state_strings': [],
         'urls': []},
    ]

    # signature tests

    def test_signature_getStep(self):
        @self.assertArgSpecMatches(self.db.steps.getStep)
        def getStep(self, stepid):
            pass

    def test_signature_getStepByBuild(self):
        @self.assertArgSpecMatches(self.db.steps.getStepByBuild)
        def getStep(self, buildid, number=None, name=None):
            pass

    def test_signature_getSteps(self):
        @self.assertArgSpecMatches(self.db.steps.getSteps)
        def getSteps(self, buildid):
            pass

    def test_signature_addStep(self):
        @self.assertArgSpecMatches(self.db.steps.addStep)
        def addStep(self, buildid, name, state_strings):
            pass

    def test_signature_startStep(self):
        @self.assertArgSpecMatches(self.db.steps.startStep)
        def addStep(self, stepid):
            pass

    def test_signature_setStepStateStrings(self):
        @self.assertArgSpecMatches(self.db.steps.setStepStateStrings)
        def setStepStateStrings(self, stepid, state_strings):
            pass

    def test_signature_finishStep(self):
        @self.assertArgSpecMatches(self.db.steps.finishStep)
        def finishStep(self, stepid, results):
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
    def test_getStepByBuild_number(self):
        yield self.insertTestData(self.backgroundData + [self.stepRows[1]])
        stepdict = yield self.db.steps.getStepByBuild(buildid=30, number=1)
        validation.verifyDbDict(self, 'stepdict', stepdict)
        self.assertEqual(stepdict['id'], 71)

    @defer.inlineCallbacks
    def test_getStepByBuild_number_missing(self):
        yield self.insertTestData(self.backgroundData + [self.stepRows[1]])
        stepdict = yield self.db.steps.getStepByBuild(buildid=30, number=9)
        self.assertEqual(stepdict, None)

    @defer.inlineCallbacks
    def test_getStepByBuild_name(self):
        yield self.insertTestData(self.backgroundData + [self.stepRows[2]])
        stepdict = yield self.db.steps.getStepByBuild(buildid=30,
                                                      name='three')
        validation.verifyDbDict(self, 'stepdict', stepdict)
        self.assertEqual(stepdict['id'], 72)

    @defer.inlineCallbacks
    def test_getStepByBuild_name_missing(self):
        yield self.insertTestData(self.backgroundData + [self.stepRows[2]])
        stepdict = yield self.db.steps.getStepByBuild(buildid=30, name='five')
        self.assertEqual(stepdict, None)

    def test_getStepByBuild_invalid(self):
        d = self.db.steps.getStepByBuild(buildid=30)
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
                                                           name=u'new', state_strings=[u'new'])
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
            'state_strings': [u'new'],
            'urls': []})

    @defer.inlineCallbacks
    def test_addStep_getStep_existing_step(self):
        clock = task.Clock()
        clock.advance(TIME1)
        yield self.insertTestData(self.backgroundData + [self.stepRows[0]])
        stepid, number, name = yield self.db.steps.addStep(buildid=30,
                                                           name=u'new', state_strings=[u'new'])
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
        stepid, number, name = yield self.db.steps.addStep(buildid=30,
                                                           name=u'new', state_strings=[u'new'])
        yield self.db.steps.startStep(stepid=stepid, _reactor=clock)
        self.assertEqual((number, name), (4, u'new_3'))
        stepdict = yield self.db.steps.getStep(stepid=stepid)
        validation.verifyDbDict(self, 'stepdict', stepdict)
        self.assertEqual(stepdict['number'], number)
        self.assertEqual(stepdict['name'], name)

    @defer.inlineCallbacks
    def test_setStepStateStrings(self):
        yield self.insertTestData(self.backgroundData + [self.stepRows[2]])
        yield self.db.steps.setStepStateStrings(stepid=72,
                                                state_strings=[u'aaa', u'bbb'])
        stepdict = yield self.db.steps.getStep(stepid=72)
        self.assertEqual(stepdict['state_strings'], [u'aaa', u'bbb'])

    @defer.inlineCallbacks
    def test_finishStep(self):
        clock = task.Clock()
        clock.advance(TIME2)
        yield self.insertTestData(self.backgroundData + [self.stepRows[2]])
        yield self.db.steps.finishStep(stepid=72, results=11, _reactor=clock)
        stepdict = yield self.db.steps.getStep(stepid=72)
        self.assertEqual(stepdict['results'], 11)
        self.assertEqual(stepdict['complete_at'], epoch2datetime(TIME2))


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
        stepid, number, name = yield self.db.steps.addStep(buildid=30,
                                                           name=u'a' * 49, state_strings=[u'new'])
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
        stepid, number, name = yield self.db.steps.addStep(buildid=30,
                                                           name=u'a' * 50, state_strings=[u'new'])
        yield self.db.steps.startStep(stepid=stepid, _reactor=clock)
        self.assertEqual((number, name), (100, u'a' * 46 + '_100'))
        stepdict = yield self.db.steps.getStep(stepid=stepid)
        validation.verifyDbDict(self, 'stepdict', stepdict)
        self.assertEqual(stepdict['number'], number)
        self.assertEqual(stepdict['name'], name)


class TestFakeDB(unittest.TestCase, Tests):

    def setUp(self):
        self.master = fakemaster.make_master()
        self.db = fakedb.FakeDBConnector(self.master, self)
        self.insertTestData = self.db.insertTestData


class TestRealDB(unittest.TestCase,
                 connector_component.ConnectorComponentMixin,
                 RealTests):

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['steps', 'builds', 'builders', 'masters',
                         'buildrequests', 'buildsets', 'buildslaves'])

        @d.addCallback
        def finish_setup(_):
            self.db.steps = steps.StepsConnectorComponent(self.db)
        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()
