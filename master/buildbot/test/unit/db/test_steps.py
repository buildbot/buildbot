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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.db import steps
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.util import epoch2datetime

TIME1 = 1304262222
TIME2 = 1304262223
TIME3 = 1304262224
TIME4 = 1304262235
TIME5 = 1304262236


class Tests(TestReactorMixin, unittest.TestCase):
    # common sample data

    backgroundData = [
        fakedb.Worker(id=47, name='linux'),
        fakedb.Buildset(id=20),
        fakedb.Builder(id=88, name='b1'),
        fakedb.BuildRequest(id=41, buildsetid=20, builderid=88),
        fakedb.Master(id=88),
        fakedb.Build(id=30, buildrequestid=41, number=7, masterid=88, builderid=88, workerid=47),
        fakedb.Build(id=31, buildrequestid=41, number=8, masterid=88, builderid=88, workerid=47),
    ]
    stepRows = [
        fakedb.Step(
            id=70,
            number=0,
            name='one',
            buildid=30,
            started_at=TIME1,
            locks_acquired_at=TIME2,
            complete_at=TIME3,
            state_string='test',
            results=0,
        ),
        fakedb.Step(
            id=71,
            number=1,
            name='two',
            buildid=30,
            started_at=TIME2,
            locks_acquired_at=TIME3,
            complete_at=TIME4,
            state_string='test',
            results=2,
            urls_json='[{"name": "url", "url": "http://url"}]',
            hidden=1,
        ),
        fakedb.Step(id=72, number=2, name='three', buildid=30, started_at=TIME5),
        fakedb.Step(id=73, number=0, name='wrong-build', buildid=31),
    ]
    stepDicts = [
        steps.StepModel(
            id=70,
            buildid=30,
            number=0,
            name='one',
            results=0,
            started_at=epoch2datetime(TIME1),
            locks_acquired_at=epoch2datetime(TIME2),
            complete_at=epoch2datetime(TIME3),
            state_string='test',
            urls=[],
            hidden=False,
        ),
        steps.StepModel(
            id=71,
            buildid=30,
            number=1,
            name='two',
            results=2,
            started_at=epoch2datetime(TIME2),
            locks_acquired_at=epoch2datetime(TIME3),
            complete_at=epoch2datetime(TIME4),
            state_string='test',
            urls=[steps.UrlModel(name='url', url='http://url')],
            hidden=True,
        ),
        steps.StepModel(
            id=72,
            buildid=30,
            number=2,
            name='three',
            results=None,
            started_at=epoch2datetime(TIME5),
            locks_acquired_at=None,
            complete_at=None,
            state_string='',
            urls=[],
            hidden=False,
        ),
    ]

    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantDb=True)
        self.db = self.master.db

    @defer.inlineCallbacks
    def test_getStep(self):
        yield self.db.insert_test_data([*self.backgroundData, self.stepRows[0]])
        stepdict = yield self.db.steps.getStep(70)
        self.assertIsInstance(stepdict, steps.StepModel)
        self.assertEqual(stepdict, self.stepDicts[0])

    @defer.inlineCallbacks
    def test_getStep_missing(self):
        stepdict = yield self.db.steps.getStep(50)
        self.assertEqual(stepdict, None)

    @defer.inlineCallbacks
    def test_getStep_number(self):
        yield self.db.insert_test_data([*self.backgroundData, self.stepRows[1]])
        stepdict = yield self.db.steps.getStep(buildid=30, number=1)
        self.assertIsInstance(stepdict, steps.StepModel)
        self.assertEqual(stepdict.id, 71)

    @defer.inlineCallbacks
    def test_getStep_number_missing(self):
        yield self.db.insert_test_data([*self.backgroundData, self.stepRows[1]])
        stepdict = yield self.db.steps.getStep(buildid=30, number=9)
        self.assertEqual(stepdict, None)

    @defer.inlineCallbacks
    def test_getStep_name(self):
        yield self.db.insert_test_data([*self.backgroundData, self.stepRows[2]])
        stepdict = yield self.db.steps.getStep(buildid=30, name='three')
        self.assertIsInstance(stepdict, steps.StepModel)
        self.assertEqual(stepdict.id, 72)

    @defer.inlineCallbacks
    def test_getStep_name_missing(self):
        yield self.db.insert_test_data([*self.backgroundData, self.stepRows[2]])
        stepdict = yield self.db.steps.getStep(buildid=30, name='five')
        self.assertEqual(stepdict, None)

    @defer.inlineCallbacks
    def test_getStep_invalid(self):
        with self.assertRaises(RuntimeError):
            yield self.db.steps.getStep(buildid=30)

    @defer.inlineCallbacks
    def test_getSteps(self):
        yield self.db.insert_test_data(self.backgroundData + self.stepRows)
        stepdicts = yield self.db.steps.getSteps(buildid=30)

        for stepdict in stepdicts:
            self.assertIsInstance(stepdict, steps.StepModel)

        self.assertEqual(stepdicts, self.stepDicts[:3])

    @defer.inlineCallbacks
    def test_getSteps_none(self):
        yield self.db.insert_test_data(self.backgroundData + self.stepRows)
        stepdicts = yield self.db.steps.getSteps(buildid=33)
        self.assertEqual(stepdicts, [])

    @defer.inlineCallbacks
    def test_addStep_getStep(self):
        yield self.db.insert_test_data(self.backgroundData)
        stepid, number, name = yield self.db.steps.addStep(
            buildid=30, name='new', state_string='new'
        )
        yield self.db.steps.startStep(stepid=stepid, started_at=TIME1, locks_acquired=False)
        self.assertEqual((number, name), (0, 'new'))
        stepdict = yield self.db.steps.getStep(stepid=stepid)
        self.assertIsInstance(stepdict, steps.StepModel)
        self.assertEqual(
            stepdict,
            steps.StepModel(
                id=stepid,
                buildid=30,
                name='new',
                number=0,
                started_at=epoch2datetime(TIME1),
                locks_acquired_at=None,
                complete_at=None,
                results=None,
                state_string='new',
                urls=[],
                hidden=False,
            ),
        )

    @defer.inlineCallbacks
    def test_addStep_getStep_locks_acquired_already(self):
        yield self.db.insert_test_data(self.backgroundData)
        stepid, number, name = yield self.db.steps.addStep(
            buildid=30, name='new', state_string='new'
        )
        yield self.db.steps.startStep(stepid=stepid, started_at=TIME1, locks_acquired=True)
        self.assertEqual((number, name), (0, 'new'))
        stepdict = yield self.db.steps.getStep(stepid=stepid)
        self.assertIsInstance(stepdict, steps.StepModel)
        self.assertEqual(
            stepdict,
            steps.StepModel(
                id=stepid,
                buildid=30,
                name="new",
                number=0,
                started_at=epoch2datetime(TIME1),
                locks_acquired_at=epoch2datetime(TIME1),
                complete_at=None,
                results=None,
                state_string="new",
                urls=[],
                hidden=False,
            ),
        )

    @defer.inlineCallbacks
    def test_addStep_getStep_locks_acquired_later(self):
        yield self.db.insert_test_data(self.backgroundData)
        stepid, number, name = yield self.db.steps.addStep(
            buildid=30, name='new', state_string='new'
        )
        yield self.db.steps.startStep(stepid=stepid, started_at=TIME1, locks_acquired=False)
        yield self.db.steps.set_step_locks_acquired_at(stepid=stepid, locks_acquired_at=TIME2)
        self.assertEqual((number, name), (0, 'new'))
        stepdict = yield self.db.steps.getStep(stepid=stepid)
        self.assertIsInstance(stepdict, steps.StepModel)
        self.assertEqual(
            stepdict,
            steps.StepModel(
                id=stepid,
                buildid=30,
                name='new',
                number=0,
                started_at=epoch2datetime(TIME1),
                locks_acquired_at=epoch2datetime(TIME2),
                complete_at=None,
                results=None,
                state_string='new',
                urls=[],
                hidden=False,
            ),
        )

    @defer.inlineCallbacks
    def test_addStep_getStep_existing_step(self):
        yield self.db.insert_test_data([*self.backgroundData, self.stepRows[0]])
        stepid, number, name = yield self.db.steps.addStep(
            buildid=30, name='new', state_string='new'
        )
        yield self.db.steps.startStep(stepid=stepid, started_at=TIME1, locks_acquired=False)
        self.assertEqual((number, name), (1, 'new'))
        stepdict = yield self.db.steps.getStep(stepid=stepid)
        self.assertIsInstance(stepdict, steps.StepModel)
        self.assertEqual(stepdict.number, number)
        self.assertEqual(stepdict.name, name)

    @defer.inlineCallbacks
    def test_addStep_getStep_name_collisions(self):
        yield self.db.insert_test_data([
            *self.backgroundData,
            fakedb.Step(id=73, number=0, name='new', buildid=30),
            fakedb.Step(id=74, number=1, name='new_1', buildid=30),
            fakedb.Step(id=75, number=2, name='new_2', buildid=30),
            fakedb.Step(id=76, number=3, name='new_step', buildid=30),
        ])
        stepid, number, name = yield self.db.steps.addStep(
            buildid=30, name='new', state_string='new'
        )
        yield self.db.steps.startStep(stepid=stepid, started_at=TIME1, locks_acquired=False)
        self.assertEqual((number, name), (4, 'new_3'))
        stepdict = yield self.db.steps.getStep(stepid=stepid)
        self.assertIsInstance(stepdict, steps.StepModel)
        self.assertEqual(stepdict.number, number)
        self.assertEqual(stepdict.name, name)

    @defer.inlineCallbacks
    def test_setStepStateString(self):
        yield self.db.insert_test_data([*self.backgroundData, self.stepRows[2]])
        yield self.db.steps.setStepStateString(stepid=72, state_string='aaa')
        stepdict = yield self.db.steps.getStep(stepid=72)
        self.assertEqual(stepdict.state_string, 'aaa')

    @defer.inlineCallbacks
    def test_addURL(self):
        yield self.db.insert_test_data([*self.backgroundData, self.stepRows[2]])
        yield self.db.steps.addURL(stepid=72, name='foo', url='bar')

        stepdict = yield self.db.steps.getStep(stepid=72)
        self.assertEqual(stepdict.urls, [steps.UrlModel(name='foo', url='bar')])

    @defer.inlineCallbacks
    def test_addURL_race(self):
        yield self.db.insert_test_data([*self.backgroundData, self.stepRows[2]])
        yield defer.gatherResults(
            [
                # only a tiny sleep is required to see the problem.
                self.db.steps.addURL(
                    stepid=72, name='foo', url='bar', _racehook=lambda: time.sleep(0.01)
                ),
                self.db.steps.addURL(stepid=72, name='foo2', url='bar2'),
            ],
            consumeErrors=True,
        )

        stepdict = yield self.db.steps.getStep(stepid=72)

        def urlKey(url):
            return url.name

        # order is not guaranteed though
        self.assertEqual(
            sorted(stepdict.urls, key=urlKey),
            sorted(
                [steps.UrlModel(name='foo', url='bar'), steps.UrlModel(name='foo2', url='bar2')],
                key=urlKey,
            ),
        )

    @defer.inlineCallbacks
    def test_addURL_no_duplicate(self):
        yield self.db.insert_test_data([*self.backgroundData, self.stepRows[2]])
        yield defer.gatherResults(
            [
                self.db.steps.addURL(stepid=72, name='foo', url='bar'),
                self.db.steps.addURL(stepid=72, name='foo', url='bar'),
            ],
            consumeErrors=True,
        )

        stepdict = yield self.db.steps.getStep(stepid=72)

        self.assertEqual(stepdict.urls, [steps.UrlModel(name='foo', url='bar')])

    @defer.inlineCallbacks
    def test_finishStep(self):
        self.reactor.advance(TIME2)
        yield self.db.insert_test_data([*self.backgroundData, self.stepRows[2]])
        yield self.db.steps.finishStep(stepid=72, results=11, hidden=False)
        stepdict = yield self.db.steps.getStep(stepid=72)
        self.assertEqual(stepdict.results, 11)
        self.assertEqual(stepdict.complete_at, epoch2datetime(TIME2))
        self.assertEqual(stepdict.hidden, False)

    @defer.inlineCallbacks
    def test_finishStep_hidden(self):
        yield self.db.insert_test_data([*self.backgroundData, self.stepRows[2]])
        yield self.db.steps.finishStep(stepid=72, results=11, hidden=True)
        stepdict = yield self.db.steps.getStep(stepid=72)
        self.assertEqual(stepdict.hidden, True)

    @defer.inlineCallbacks
    def test_addStep_getStep_name_collisions_too_long(self):
        yield self.db.insert_test_data([
            *self.backgroundData,
            fakedb.Step(id=73, number=0, name='a' * 49, buildid=30),
            fakedb.Step(id=74, number=1, name='a' * 48 + '_1', buildid=30),
        ])
        stepid, number, name = yield self.db.steps.addStep(
            buildid=30, name='a' * 49, state_string='new'
        )
        yield self.db.steps.startStep(stepid=stepid, started_at=TIME1, locks_acquired=False)
        self.assertEqual((number, name), (2, 'a' * 48 + '_2'))
        stepdict = yield self.db.steps.getStep(stepid=stepid)
        self.assertIsInstance(stepdict, steps.StepModel)
        self.assertEqual(stepdict.number, number)
        self.assertEqual(stepdict.name, name)

    @defer.inlineCallbacks
    def test_addStep_getStep_name_collisions_too_long_extra_digits(self):
        yield self.db.insert_test_data(
            self.backgroundData
            + [
                fakedb.Step(id=73, number=0, name='a' * 50, buildid=30),
            ]
            + [
                fakedb.Step(id=73 + i, number=i, name='a' * 48 + (f'_{i}'), buildid=30)
                for i in range(1, 10)
            ]
            + [
                fakedb.Step(id=73 + i, number=i, name='a' * 47 + (f'_{i}'), buildid=30)
                for i in range(10, 100)
            ]
        )
        stepid, number, name = yield self.db.steps.addStep(
            buildid=30, name='a' * 50, state_string='new'
        )
        yield self.db.steps.startStep(stepid=stepid, started_at=TIME1, locks_acquired=False)
        self.assertEqual((number, name), (100, 'a' * 46 + '_100'))
        stepdict = yield self.db.steps.getStep(stepid=stepid)
        self.assertIsInstance(stepdict, steps.StepModel)
        self.assertEqual(stepdict.number, number)
        self.assertEqual(stepdict.name, name)
