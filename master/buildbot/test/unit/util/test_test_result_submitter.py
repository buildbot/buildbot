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

from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.util.test_result_submitter import TestResultSubmitter


class TestTestResultSubmitter(TestReactorMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True)
        yield self.master.startService()

        self.master.db.insertTestData([
            fakedb.Worker(id=47, name='linux'),
            fakedb.Buildset(id=20),
            fakedb.Builder(id=88, name='b1'),
            fakedb.BuildRequest(id=41, buildsetid=20, builderid=88),
            fakedb.Master(id=88),
            fakedb.Build(id=30, buildrequestid=41, number=7, masterid=88,
                         builderid=88, workerid=47),
            fakedb.Step(id=131, number=132, name='step132', buildid=30),
        ])

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.master.stopService()

    @defer.inlineCallbacks
    def test_complete_empty(self):
        sub = TestResultSubmitter()
        yield sub.setup_by_ids(self.master, 88, 30, 131, 'desc', 'cat', 'unit')

        setid = sub.get_test_result_set_id()
        sets = yield self.master.data.get(('builds', 30, 'test_result_sets'))
        self.assertEqual(list(sets), [{
            'test_result_setid': setid,
            'builderid': 88,
            'buildid': 30,
            'stepid': 131,
            'description': 'desc',
            'category': 'cat',
            'value_unit': 'unit',
            'tests_passed': None,
            'tests_failed': None,
            'complete': False
        }])

        yield sub.finish()

        sets = yield self.master.data.get(('builds', 30, 'test_result_sets'))
        self.assertEqual(list(sets), [{
            'test_result_setid': setid,
            'builderid': 88,
            'buildid': 30,
            'stepid': 131,
            'description': 'desc',
            'category': 'cat',
            'value_unit': 'unit',
            'tests_passed': None,
            'tests_failed': None,
            'complete': True
        }])

    @defer.inlineCallbacks
    def test_submit_result(self):
        sub = TestResultSubmitter(batch_n=3)
        yield sub.setup_by_ids(self.master, 88, 30, 131, 'desc', 'cat', 'unit')
        sub.add_test_result('1', 'name1')
        yield sub.finish()

        setid = sub.get_test_result_set_id()

        sets = yield self.master.data.get(('builds', 30, 'test_result_sets'))
        self.assertEqual(list(sets), [{
            'test_result_setid': setid,
            'builderid': 88,
            'buildid': 30,
            'stepid': 131,
            'description': 'desc',
            'category': 'cat',
            'value_unit': 'unit',
            'tests_passed': None,
            'tests_failed': None,
            'complete': True
        }])

        results = yield self.master.data.get(('test_result_sets', setid, 'results'))
        self.assertEqual(list(results), [{
            'test_resultid': 1002,
            'builderid': 88,
            'test_result_setid': setid,
            'test_name': 'name1',
            'test_code_path': None,
            'duration_ns': None,
            'line': None,
            'value': '1'
        }])

    def filter_results_value_name(self, results):
        return [{'test_name': r['test_name'], 'value': r['value']} for r in results]

    @defer.inlineCallbacks
    def test_submit_result_wrong_argument_types(self):
        sub = TestResultSubmitter()
        yield sub.setup_by_ids(self.master, 88, 30, 131, 'desc', 'cat', 'unit')

        with self.assertRaises(TypeError):
            sub.add_test_result(1, 'name1')
        with self.assertRaises(TypeError):
            sub.add_test_result('1', test_name=123)
        with self.assertRaises(TypeError):
            sub.add_test_result('1', 'name1', test_code_path=123)
        with self.assertRaises(TypeError):
            sub.add_test_result('1', 'name1', line='123')
        with self.assertRaises(TypeError):
            sub.add_test_result('1', 'name1', duration_ns='123')

    @defer.inlineCallbacks
    def test_batchs_last_batch_full(self):
        sub = TestResultSubmitter(batch_n=3)
        yield sub.setup_by_ids(self.master, 88, 30, 131, 'desc', 'cat', 'unit')
        sub.add_test_result('1', 'name1')
        sub.add_test_result('2', 'name2')
        sub.add_test_result('3', 'name3')
        sub.add_test_result('4', 'name4')
        sub.add_test_result('5', 'name5')
        sub.add_test_result('6', 'name6')
        yield sub.finish()

        setid = sub.get_test_result_set_id()

        results = yield self.master.data.get(('test_result_sets', setid, 'results'))
        results = self.filter_results_value_name(results)
        self.assertEqual(results, [
            {'test_name': 'name1', 'value': '1'},
            {'test_name': 'name2', 'value': '2'},
            {'test_name': 'name3', 'value': '3'},
            {'test_name': 'name4', 'value': '4'},
            {'test_name': 'name5', 'value': '5'},
            {'test_name': 'name6', 'value': '6'},
        ])

    @defer.inlineCallbacks
    def test_batchs_last_batch_not_full(self):
        sub = TestResultSubmitter(batch_n=3)
        yield sub.setup_by_ids(self.master, 88, 30, 131, 'desc', 'cat', 'unit')
        sub.add_test_result('1', 'name1')
        sub.add_test_result('2', 'name2')
        sub.add_test_result('3', 'name3')
        sub.add_test_result('4', 'name4')
        sub.add_test_result('5', 'name5')
        yield sub.finish()

        setid = sub.get_test_result_set_id()

        results = yield self.master.data.get(('test_result_sets', setid, 'results'))
        results = self.filter_results_value_name(results)
        self.assertEqual(results, [
            {'test_name': 'name1', 'value': '1'},
            {'test_name': 'name2', 'value': '2'},
            {'test_name': 'name3', 'value': '3'},
            {'test_name': 'name4', 'value': '4'},
            {'test_name': 'name5', 'value': '5'},
        ])

    @defer.inlineCallbacks
    def test_counts_pass_fail(self):
        sub = TestResultSubmitter(batch_n=3)
        yield sub.setup_by_ids(self.master, 88, 30, 131, 'desc', 'pass_fail', 'boolean')
        sub.add_test_result('0', 'name1')
        sub.add_test_result('0', 'name2')
        sub.add_test_result('1', 'name3')
        sub.add_test_result('1', 'name4')
        sub.add_test_result('0', 'name5')
        yield sub.finish()

        setid = sub.get_test_result_set_id()
        sets = yield self.master.data.get(('builds', 30, 'test_result_sets'))
        self.assertEqual(list(sets), [{
            'test_result_setid': setid,
            'builderid': 88,
            'buildid': 30,
            'stepid': 131,
            'description': 'desc',
            'category': 'pass_fail',
            'value_unit': 'boolean',
            'tests_passed': 2,
            'tests_failed': 3,
            'complete': True
        }])

    @defer.inlineCallbacks
    def test_counts_pass_fail_invalid_values(self):
        sub = TestResultSubmitter(batch_n=3)
        yield sub.setup_by_ids(self.master, 88, 30, 131, 'desc', 'pass_fail', 'boolean')
        sub.add_test_result('0', 'name1')
        sub.add_test_result('0', 'name2')
        sub.add_test_result('1', 'name3')
        sub.add_test_result('1', 'name4')
        sub.add_test_result('invalid', 'name5')
        yield sub.finish()

        setid = sub.get_test_result_set_id()
        sets = yield self.master.data.get(('builds', 30, 'test_result_sets'))
        self.assertEqual(list(sets), [{
            'test_result_setid': setid,
            'builderid': 88,
            'buildid': 30,
            'stepid': 131,
            'description': 'desc',
            'category': 'pass_fail',
            'value_unit': 'boolean',
            'tests_passed': 2,
            'tests_failed': 2,
            'complete': True
        }])

        # also check whether we preserve the "invalid" values in the database.
        results = yield self.master.data.get(('test_result_sets', setid, 'results'))
        results = self.filter_results_value_name(results)
        self.assertEqual(results, [
            {'test_name': 'name1', 'value': '0'},
            {'test_name': 'name2', 'value': '0'},
            {'test_name': 'name3', 'value': '1'},
            {'test_name': 'name4', 'value': '1'},
            {'test_name': 'name5', 'value': 'invalid'},
        ])

        self.flushLoggedErrors(ValueError)

    @defer.inlineCallbacks
    def test_counts_pass_only(self):
        sub = TestResultSubmitter(batch_n=3)
        yield sub.setup_by_ids(self.master, 88, 30, 131, 'desc', 'pass_only', 'some_unit')
        sub.add_test_result('string1', 'name1')
        sub.add_test_result('string2', 'name2')
        sub.add_test_result('string3', 'name3')
        sub.add_test_result('string4', 'name4')
        sub.add_test_result('string5', 'name5')
        yield sub.finish()

        setid = sub.get_test_result_set_id()
        sets = yield self.master.data.get(('builds', 30, 'test_result_sets'))
        self.assertEqual(list(sets), [{
            'test_result_setid': setid,
            'builderid': 88,
            'buildid': 30,
            'stepid': 131,
            'description': 'desc',
            'category': 'pass_only',
            'value_unit': 'some_unit',
            'tests_passed': 5,
            'tests_failed': 0,
            'complete': True
        }])

        results = yield self.master.data.get(('test_result_sets', setid, 'results'))
        results = self.filter_results_value_name(results)
        self.assertEqual(results, [
            {'test_name': 'name1', 'value': 'string1'},
            {'test_name': 'name2', 'value': 'string2'},
            {'test_name': 'name3', 'value': 'string3'},
            {'test_name': 'name4', 'value': 'string4'},
            {'test_name': 'name5', 'value': 'string5'},
        ])

        self.flushLoggedErrors(ValueError)

    @defer.inlineCallbacks
    def test_counts_fail_only(self):
        sub = TestResultSubmitter(batch_n=3)
        yield sub.setup_by_ids(self.master, 88, 30, 131, 'desc', 'fail_only', 'some_unit')
        sub.add_test_result('string1', 'name1')
        sub.add_test_result('string2', 'name2')
        sub.add_test_result('string3', 'name3')
        sub.add_test_result('string4', 'name4')
        sub.add_test_result('string5', 'name5')
        yield sub.finish()

        setid = sub.get_test_result_set_id()
        sets = yield self.master.data.get(('builds', 30, 'test_result_sets'))
        self.assertEqual(list(sets), [{
            'test_result_setid': setid,
            'builderid': 88,
            'buildid': 30,
            'stepid': 131,
            'description': 'desc',
            'category': 'fail_only',
            'value_unit': 'some_unit',
            'tests_passed': 0,
            'tests_failed': 5,
            'complete': True
        }])

        results = yield self.master.data.get(('test_result_sets', setid, 'results'))
        results = self.filter_results_value_name(results)
        self.assertEqual(results, [
            {'test_name': 'name1', 'value': 'string1'},
            {'test_name': 'name2', 'value': 'string2'},
            {'test_name': 'name3', 'value': 'string3'},
            {'test_name': 'name4', 'value': 'string4'},
            {'test_name': 'name5', 'value': 'string5'},
        ])

        self.flushLoggedErrors(ValueError)
