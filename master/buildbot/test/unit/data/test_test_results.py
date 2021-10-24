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

from buildbot.data import test_results
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import endpoint
from buildbot.test.util import interfaces


class TestResultsEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = test_results.TestResultsEndpoint
    resourceTypeClass = test_results.TestResult

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
            fakedb.TestName(id=301, builderid=88, name='name301'),
            fakedb.TestName(id=302, builderid=88, name='name302'),
            fakedb.TestCodePath(id=401, builderid=88, path='path401'),
            fakedb.TestCodePath(id=402, builderid=88, path='path402'),
            fakedb.TestResult(id=101, builderid=88, test_result_setid=13, line=400, value='v101'),
            fakedb.TestResult(id=102, builderid=88, test_result_setid=13,
                              test_nameid=301, test_code_pathid=401, line=401, value='v102'),
            fakedb.TestResult(id=103, builderid=88, test_result_setid=13,
                              test_nameid=302, test_code_pathid=402, line=402,
                              duration_ns=1012, value='v103'),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    @defer.inlineCallbacks
    def test_get_existing_results(self):
        results = yield self.callGet(('test_result_sets', 13, 'results'))
        for result in results:
            self.validateData(result)
        self.assertEqual([r['test_resultid'] for r in results], [101, 102, 103])

    @defer.inlineCallbacks
    def test_get_missing_results(self):
        results = yield self.callGet(('test_result_sets', 14, 'results'))
        self.assertEqual(results, [])


class TestResult(TestReactorMixin, interfaces.InterfaceTests, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self, wantMq=True, wantDb=True, wantData=True)
        self.rtype = test_results.TestResult(self.master)

    def test_signature_add_test_results(self):
        @self.assertArgSpecMatches(self.master.data.updates.addTestResults,
                                   self.rtype.addTestResults)
        def addTestResults(self, builderid, test_result_setid, result_values):
            pass

    @defer.inlineCallbacks
    def test_add_test_results(self):
        result_values = [
            {'test_name': 'name1', 'value': '1'},
            {'test_name': 'name2', 'duration_ns': 1000, 'value': '1'},
            {'test_name': 'name3', 'test_code_path': 'path2', 'value': '2'},
            {'test_name': 'name4', 'test_code_path': 'path3', 'value': '3'},
            {'test_name': 'name5', 'test_code_path': 'path4', 'line': 4, 'value': '4'},
            {'test_code_path': 'path5', 'line': 5, 'value': '5'},
        ]
        yield self.rtype.addTestResults(builderid=88, test_result_setid=13,
                                        result_values=result_values)

        self.master.mq.assertProductions([])

        results = yield self.master.db.test_results.getTestResults(builderid=88,
                                                                   test_result_setid=13)
        resultid = results[0]['id']
        self.assertEqual(results, [
            {'id': resultid, 'builderid': 88, 'test_result_setid': 13, 'test_name': 'name1',
             'test_code_path': None, 'line': None, 'duration_ns': None, 'value': '1'},
            {'id': resultid + 1, 'builderid': 88, 'test_result_setid': 13, 'test_name': 'name2',
             'test_code_path': None, 'line': None, 'duration_ns': 1000, 'value': '1'},
            {'id': resultid + 2, 'builderid': 88, 'test_result_setid': 13, 'test_name': 'name3',
             'test_code_path': 'path2', 'line': None, 'duration_ns': None, 'value': '2'},
            {'id': resultid + 3, 'builderid': 88, 'test_result_setid': 13, 'test_name': 'name4',
             'test_code_path': 'path3', 'line': None, 'duration_ns': None, 'value': '3'},
            {'id': resultid + 4, 'builderid': 88, 'test_result_setid': 13, 'test_name': 'name5',
             'test_code_path': 'path4', 'line': 4, 'duration_ns': None, 'value': '4'},
            {'id': resultid + 5, 'builderid': 88, 'test_result_setid': 13, 'test_name': None,
             'test_code_path': 'path5', 'line': 5, 'duration_ns': None, 'value': '5'},
        ])
