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
from buildbot.db.test_result_sets import TestResultSetModel
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import endpoint
from buildbot.test.util import interfaces
from buildbot.util.twisted import async_to_deferred


class TestResultSetEndpoint(endpoint.EndpointMixin, unittest.TestCase):
    endpointClass = test_result_sets.TestResultSetEndpoint
    resourceTypeClass = test_result_sets.TestResultSet

    @defer.inlineCallbacks
    def setUp(self):
        yield self.setUpEndpoint()
        yield self.master.db.insert_test_data([
            fakedb.Worker(id=47, name='linux'),
            fakedb.Buildset(id=20),
            fakedb.Builder(id=88, name='b1'),
            fakedb.BuildRequest(id=41, buildsetid=20, builderid=88),
            fakedb.Master(id=88),
            fakedb.Build(
                id=30, buildrequestid=41, number=7, masterid=88, builderid=88, workerid=47
            ),
            fakedb.Step(id=131, number=132, name='step132', buildid=30),
            fakedb.TestResultSet(
                id=13,
                builderid=88,
                buildid=30,
                stepid=131,
                description='desc',
                category='cat',
                value_unit='ms',
                complete=1,
            ),
        ])

    @defer.inlineCallbacks
    def test_get_existing_result_set(self):
        result = yield self.callGet(('test_result_sets', 13))
        self.validateData(result)
        self.assertEqual(
            result,
            {
                'test_result_setid': 13,
                'builderid': 88,
                'buildid': 30,
                'stepid': 131,
                'description': 'desc',
                'category': 'cat',
                'value_unit': 'ms',
                'tests_passed': None,
                'tests_failed': None,
                'complete': True,
            },
        )

    @defer.inlineCallbacks
    def test_get_missing_result_set(self):
        results = yield self.callGet(('test_result_sets', 14))
        self.assertIsNone(results)


class TestResultSetsEndpoint(endpoint.EndpointMixin, unittest.TestCase):
    endpointClass = test_result_sets.TestResultSetsEndpoint
    resourceTypeClass = test_result_sets.TestResultSet

    @defer.inlineCallbacks
    def setUp(self):
        yield self.setUpEndpoint()
        yield self.master.db.insert_test_data([
            fakedb.Worker(id=47, name='linux'),
            fakedb.Buildset(id=20),
            fakedb.Builder(id=88, name='b1'),
            fakedb.BuildRequest(id=41, buildsetid=20, builderid=88),
            fakedb.Master(id=88),
            fakedb.Build(
                id=30, buildrequestid=41, number=7, masterid=88, builderid=88, workerid=47
            ),
            fakedb.Step(id=131, number=132, name='step132', buildid=30),
            fakedb.TestResultSet(
                id=13,
                builderid=88,
                buildid=30,
                stepid=131,
                description='desc',
                category='cat',
                value_unit='ms',
                complete=1,
            ),
            fakedb.TestResultSet(
                id=14,
                builderid=88,
                buildid=30,
                stepid=131,
                description='desc',
                category='cat',
                value_unit='ms',
                complete=1,
            ),
        ])

    @defer.inlineCallbacks
    def test_get_result_sets_all(self):
        results = yield self.callGet(('test_result_sets',))
        for result in results:
            self.validateData(result)
        self.assertEqual([r['test_result_setid'] for r in results], [13, 14])

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


class TestResultSetsFromCommitRangeEndpoint(endpoint.EndpointMixin, unittest.TestCase):
    endpointClass = test_result_sets.TestResultSetsFromCommitRangeEndpoint
    resourceTypeClass = test_result_sets.TestResultSet

    @async_to_deferred
    async def setUp(self) -> None:  # type: ignore[override]
        await self.setUpEndpoint()

        master_id = fakedb.FakeDBConnector.MASTER_ID
        await self.master.db.insert_test_data([
            fakedb.Master(id=master_id),
            fakedb.Worker(id=47, name='linux'),
            fakedb.Project(id=100),
            fakedb.Codebase(id=200, projectid=100),
            fakedb.CodebaseCommit(id=300, codebaseid=200, revision='rev300'),
            fakedb.CodebaseCommit(id=301, codebaseid=200, revision='rev301', parent_commitid=300),
            fakedb.CodebaseCommit(id=302, codebaseid=200, revision='rev302', parent_commitid=301),
            fakedb.CodebaseCommit(id=303, codebaseid=200, revision='rev303', parent_commitid=302),
            fakedb.CodebaseCommit(id=304, codebaseid=200, revision='rev304', parent_commitid=303),
            fakedb.Buildset(id=4000),
            fakedb.Buildset(id=4010),
            fakedb.Buildset(id=4020),
            fakedb.Buildset(id=4021),
            fakedb.Buildset(id=4040),
            fakedb.SourceStamp(id=5000, revision='rev300'),
            fakedb.SourceStamp(id=5010, revision='rev301'),
            fakedb.SourceStamp(id=5020, revision='rev302'),
            fakedb.SourceStamp(id=5040, revision='rev304'),
            fakedb.BuildsetSourceStamp(id=6000, buildsetid=4000, sourcestampid=5000),
            fakedb.BuildsetSourceStamp(id=6001, buildsetid=4010, sourcestampid=5010),
            fakedb.BuildsetSourceStamp(id=6002, buildsetid=4020, sourcestampid=5020),
            fakedb.BuildsetSourceStamp(id=6003, buildsetid=4021, sourcestampid=5020),
            fakedb.BuildsetSourceStamp(id=6004, buildsetid=4040, sourcestampid=5040),
            fakedb.Builder(id=400, name='b1'),
            fakedb.BuildRequest(id=7000, buildsetid=4000, builderid=400),
            fakedb.BuildRequest(id=7010, buildsetid=4010, builderid=400),
            fakedb.BuildRequest(id=7020, buildsetid=4020, builderid=400),
            fakedb.BuildRequest(id=7021, buildsetid=4021, builderid=400),
            fakedb.BuildRequest(id=7040, buildsetid=4040, builderid=400),
            fakedb.Build(
                id=8000, buildrequestid=7000, masterid=master_id, builderid=400, workerid=47
            ),
            fakedb.Build(
                id=8010, buildrequestid=7010, masterid=master_id, builderid=400, workerid=47
            ),
            fakedb.Build(
                id=8020, buildrequestid=7020, masterid=master_id, builderid=400, workerid=47
            ),
            fakedb.Build(
                id=8021, buildrequestid=7021, masterid=master_id, builderid=400, workerid=47
            ),
            fakedb.Build(
                id=8040, buildrequestid=7040, masterid=master_id, builderid=400, workerid=47
            ),
            fakedb.Step(id=9000, buildid=8000),
            fakedb.Step(id=9010, buildid=8010),
            fakedb.Step(id=9020, buildid=8020),
            fakedb.Step(id=9021, buildid=8021),
            fakedb.Step(id=9040, buildid=8040),
            fakedb.TestResultSet(id=10000, builderid=400, buildid=8000, stepid=9000),
            fakedb.TestResultSet(id=10010, builderid=400, buildid=8010, stepid=9010),
            fakedb.TestResultSet(id=10020, builderid=400, buildid=8020, stepid=9020),
            fakedb.TestResultSet(id=10021, builderid=400, buildid=8021, stepid=9021),
            fakedb.TestResultSet(id=10040, builderid=400, buildid=8040, stepid=9040),
        ])

    @async_to_deferred
    async def test_get_full_range(self) -> None:
        results = await self.callGet((
            'codebases',
            200,
            'commit_range',
            300,
            304,
            'test_result_sets',
        ))
        for result in results:
            self.validateData(result)
        self.assertEqual(
            [r['test_result_setid'] for r in results], [10000, 10010, 10020, 10021, 10040]
        )

    @async_to_deferred
    async def test_get_opposite_range(self) -> None:
        results = await self.callGet((
            'codebases',
            200,
            'commit_range',
            304,
            300,
            'test_result_sets',
        ))
        self.assertEqual(results, [])


class TestResultSet(TestReactorMixin, interfaces.InterfaceTests, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantMq=True, wantDb=True, wantData=True)
        yield self.master.db.insert_test_data([
            fakedb.Master(id=1),
            fakedb.Worker(id=1, name='example-worker'),
            fakedb.Builder(id=1),
            fakedb.Buildset(id=1),
            fakedb.BuildRequest(
                id=1,
                buildsetid=1,
                builderid=1,
            ),
            fakedb.Build(
                id=2,
                number=1,
                buildrequestid=1,
                builderid=1,
                workerid=1,
                masterid=1,
            ),
            fakedb.Step(
                id=3,
                number=1,
                name='step1',
                buildid=2,
            ),
        ])
        self.rtype = test_result_sets.TestResultSet(self.master)

    def test_signature_add_test_result_set(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.addTestResultSet, self.rtype.addTestResultSet
        )
        def addTestResultSet(self, builderid, buildid, stepid, description, category, value_unit):
            pass

    def test_signature_complete_test_result_set(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.completeTestResultSet, self.rtype.completeTestResultSet
        )
        def completeTestResultSet(self, test_result_setid, tests_passed=None, tests_failed=None):
            pass

    @defer.inlineCallbacks
    def test_add_test_result_set(self):
        test_result_setid = yield self.rtype.addTestResultSet(
            builderid=1, buildid=2, stepid=3, description='desc', category='cat4', value_unit='ms'
        )

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
        self.assertEqual(
            result,
            TestResultSetModel(
                id=test_result_setid,
                builderid=1,
                buildid=2,
                stepid=3,
                description='desc',
                category='cat4',
                value_unit='ms',
                tests_passed=None,
                tests_failed=None,
                complete=False,
            ),
        )

    @defer.inlineCallbacks
    def test_complete_test_result_set_no_results(self):
        test_result_setid = yield self.master.db.test_result_sets.addTestResultSet(
            builderid=1, buildid=2, stepid=3, description='desc', category='cat4', value_unit='ms'
        )

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
        self.assertEqual(
            result,
            TestResultSetModel(
                id=test_result_setid,
                builderid=1,
                buildid=2,
                stepid=3,
                description='desc',
                category='cat4',
                value_unit='ms',
                tests_passed=None,
                tests_failed=None,
                complete=True,
            ),
        )

    @defer.inlineCallbacks
    def test_complete_test_result_set_with_results(self):
        test_result_setid = yield self.master.db.test_result_sets.addTestResultSet(
            builderid=1, buildid=2, stepid=3, description='desc', category='cat4', value_unit='ms'
        )

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
        self.assertEqual(
            result,
            TestResultSetModel(
                id=test_result_setid,
                builderid=1,
                buildid=2,
                stepid=3,
                description='desc',
                category='cat4',
                value_unit='ms',
                tests_passed=12,
                tests_failed=34,
                complete=True,
            ),
        )
