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

from buildbot.db import build_data
from buildbot.test import fakedb
from buildbot.test.util import connector_component
from buildbot.test.util import interfaces
from buildbot.test.util import validation


class Tests(interfaces.InterfaceTests):

    common_data = [
        fakedb.Worker(id=47, name='linux'),
        fakedb.Buildset(id=20),
        fakedb.Builder(id=88, name='b1'),
        fakedb.Builder(id=89, name='b2'),
        fakedb.BuildRequest(id=41, buildsetid=20, builderid=88),
        fakedb.BuildRequest(id=42, buildsetid=20, builderid=88),
        fakedb.BuildRequest(id=43, buildsetid=20, builderid=89),
        fakedb.Master(id=88),
        fakedb.Build(id=30, buildrequestid=41, number=7, masterid=88, builderid=88, workerid=47),
        fakedb.Build(id=31, buildrequestid=42, number=8, masterid=88, builderid=88, workerid=47),
        fakedb.Build(id=40, buildrequestid=43, number=9, masterid=88, builderid=89, workerid=47),
    ]

    def test_signature_add_build_data(self):
        @self.assertArgSpecMatches(self.db.build_data.setBuildData)
        def setBuildData(self, buildid, name, value, source):
            pass

    def test_signature_get_build_data(self):
        @self.assertArgSpecMatches(self.db.build_data.getBuildData)
        def getBuildData(self, buildid, name):
            pass

    def test_signature_get_build_data_no_value(self):
        @self.assertArgSpecMatches(self.db.build_data.getBuildDataNoValue)
        def getBuildDataNoValue(self, buildid, name):
            pass

    def test_signature_get_all_build_data_no_values(self):
        @self.assertArgSpecMatches(self.db.build_data.getAllBuildDataNoValues)
        def getAllBuildDataNoValues(self, buildid):
            pass

    @defer.inlineCallbacks
    def test_add_data_get_data(self):
        yield self.insertTestData(self.common_data)
        yield self.db.build_data.setBuildData(buildid=30, name='mykey', value=b'myvalue',
                                              source='mysource')
        data_dict = yield self.db.build_data.getBuildData(buildid=30, name='mykey')
        validation.verifyDbDict(self, 'build_datadict', data_dict)
        self.assertEqual(data_dict, {
            'buildid': 30,
            'name': 'mykey',
            'value': b'myvalue',
            'length': 7,
            'source': 'mysource'
        })

    @defer.inlineCallbacks
    def test_get_data_non_existing(self):
        yield self.insertTestData(self.common_data)
        data_dict = yield self.db.build_data.getBuildData(buildid=30, name='mykey')
        self.assertIsNone(data_dict)

    @defer.inlineCallbacks
    def test_add_data_replace_value(self):
        yield self.insertTestData(self.common_data)
        yield self.db.build_data.setBuildData(buildid=30, name='mykey', value=b'myvalue',
                                              source='mysource')
        yield self.db.build_data.setBuildData(buildid=30, name='mykey', value=b'myvalue2',
                                              source='mysource2')

        data_dict = yield self.db.build_data.getBuildData(buildid=30, name='mykey')
        validation.verifyDbDict(self, 'build_datadict', data_dict)
        self.assertEqual(data_dict, {
            'buildid': 30,
            'name': 'mykey',
            'value': b'myvalue2',
            'length': 8,
            'source': 'mysource2'
        })

    @defer.inlineCallbacks
    def test_add_data_insert_race(self):
        yield self.insertTestData(self.common_data)

        def hook(conn):
            value = b'myvalue_old'
            insert_values = {
                'buildid': 30,
                'name': 'mykey',
                'value': value,
                'length': len(value),
                'source': 'mysourec_old'
            }
            q = self.db.model.build_data.insert().values(insert_values)
            conn.execute(q)
        self.db.build_data._test_timing_hook = hook

        yield self.db.build_data.setBuildData(buildid=30, name='mykey', value=b'myvalue',
                                              source='mysource')

        data_dict = yield self.db.build_data.getBuildData(buildid=30, name='mykey')
        validation.verifyDbDict(self, 'build_datadict', data_dict)
        self.assertEqual(data_dict, {
            'buildid': 30,
            'name': 'mykey',
            'value': b'myvalue',
            'length': 7,
            'source': 'mysource'
        })

    @defer.inlineCallbacks
    def test_add_data_get_data_no_value(self):
        yield self.insertTestData(self.common_data)
        yield self.db.build_data.setBuildData(buildid=30, name='mykey', value=b'myvalue',
                                              source='mysource')
        data_dict = yield self.db.build_data.getBuildDataNoValue(buildid=30, name='mykey')
        validation.verifyDbDict(self, 'build_datadict', data_dict)
        self.assertEqual(data_dict, {
            'buildid': 30,
            'name': 'mykey',
            'value': None,
            'length': 7,
            'source': 'mysource'
        })

    @defer.inlineCallbacks
    def test_get_data_no_values_non_existing(self):
        yield self.insertTestData(self.common_data)
        data_dict = yield self.db.build_data.getBuildDataNoValue(buildid=30, name='mykey')
        self.assertIsNone(data_dict)

    @defer.inlineCallbacks
    def test_get_all_build_data_no_values(self):
        yield self.insertTestData(self.common_data + [
            fakedb.BuildData(id=91, buildid=30, name='name1', value=b'value1', source='source1'),
            fakedb.BuildData(id=92, buildid=30, name='name2', value=b'value2', source='source2'),
            fakedb.BuildData(id=93, buildid=31, name='name3', value=b'value3', source='source3'),
        ])

        data_dicts = yield self.db.build_data.getAllBuildDataNoValues(30)
        self.assertEqual([d['name'] for d in data_dicts], ['name1', 'name2'])
        for d in data_dicts:
            validation.verifyDbDict(self, 'build_datadict', d)

        # note that value is not in dict, but length is
        self.assertEqual(data_dicts[0], {
            'buildid': 30,
            'name': 'name1',
            'value': None,
            'length': 6,
            'source': 'source1'
        })

        data_dicts = yield self.db.build_data.getAllBuildDataNoValues(31)
        self.assertEqual([d['name'] for d in data_dicts], ['name3'])
        data_dicts = yield self.db.build_data.getAllBuildDataNoValues(32)
        self.assertEqual([d['name'] for d in data_dicts], [])

    @parameterized.expand([
        (1000000, 0, ['name1', 'name2', 'name3', 'name4', 'name5', 'name6']),
        (1000001, 0, ['name1', 'name2', 'name3', 'name4', 'name5', 'name6']),
        (1000002, 2, ['name1', 'name2', 'name5', 'name6']),
        (1000003, 3, ['name1', 'name2', 'name6']),
        (1000004, 4, ['name1', 'name2']),
        (1000005, 4, ['name1', 'name2']),
    ])
    @defer.inlineCallbacks
    def test_remove_old_build_data(self, older_than_timestamp, exp_num_deleted,
                                   exp_remaining_names):
        yield self.insertTestData(self.common_data + [
            fakedb.Build(id=50, buildrequestid=41, number=17, masterid=88,
                         builderid=88, workerid=47, complete_at=None),
            fakedb.Build(id=51, buildrequestid=42, number=18, masterid=88,
                         builderid=88, workerid=47, complete_at=1000001),
            fakedb.Build(id=52, buildrequestid=43, number=19, masterid=88,
                         builderid=89, workerid=47, complete_at=1000002),
            fakedb.Build(id=53, buildrequestid=43, number=20, masterid=88,
                         builderid=89, workerid=47, complete_at=1000003),
            fakedb.BuildData(id=91, buildid=50, name='name1', value=b'value1', source='src1'),
            fakedb.BuildData(id=92, buildid=50, name='name2', value=b'value2', source='src2'),
            fakedb.BuildData(id=93, buildid=51, name='name3', value=b'value3', source='src3'),
            fakedb.BuildData(id=94, buildid=51, name='name4', value=b'value4', source='src4'),
            fakedb.BuildData(id=95, buildid=52, name='name5', value=b'value5', source='src5'),
            fakedb.BuildData(id=96, buildid=53, name='name6', value=b'value6', source='src6'),
        ])

        num_deleted = yield self.db.build_data.deleteOldBuildData(older_than_timestamp)
        self.assertEqual(num_deleted, exp_num_deleted)

        remaining_names = []
        for buildid in [50, 51, 52, 53]:
            data_dicts = yield self.db.build_data.getAllBuildDataNoValues(buildid)
            remaining_names += [d['name'] for d in data_dicts]

        self.assertEqual(sorted(remaining_names), sorted(exp_remaining_names))


class TestFakeDB(Tests, connector_component.FakeConnectorComponentMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        yield self.setUpConnectorComponent()


class TestRealDB(unittest.TestCase,
                 connector_component.ConnectorComponentMixin,
                 Tests):

    @defer.inlineCallbacks
    def setUp(self):
        yield self.setUpConnectorComponent(
            table_names=['builds', 'builders', 'masters', 'buildrequests', 'buildsets',
                         'workers', 'build_data'])

        self.db.build_data = build_data.BuildDataConnectorComponent(self.db)

    def tearDown(self):
        return self.tearDownConnectorComponent()
