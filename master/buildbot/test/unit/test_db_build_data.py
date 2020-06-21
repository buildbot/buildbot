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
            'source': 'mysource2'
        })

    @defer.inlineCallbacks
    def test_add_data_insert_race(self):
        yield self.insertTestData(self.common_data)

        def hook(conn):
            insert_values = {
                'buildid': 30,
                'name': 'mykey',
                'value': b'myvalue_old',
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

        # note that value is not in dict
        self.assertEqual(data_dicts[0], {
            'buildid': 30,
            'name': 'name1',
            'value': None,
            'source': 'source1'
        })

        data_dicts = yield self.db.build_data.getAllBuildDataNoValues(31)
        self.assertEqual([d['name'] for d in data_dicts], ['name3'])
        data_dicts = yield self.db.build_data.getAllBuildDataNoValues(32)
        self.assertEqual([d['name'] for d in data_dicts], [])


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
