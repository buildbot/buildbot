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

from buildbot.db import test_results
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin


class Tests(TestReactorMixin, unittest.TestCase):
    common_data = [
        fakedb.Worker(id=47, name='linux'),
        fakedb.Buildset(id=20),
        fakedb.Builder(id=88, name='b1'),
        fakedb.BuildRequest(id=41, buildsetid=20, builderid=88),
        fakedb.Master(id=88),
        fakedb.Build(id=30, buildrequestid=41, number=7, masterid=88, builderid=88, workerid=47),
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
    ]

    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantDb=True)
        self.db = self.master.db

    @defer.inlineCallbacks
    def test_add_set_results(self):
        yield self.db.insert_test_data(self.common_data)

        result_values = [
            {'test_name': 'name1', 'value': '1'},
            {'test_name': 'name1', 'duration_ns': 1000, 'value': '2'},
            {'test_name': 'name2', 'test_code_path': 'path2', 'value': '3'},
            {'test_name': 'name3', 'test_code_path': 'path3', 'value': '4'},
            {'test_name': 'name4', 'test_code_path': 'path4', 'line': 4, 'value': '5'},
            {'test_code_path': 'path5', 'line': 5, 'value': '6'},
        ]

        yield self.db.test_results.addTestResults(
            builderid=88, test_result_setid=13, result_values=result_values
        )

        result_dicts = yield self.db.test_results.getTestResults(builderid=88, test_result_setid=13)
        for d in result_dicts:
            self.assertIsInstance(d, test_results.TestResultModel)

        result_dicts = sorted(result_dicts, key=lambda x: x.id)
        resultid = result_dicts[0].id
        self.assertEqual(
            result_dicts,
            [
                test_results.TestResultModel(
                    id=resultid,
                    builderid=88,
                    test_result_setid=13,
                    test_name='name1',
                    test_code_path=None,
                    line=None,
                    duration_ns=None,
                    value='1',
                ),
                test_results.TestResultModel(
                    id=resultid + 1,
                    builderid=88,
                    test_result_setid=13,
                    test_name='name1',
                    test_code_path=None,
                    line=None,
                    duration_ns=1000,
                    value='2',
                ),
                test_results.TestResultModel(
                    id=resultid + 2,
                    builderid=88,
                    test_result_setid=13,
                    test_name='name2',
                    test_code_path='path2',
                    line=None,
                    duration_ns=None,
                    value='3',
                ),
                test_results.TestResultModel(
                    id=resultid + 3,
                    builderid=88,
                    test_result_setid=13,
                    test_name='name3',
                    test_code_path='path3',
                    line=None,
                    duration_ns=None,
                    value='4',
                ),
                test_results.TestResultModel(
                    id=resultid + 4,
                    builderid=88,
                    test_result_setid=13,
                    test_name='name4',
                    test_code_path='path4',
                    line=4,
                    duration_ns=None,
                    value='5',
                ),
                test_results.TestResultModel(
                    id=resultid + 5,
                    builderid=88,
                    test_result_setid=13,
                    test_name=None,
                    test_code_path='path5',
                    line=5,
                    duration_ns=None,
                    value='6',
                ),
            ],
        )

        result_dict = yield self.db.test_results.getTestResult(test_resultid=resultid)
        self.assertEqual(
            result_dict,
            test_results.TestResultModel(
                id=resultid,
                builderid=88,
                test_result_setid=13,
                test_name='name1',
                test_code_path=None,
                line=None,
                duration_ns=None,
                value='1',
            ),
        )

    @defer.inlineCallbacks
    def test_get_names(self):
        yield self.db.insert_test_data([
            *self.common_data,
            fakedb.TestName(id=103, builderid=88, name='name103'),
            fakedb.TestName(id=104, builderid=88, name='name104'),
            fakedb.TestName(id=105, builderid=88, name='name105'),
            fakedb.TestName(id=116, builderid=88, name='name116'),
            fakedb.TestName(id=117, builderid=88, name='name117'),
        ])

        name_dicts = yield self.db.test_results.getTestNames(builderid=88)
        self.assertEqual(name_dicts, ['name103', 'name104', 'name105', 'name116', 'name117'])

        name_dicts = yield self.db.test_results.getTestNames(
            builderid=88, name_prefix='non_existing'
        )
        self.assertEqual(name_dicts, [])

        name_dicts = yield self.db.test_results.getTestNames(builderid=88, name_prefix='name10')
        self.assertEqual(name_dicts, ['name103', 'name104', 'name105'])

        name_dicts = yield self.db.test_results.getTestNames(builderid=88, name_prefix='name11')
        self.assertEqual(name_dicts, ['name116', 'name117'])

    @defer.inlineCallbacks
    def test_get_code_paths(self):
        yield self.db.insert_test_data([
            *self.common_data,
            fakedb.TestCodePath(id=103, builderid=88, path='path103'),
            fakedb.TestCodePath(id=104, builderid=88, path='path104'),
            fakedb.TestCodePath(id=105, builderid=88, path='path105'),
            fakedb.TestCodePath(id=116, builderid=88, path='path116'),
            fakedb.TestCodePath(id=117, builderid=88, path='path117'),
        ])

        path_dicts = yield self.db.test_results.getTestCodePaths(builderid=88)
        self.assertEqual(path_dicts, ['path103', 'path104', 'path105', 'path116', 'path117'])

        path_dicts = yield self.db.test_results.getTestCodePaths(
            builderid=88, path_prefix='non_existing'
        )
        self.assertEqual(path_dicts, [])

        path_dicts = yield self.db.test_results.getTestCodePaths(builderid=88, path_prefix='path10')
        self.assertEqual(path_dicts, ['path103', 'path104', 'path105'])

        path_dicts = yield self.db.test_results.getTestCodePaths(builderid=88, path_prefix='path11')
        self.assertEqual(path_dicts, ['path116', 'path117'])
