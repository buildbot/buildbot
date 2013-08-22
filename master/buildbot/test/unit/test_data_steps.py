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
from twisted.internet import defer
from buildbot.data import steps, base
from buildbot.test.util import endpoint, interfaces
from buildbot.test.fake import fakemaster, fakedb

TIME1 = 2001111
TIME2 = 2002222
TIME3 = 2003333

class StepEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = steps.StepEndpoint
    resourceTypeClass = steps.Step

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.Buildslave(id=47, name='linux'),
            fakedb.Builder(id=77),
            fakedb.Master(id=88),
            fakedb.Buildset(id=8822),
            fakedb.BuildRequest(id=82, buildsetid=8822),
            fakedb.Build(id=30, builderid=77, number=7, masterid=88,
                buildrequestid=82, buildslaveid=47),
            fakedb.Step(id=70, number=0, name='one', buildid=30,
                started_at=TIME1, complete_at=TIME2, results=0),
            fakedb.Step(id=71, number=1, name='two', buildid=30,
                started_at=TIME2, complete_at=TIME3, results=2,
                urls_json='["http://url"]'),
            fakedb.Step(id=72, number=2, name='three', buildid=30,
                started_at=TIME3),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    @defer.inlineCallbacks
    def test_get_existing(self):
        step = yield self.callGet(('step', 72))
        self.validateData(step)
        self.assertEqual(step, {
            'build_link': base.Link(('build', '30')),
            'buildid': 30,
            'complete': False,
            'complete_at': None,
            'link': base.Link(('build', '72')),
            'name': u'three',
            'number': 2,
            'results': None,
            'started_at': TIME3,
            'state_strings': [],
            'stepid': 72,
            'urls': []})

    @defer.inlineCallbacks
    def test_get_existing_buildid_name(self):
        step = yield self.callGet(('build', 30, 'step', 'two'))
        self.validateData(step)
        self.assertEqual(step['stepid'], 71)

    @defer.inlineCallbacks
    def test_get_existing_buildid_number(self):
        step = yield self.callGet(('build', 30, 'step', 1))
        self.validateData(step)
        self.assertEqual(step['stepid'], 71)

    @defer.inlineCallbacks
    def test_get_existing_builder_name(self):
        step = yield self.callGet(('builder', 77, 'build', 7, 'step', 'two'))
        self.validateData(step)
        self.assertEqual(step['stepid'], 71)

    @defer.inlineCallbacks
    def test_get_existing_builder_number(self):
        step = yield self.callGet(('builder', 77, 'build', 7, 'step', 1))
        self.validateData(step)
        self.assertEqual(step['stepid'], 71)

    @defer.inlineCallbacks
    def test_get_missing(self):
        step = yield self.callGet(('step', 9999))
        self.assertEqual(step, None)


class StepsEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = steps.StepsEndpoint
    resourceTypeClass = steps.Step

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.Buildslave(id=47, name='linux'),
            fakedb.Builder(id=77),
            fakedb.Master(id=88),
            fakedb.Buildset(id=8822),
            fakedb.BuildRequest(id=82, buildsetid=8822),
            fakedb.Build(id=30, builderid=77, number=7, masterid=88,
                buildrequestid=82, buildslaveid=47),
            fakedb.Build(id=31, builderid=77, number=8, masterid=88,
                buildrequestid=82, buildslaveid=47),
            fakedb.Step(id=70, number=0, name='one', buildid=30,
                started_at=TIME1, complete_at=TIME2, results=0),
            fakedb.Step(id=71, number=1, name='two', buildid=30,
                started_at=TIME2, complete_at=TIME3, results=2,
                urls_json='["http://url"]'),
            fakedb.Step(id=72, number=2, name='three', buildid=30,
                started_at=TIME3),
            fakedb.Step(id=73, number=0, name='otherbuild', buildid=31,
                started_at=TIME2),
        ])


    def tearDown(self):
        self.tearDownEndpoint()

    @defer.inlineCallbacks
    def test_get_buildid(self):
        steps = yield self.callGet(('build', 30, 'step'))
        [ self.validateData(step) for step in steps ]
        self.assertEqual([ s['number'] for s in steps ], [0, 1, 2])

    @defer.inlineCallbacks
    def xtest_get_builder(self):
        steps = yield self.callGet(('builder', 77, 'build', 7, 'step'))
        [ self.validateData(step) for step in steps ]
        self.assertEqual([ s['number'] for s in steps ], [0, 1, 2])


class Step(interfaces.InterfaceTests, unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self,
                wantMq=True, wantDb=True, wantData=True)
        self.rtype = steps.Step(self.master)

    def do_test_callthrough(self, dbMethodName, method, exp_args=None,
            exp_kwargs=None, *args, **kwargs):
        rv = defer.succeed(None)
        m = mock.Mock(return_value=rv)
        setattr(self.master.db.steps, dbMethodName, m)
        self.assertIdentical(method(*args, **kwargs), rv)
        m.assert_called_with(*(exp_args or args), **(exp_kwargs or kwargs))

    def test_signature_newStep(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.newStep, # fake
            self.rtype.newStep) # real
        def newStep(self, buildid, name):
            pass

    def test_newStep(self):
        self.do_test_callthrough('addStep', self.rtype.newStep,
                buildid=10, name=u'name',
                exp_kwargs=dict(buildid=10, name=u'name',
                                state_strings=['starting']))

    def test_signature_setStepStateStrings(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.setStepStateStrings, # fake
            self.rtype.setStepStateStrings) # real
        def setStepStateStrings(self, stepid, state_strings):
            pass

    def test_setStepStateStrings(self):
        self.do_test_callthrough('setStepStateStrings',
                self.rtype.setStepStateStrings,
                stepid=10, state_strings=['a', 'b'])

    def test_signature_finishStep(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.finishStep, # fake
            self.rtype.finishStep) # real
        def finishStep(self, stepid, results):
            pass

    def test_finishStep(self):
        self.do_test_callthrough('finishStep', self.rtype.finishStep,
                stepid=10, results=3)
