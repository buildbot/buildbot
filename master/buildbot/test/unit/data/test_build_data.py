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

from parameterized import parameterized

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.data import build_data
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import endpoint
from buildbot.test.util import interfaces


class TestBuildDataNoValueEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = build_data.BuildDataNoValueEndpoint
    resourceTypeClass = build_data.BuildData

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.Worker(id=47, name='linux'),
            fakedb.Buildset(id=20),
            fakedb.Builder(id=88, name='b1'),
            fakedb.BuildRequest(id=41, buildsetid=20, builderid=88),
            fakedb.Master(id=88),
            fakedb.Build(id=30, buildrequestid=41, number=7, masterid=88, builderid=88,
                         workerid=47),
            fakedb.BuildData(id=91, buildid=30, name='name1', value=b'value1', source='source1'),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    @defer.inlineCallbacks
    def test_get_existing_build_data_by_build_id(self):
        result = yield self.callGet(('builds', 30, 'data', 'name1'))
        self.validateData(result)
        self.assertEqual(result, {
            'buildid': 30,
            'name': 'name1',
            'value': None,
            'source': 'source1',
            'length': 6,
        })

    @defer.inlineCallbacks
    def test_get_existing_build_data_by_builder_name_build_number(self):
        result = yield self.callGet(('builders', 'b1', 'builds', 7, 'data', 'name1'))
        self.validateData(result)
        self.assertEqual(result, {
            'buildid': 30,
            'name': 'name1',
            'value': None,
            'source': 'source1',
            'length': 6,
        })

    @defer.inlineCallbacks
    def test_get_existing_build_data_by_builder_id_build_number(self):
        result = yield self.callGet(('builders', 88, 'builds', 7, 'data', 'name1'))
        self.validateData(result)
        self.assertEqual(result, {
            'buildid': 30,
            'name': 'name1',
            'value': None,
            'length': 6,
            'source': 'source1',
        })

    @defer.inlineCallbacks
    def test_get_missing_by_build_id_missing_build(self):
        result = yield self.callGet(('builds', 31, 'data', 'name1'))
        self.assertIsNone(result)

    @defer.inlineCallbacks
    def test_get_missing_by_build_id_missing_name(self):
        result = yield self.callGet(('builds', 30, 'data', 'name_missing'))
        self.assertIsNone(result)

    @defer.inlineCallbacks
    def test_get_missing_by_builder_name_build_number_missing_builder(self):
        result = yield self.callGet(('builders', 'b_missing', 'builds', 7, 'data', 'name1'))
        self.assertIsNone(result)

    @defer.inlineCallbacks
    def test_get_missing_by_builder_name_build_number_missing_build(self):
        result = yield self.callGet(('builders', 'b1', 'builds', 17, 'data', 'name1'))
        self.assertIsNone(result)

    @defer.inlineCallbacks
    def test_get_missing_by_builder_name_build_number_missing_name(self):
        result = yield self.callGet(('builders', 'b1', 'builds', 7, 'data', 'name_missing'))
        self.assertIsNone(result)

    @defer.inlineCallbacks
    def test_get_missing_by_builder_id_build_number_missing_builder(self):
        result = yield self.callGet(('builders', 188, 'builds', 7, 'data', 'name1'))
        self.assertIsNone(result)

    @defer.inlineCallbacks
    def test_get_missing_by_builder_id_build_number_missing_build(self):
        result = yield self.callGet(('builders', 88, 'builds', 17, 'data', 'name1'))
        self.assertIsNone(result)

    @defer.inlineCallbacks
    def test_get_missing_by_builder_id_build_number_missing_name(self):
        result = yield self.callGet(('builders', 88, 'builds', 7, 'data', 'name_missing'))
        self.assertIsNone(result)


class TestBuildDataEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = build_data.BuildDataEndpoint
    resourceTypeClass = build_data.BuildData

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.Worker(id=47, name='linux'),
            fakedb.Buildset(id=20),
            fakedb.Builder(id=88, name='b1'),
            fakedb.BuildRequest(id=41, buildsetid=20, builderid=88),
            fakedb.Master(id=88),
            fakedb.Build(id=30, buildrequestid=41, number=7, masterid=88, builderid=88,
                         workerid=47),
            fakedb.BuildData(id=91, buildid=30, name='name1', value=b'value1', source='source1'),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    def validateData(self, data):
        self.assertIsInstance(data['raw'], bytes)
        self.assertIsInstance(data['mime-type'], str)
        self.assertIsInstance(data['filename'], str)

    @defer.inlineCallbacks
    def test_get_existing_build_data_by_build_id(self):
        result = yield self.callGet(('builds', 30, 'data', 'name1', 'value'))
        self.validateData(result)
        self.assertEqual(result, {
            'raw': b'value1',
            'mime-type': 'application/octet-stream',
            'filename': 'name1',
        })

    @defer.inlineCallbacks
    def test_get_existing_build_data_by_builder_name_build_number(self):
        result = yield self.callGet(('builders', 'b1', 'builds', 7, 'data', 'name1', 'value'))
        self.validateData(result)
        self.assertEqual(result, {
            'raw': b'value1',
            'mime-type': 'application/octet-stream',
            'filename': 'name1',
        })

    @defer.inlineCallbacks
    def test_get_existing_build_data_by_builder_id_build_number(self):
        result = yield self.callGet(('builders', 88, 'builds', 7, 'data', 'name1', 'value'))
        self.validateData(result)
        self.assertEqual(result, {
            'raw': b'value1',
            'mime-type': 'application/octet-stream',
            'filename': 'name1',
        })

    @defer.inlineCallbacks
    def test_get_missing_by_build_id_missing_build(self):
        result = yield self.callGet(('builds', 31, 'data', 'name1', 'value'))
        self.assertIsNone(result)

    @defer.inlineCallbacks
    def test_get_missing_by_build_id_missing_name(self):
        result = yield self.callGet(('builds', 30, 'data', 'name_missing', 'value'))
        self.assertIsNone(result)

    @defer.inlineCallbacks
    def test_get_missing_by_builder_name_build_number_missing_builder(self):
        result = yield self.callGet(('builders', 'b_missing', 'builds', 7, 'data', 'name1',
                                     'value'))
        self.assertIsNone(result)

    @defer.inlineCallbacks
    def test_get_missing_by_builder_name_build_number_missing_build(self):
        result = yield self.callGet(('builders', 'b1', 'builds', 17, 'data', 'name1', 'value'))
        self.assertIsNone(result)

    @defer.inlineCallbacks
    def test_get_missing_by_builder_name_build_number_missing_name(self):
        result = yield self.callGet(('builders', 'b1', 'builds', 7, 'data', 'name_missing',
                                     'value'))
        self.assertIsNone(result)

    @defer.inlineCallbacks
    def test_get_missing_by_builder_id_build_number_missing_builder(self):
        result = yield self.callGet(('builders', 188, 'builds', 7, 'data', 'name1', 'value'))
        self.assertIsNone(result)

    @defer.inlineCallbacks
    def test_get_missing_by_builder_id_build_number_missing_build(self):
        result = yield self.callGet(('builders', 88, 'builds', 17, 'data', 'name1', 'value'))
        self.assertIsNone(result)

    @defer.inlineCallbacks
    def test_get_missing_by_builder_id_build_number_missing_name(self):
        result = yield self.callGet(('builders', 88, 'builds', 7, 'data', 'name_missing', 'value'))
        self.assertIsNone(result)


class TestBuildDatasNoValueEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = build_data.BuildDatasNoValueEndpoint
    resourceTypeClass = build_data.BuildData

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.Worker(id=47, name='linux'),
            fakedb.Buildset(id=20),
            fakedb.Builder(id=88, name='b1'),
            fakedb.Master(id=88),
            fakedb.BuildRequest(id=41, buildsetid=20, builderid=88),
            fakedb.BuildRequest(id=42, buildsetid=20, builderid=88),
            fakedb.BuildRequest(id=43, buildsetid=20, builderid=88),
            fakedb.Build(id=30, buildrequestid=41, number=7, masterid=88, builderid=88,
                         workerid=47),
            fakedb.Build(id=31, buildrequestid=42, number=8, masterid=88, builderid=88,
                         workerid=47),
            fakedb.Build(id=32, buildrequestid=42, number=9, masterid=88, builderid=88,
                         workerid=47),
            fakedb.BuildData(id=91, buildid=30, name='name1', value=b'value1', source='source1'),
            fakedb.BuildData(id=92, buildid=30, name='name2', value=b'value2', source='source2'),
            fakedb.BuildData(id=93, buildid=31, name='name3', value=b'value3', source='source3'),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    @parameterized.expand([
        ('multiple_values', 7, ['name1', 'name2']),
        ('single_value', 8, ['name3']),
        ('no_values', 9, []),
        ('not_existing', 10, []),
    ])
    @defer.inlineCallbacks
    def test_get_builders_builder_name(self, name, build_number, exp_names):
        results = yield self.callGet(('builders', 'b1', 'builds', build_number, 'data'))
        for result in results:
            self.validateData(result)
        self.assertEqual([r['name'] for r in results], exp_names)

    @parameterized.expand([
        ('multiple_values', 7, ['name1', 'name2']),
        ('single_value', 8, ['name3']),
        ('no_values', 9, []),
        ('not_existing', 10, []),
    ])
    @defer.inlineCallbacks
    def test_get_builders_builder_id(self, name, build_number, exp_names):
        results = yield self.callGet(('builders', 88, 'builds', build_number, 'data'))
        for result in results:
            self.validateData(result)
        self.assertEqual([r['name'] for r in results], exp_names)

    @parameterized.expand([
        ('multiple_values', 30, ['name1', 'name2']),
        ('single_value', 31, ['name3']),
        ('no_values', 32, []),
        ('not_existing', 33, []),
    ])
    @defer.inlineCallbacks
    def test_get_builds_id(self, name, buildid, exp_names):
        results = yield self.callGet(('builds', buildid, 'data'))
        for result in results:
            self.validateData(result)
        self.assertEqual([r['name'] for r in results], exp_names)


class TestBuildData(TestReactorMixin, interfaces.InterfaceTests, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self, wantMq=True, wantDb=True, wantData=True)
        self.rtype = build_data.BuildData(self.master)

    def test_signature_set_build_data(self):
        @self.assertArgSpecMatches(self.master.data.updates.setBuildData,
                                   self.rtype.setBuildData)
        def setBuildData(self, buildid, name, value, source):
            pass

    @defer.inlineCallbacks
    def test_set_build_data(self):
        yield self.rtype.setBuildData(buildid=2, name='name1', value=b'value1', source='source1')

        result = yield self.master.db.build_data.getBuildData(2, 'name1')
        self.assertEqual(result, {
            'buildid': 2,
            'name': 'name1',
            'value': b'value1',
            'length': 6,
            'source': 'source1',
        })
