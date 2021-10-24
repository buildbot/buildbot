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


from twisted.internet import defer
from twisted.trial import unittest

from buildbot.data import test_result_sets
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import endpoint
from buildbot.test.util import interfaces


class TestResultSetEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = test_result_sets.TestResultSetEndpoint
    resourceTypeClass = test_result_sets.TestResultSet

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.Worker(id=47, name='linux'),
            fakedb.Buildset(id=20),
            fakedb.Builder(id=88, name='b1'),
            fakedb.BuildRequest(id=41, buildsetid=20, builderid=88),
            fakedb.Master(id=88),
            fakedb.Build(id=30, buildrequestid=41, number=7, masterid=88,
                         builderid=88, workerid=47),
            fakedb.Step(id=131, number=132, name='step132', buildid=30),
            fakedb.TestResultSet(id=13, builderid=88, buildid=30, stepid=131, description='desc',
                                 category='cat', value_unit='ms', complete=1),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    @defer.inlineCallbacks
    def test_get_existing_result_set(self):
        result = yield self.callGet(('test_result_sets', 13))
        self.validateData(result)
        self.assertEqual(result, {
            'test_result_setid': 13,
            'builderid': 88,
            'buildid': 30,
            'stepid': 131,
            'description': 'desc',
            'category': 'cat',
            'value_unit': 'ms',
            'tests_passed': None,
            'tests_failed': None,
            'complete': True
        })

    @defer.inlineCallbacks
    def test_get_missing_result_set(self):
        results = yield self.callGet(('test_result_sets', 14))
        self.assertIsNone(results)


class TestResultSetsEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = test_result_sets.TestResultSetsEndpoint
    resourceTypeClass = test_result_sets.TestResultSet

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.Worker(id=47, name='linux'),
            fakedb.Buildset(id=20),
            fakedb.Builder(id=88, name='b1'),
            fakedb.BuildRequest(id=41, buildsetid=20, builderid=88),
            fakedb.Master(id=88),
            fakedb.Build(id=30, buildrequestid=41, number=7, masterid=88,
                         builderid=88, workerid=47),
            fakedb.Step(id=131, number=132, name='step132', buildid=30),
            fakedb.TestResultSet(id=13, builderid=88, buildid=30, stepid=131, description='desc',
                                 category='cat', value_unit='ms', complete=1),
            fakedb.TestResultSet(id=14, builderid=88, buildid=30, stepid=131, description='desc',
                                 category='cat', value_unit='ms', complete=1),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    @defer.inlineCallbacks
    def test_get_result_sets_builders_builderid(self):
        results = yield self.callGet(('builders', 88, 'test_result_sets'))
        for result in results:
            self.validateData(result)
        self.assertEqual([r['test_result_setid'] for r in results], [13, 14])

    @defer.inlineCallbacks
    def test_get_result_sets_builders_buildername(self):
        results = yield self.callGet(('builders', 'b1', 'test_result_sets'))
        for result in results:
            self.validateData(result)
        self.assertEqual([r['test_result_setid'] for r in results], [13, 14])

    @defer.inlineCallbacks
    def test_get_result_sets_builds_buildid(self):
        results = yield self.callGet(('builds', 30, 'test_result_sets'))
        for result in results:
            self.validateData(result)
        self.assertEqual([r['test_result_setid'] for r in results], [13, 14])

    @defer.inlineCallbacks
    def test_get_result_sets_steps_stepid(self):
        results = yield self.callGet(('steps', 131, 'test_result_sets'))
        for result in results:
            self.validateData(result)
        self.assertEqual([r['test_result_setid'] for r in results], [13, 14])


class TestResultSet(TestReactorMixin, interfaces.InterfaceTests, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self, wantMq=True, wantDb=True, wantData=True)
        self.rtype = test_result_sets.TestResultSet(self.master)

    def test_signature_add_test_result_set(self):
        @self.assertArgSpecMatches(self.master.data.updates.addTestResultSet,
                                   self.rtype.addTestResultSet)
        def addTestResultSet(self, builderid, buildid, stepid, description, category, value_unit):
            pass

    def test_signature_complete_test_result_set(self):
        @self.assertArgSpecMatches(self.master.data.updates.completeTestResultSet,
                                   self.rtype.completeTestResultSet)
        def completeTestResultSet(self, test_result_setid, tests_passed=None, tests_failed=None):
            pass

    @defer.inlineCallbacks
    def test_add_test_result_set(self):
        test_result_setid = yield self.rtype.addTestResultSet(builderid=1, buildid=2, stepid=3,
                                                              description='desc',
                                                              category='cat4', value_unit='ms')

        msg_body = {
            'test_result_setid': test_result_setid,
            'builderid': 1,
            'buildid': 2,
            'stepid': 3,
            'description': 'desc',
            'category': 'cat4',
            'value_unit': 'ms',
            'tests_passed': None,
            'tests_failed': None,
            'complete': False,
        }

        self.master.mq.assertProductions([
            (('test_result_sets', str(test_result_setid), 'new'), msg_body),
        ])

        result = yield self.master.db.test_result_sets.getTestResultSet(test_result_setid)
        self.assertEqual(result, {
            'id': test_result_setid,
            'builderid': 1,
            'buildid': 2,
            'stepid': 3,
            'description': 'desc',
            'category': 'cat4',
            'value_unit': 'ms',
            'tests_passed': None,
            'tests_failed': None,
            'complete': False,
        })

    @defer.inlineCallbacks
    def test_complete_test_result_set_no_results(self):
        test_result_setid = \
            yield self.master.db.test_result_sets.addTestResultSet(builderid=1, buildid=2, stepid=3,
                                                                   description='desc',
                                                                   category='cat4', value_unit='ms')

        yield self.rtype.completeTestResultSet(test_result_setid)

        msg_body = {
            'test_result_setid': test_result_setid,
            'builderid': 1,
            'buildid': 2,
            'stepid': 3,
            'description': 'desc',
            'category': 'cat4',
            'value_unit': 'ms',
            'tests_passed': None,
            'tests_failed': None,
            'complete': True,
        }

        self.master.mq.assertProductions([
            (('test_result_sets', str(test_result_setid), 'completed'), msg_body),
        ])

        result = yield self.master.db.test_result_sets.getTestResultSet(test_result_setid)
        self.assertEqual(result, {
            'id': test_result_setid,
            'builderid': 1,
            'buildid': 2,
            'stepid': 3,
            'description': 'desc',
            'category': 'cat4',
            'value_unit': 'ms',
            'tests_passed': None,
            'tests_failed': None,
            'complete': True,
        })

    @defer.inlineCallbacks
    def test_complete_test_result_set_with_results(self):
        test_result_setid = \
            yield self.master.db.test_result_sets.addTestResultSet(builderid=1, buildid=2, stepid=3,
                                                                   description='desc',
                                                                   category='cat4', value_unit='ms')

        yield self.rtype.completeTestResultSet(test_result_setid, tests_passed=12, tests_failed=34)

        msg_body = {
            'test_result_setid': test_result_setid,
            'builderid': 1,
            'buildid': 2,
            'stepid': 3,
            'description': 'desc',
            'category': 'cat4',
            'value_unit': 'ms',
            'tests_passed': 12,
            'tests_failed': 34,
            'complete': True,
        }

        self.master.mq.assertProductions([
            (('test_result_sets', str(test_result_setid), 'completed'), msg_body),
        ])

        result = yield self.master.db.test_result_sets.getTestResultSet(test_result_setid)
        self.assertEqual(result, {
            'id': test_result_setid,
            'builderid': 1,
            'buildid': 2,
            'stepid': 3,
            'description': 'desc',
            'category': 'cat4',
            'value_unit': 'ms',
            'tests_passed': 12,
            'tests_failed': 34,
            'complete': True,
        })
