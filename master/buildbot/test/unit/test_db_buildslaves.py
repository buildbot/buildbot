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

from twisted.trial import unittest
from twisted.internet import defer
from buildbot.test.fake import fakedb, fakemaster
from buildbot.test.util import interfaces, connector_component, validation
from buildbot.db import buildslaves

class Tests(interfaces.InterfaceTests):

    # common sample data

    baseRows = [
        fakedb.Master(id=10, name='m10'),
        fakedb.Master(id=11, name='m11'),
        fakedb.Builder(id=20, name=u'a'),
        fakedb.Builder(id=21, name=u'b'),
        fakedb.Builder(id=22, name=u'c'),
        fakedb.Buildslave(id=30, name='zero'),
        fakedb.Buildslave(id=31, name='one'),
    ]

    multipleMasters = [
        fakedb.BuilderMaster(id=12, builderid=20, masterid=10),
        fakedb.BuilderMaster(id=13, builderid=21, masterid=10),
        fakedb.BuilderMaster(id=14, builderid=20, masterid=11),
        fakedb.BuilderMaster(id=15, builderid=22, masterid=11),
        fakedb.ConfiguredBuildslave(id=3012, buildslaveid=30, buildermasterid=12),
        fakedb.ConfiguredBuildslave(id=3013, buildslaveid=30, buildermasterid=13),
        fakedb.ConfiguredBuildslave(id=3014, buildslaveid=30, buildermasterid=14),
        fakedb.ConfiguredBuildslave(id=3114, buildslaveid=31, buildermasterid=14),
        fakedb.ConfiguredBuildslave(id=3115, buildslaveid=31, buildermasterid=15),
        fakedb.ConnectedBuildslave(id=3010, buildslaveid=30, masterid=10),
        fakedb.ConnectedBuildslave(id=3111, buildslaveid=31, masterid=11),
    ]

    # sample buildslave data, with id's avoiding the postgres id sequence

    BOGUS_NAME = 'bogus'

    BS1_NAME, BS1_ID, BS1_INFO = 'bs1', 100, { 'a': 1 }
    buildslave1_rows = [
        fakedb.Buildslave(id=BS1_ID, name=BS1_NAME, info=BS1_INFO),
    ]

    BS2_NAME, BS2_ID, BS2_INFO = 'bs2', 200, { 'a': 1, 'b': 2 }
    buildslave2_rows = [
        fakedb.Buildslave(id=BS2_ID, name=BS2_NAME, info=BS2_INFO),
    ]

    # tests

    def test_signature_findBuildslaveId(self):
        @self.assertArgSpecMatches(self.db.buildslaves.findBuildslaveId)
        def findBuildslaveId(self, name):
            pass

    def test_signature_getBuildslave(self):
        @self.assertArgSpecMatches(self.db.buildslaves.getBuildslave)
        def getBuildslave(self, buildslaveid=None, name=None,
                masterid=None, builderid=None):
            pass

    def test_signature_getBuildslaves(self):
        @self.assertArgSpecMatches(self.db.buildslaves.getBuildslaves)
        def getBuildslaves(self, masterid=None, builderid=None):
            pass

    def test_signature_updateBuildslave(self):
        @self.assertArgSpecMatches(self.db.buildslaves.updateBuildslave)
        def updateBuildslave(self, buildslaveid, slaveinfo):
            pass

    @defer.inlineCallbacks
    def test_findBuildslaveId_insert(self):
        id = yield self.db.buildslaves.findBuildslaveId(name=u"xyz")
        bslave = yield self.db.buildslaves.getBuildslave(buildslaveid=id)
        self.assertEqual(bslave['name'], 'xyz')
        self.assertEqual(bslave['slaveinfo'], {})

    @defer.inlineCallbacks
    def test_findBuildslaveId_existing(self):
        yield self.insertTestData(self.baseRows)
        id = yield self.db.buildslaves.findBuildslaveId(name=u"one")
        self.assertEqual(id, 31)

    @defer.inlineCallbacks
    def test_getBuildslave_no_such(self):
        yield self.insertTestData(self.baseRows)
        slavedict = yield self.db.buildslaves.getBuildslave(buildslaveid=99)
        self.assertEqual(slavedict, None)

    @defer.inlineCallbacks
    def test_getBuildslave_by_name_no_such(self):
        yield self.insertTestData(self.baseRows)
        slavedict = yield self.db.buildslaves.getBuildslave(name='NOSUCH')
        self.assertEqual(slavedict, None)

    @defer.inlineCallbacks
    def test_getBuildslave_not_configured(self):
        yield self.insertTestData(self.baseRows)
        slavedict = yield self.db.buildslaves.getBuildslave(buildslaveid=30)
        validation.verifyDbDict(self, 'buildslavedict', slavedict)
        self.assertEqual(slavedict,
            dict(buildslaveid=30, name='zero', slaveinfo={'a':'b'},
                connected_to=[], configured_on=[]))

    @defer.inlineCallbacks
    def test_getBuildslave_connected_not_configured(self):
        yield self.insertTestData(self.baseRows + [
            # the slave is connected to this master, but not configured.
            # weird, but the DB should represent it.
            fakedb.Buildslave(id=32, name='two'),
            fakedb.ConnectedBuildslave(buildslaveid=32, masterid=11),
        ])
        slavedict = yield self.db.buildslaves.getBuildslave(buildslaveid=32)
        validation.verifyDbDict(self, 'buildslavedict', slavedict)
        self.assertEqual(slavedict,
            dict(buildslaveid=32, name='two', slaveinfo={'a':'b'},
                connected_to=[11], configured_on=[]))

    @defer.inlineCallbacks
    def test_getBuildslave_multiple_connections(self):
        yield self.insertTestData(self.baseRows + [
            # the slave is connected to two masters at once.
            # weird, but the DB should represent it.
            fakedb.Buildslave(id=32, name='two'),
            fakedb.ConnectedBuildslave(buildslaveid=32, masterid=10),
            fakedb.ConnectedBuildslave(buildslaveid=32, masterid=11),
            fakedb.BuilderMaster(id=24, builderid=20, masterid=10),
            fakedb.BuilderMaster(id=25, builderid=20, masterid=11),
            fakedb.ConfiguredBuildslave(buildslaveid=32, buildermasterid=24),
            fakedb.ConfiguredBuildslave(buildslaveid=32, buildermasterid=25),
        ])
        slavedict = yield self.db.buildslaves.getBuildslave(buildslaveid=32)
        validation.verifyDbDict(self, 'buildslavedict', slavedict)
        self.assertEqual(slavedict,
            dict(buildslaveid=32, name='two', slaveinfo={'a':'b'},
                connected_to=[10, 11], configured_on=[
                    {'builderid': 20, 'masterid': 10},
                    {'builderid': 20, 'masterid': 11},
                ]))

    @defer.inlineCallbacks
    def test_getBuildslave_by_name_not_configured(self):
        yield self.insertTestData(self.baseRows)
        slavedict = yield self.db.buildslaves.getBuildslave(name='zero')
        validation.verifyDbDict(self, 'buildslavedict', slavedict)
        self.assertEqual(slavedict,
            dict(buildslaveid=30, name='zero', slaveinfo={'a':'b'},
                connected_to=[], configured_on=[]))

    @defer.inlineCallbacks
    def test_getBuildslave_not_connected(self):
        yield self.insertTestData(self.baseRows + [
            fakedb.BuilderMaster(id=12, builderid=20, masterid=10),
            fakedb.ConfiguredBuildslave(buildslaveid=30, buildermasterid=12),
        ])
        slavedict = yield self.db.buildslaves.getBuildslave(buildslaveid=30)
        validation.verifyDbDict(self, 'buildslavedict', slavedict)
        self.assertEqual(slavedict,
            dict(buildslaveid=30, name='zero', slaveinfo={'a':'b'},
                configured_on=[{'masterid': 10, 'builderid': 20}],
                connected_to=[]))

    @defer.inlineCallbacks
    def test_getBuildslave_connected(self):
        yield self.insertTestData(self.baseRows + [
            fakedb.BuilderMaster(id=12, builderid=20, masterid=10),
            fakedb.ConfiguredBuildslave(buildslaveid=30, buildermasterid=12),
            fakedb.ConnectedBuildslave(buildslaveid=30, masterid=10),
        ])
        slavedict = yield self.db.buildslaves.getBuildslave(buildslaveid=30)
        validation.verifyDbDict(self, 'buildslavedict', slavedict)
        self.assertEqual(slavedict,
            dict(buildslaveid=30, name='zero', slaveinfo={'a':'b'},
                configured_on=[{'masterid': 10, 'builderid': 20}],
                connected_to=[10]))

    @defer.inlineCallbacks
    def test_getBuildslave_with_multiple_masters(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        slavedict = yield self.db.buildslaves.getBuildslave(buildslaveid=30)
        validation.verifyDbDict(self, 'buildslavedict', slavedict)
        slavedict['configured_on'].sort()
        self.assertEqual(slavedict,
            dict(buildslaveid=30, name='zero', slaveinfo={'a':'b'},
                configured_on=sorted([
                    {'masterid': 10, 'builderid': 20},
                    {'masterid': 10, 'builderid': 21},
                    {'masterid': 11, 'builderid': 20},
                ]), connected_to=[10]))

    @defer.inlineCallbacks
    def test_getBuildslave_with_multiple_masters_builderid(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        slavedict = yield self.db.buildslaves.getBuildslave(buildslaveid=30, builderid=20)
        validation.verifyDbDict(self, 'buildslavedict', slavedict)
        slavedict['configured_on'].sort()
        self.assertEqual(slavedict,
            dict(buildslaveid=30, name='zero', slaveinfo={'a':'b'},
                configured_on=sorted([
                    {'masterid': 10, 'builderid': 20},
                    {'masterid': 11, 'builderid': 20},
                ]), connected_to=[10]))

    @defer.inlineCallbacks
    def test_getBuildslave_with_multiple_masters_masterid(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        slavedict = yield self.db.buildslaves.getBuildslave(buildslaveid=30, masterid=11)
        validation.verifyDbDict(self, 'buildslavedict', slavedict)
        self.assertEqual(slavedict,
            dict(buildslaveid=30, name='zero', slaveinfo={'a':'b'},
                configured_on=[
                    {'masterid': 11, 'builderid': 20},
                ], connected_to=[]))

    @defer.inlineCallbacks
    def test_getBuildslave_with_multiple_masters_builderid_masterid(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        slavedict = yield self.db.buildslaves.getBuildslave(buildslaveid=30,
                builderid=20, masterid=11)
        validation.verifyDbDict(self, 'buildslavedict', slavedict)
        self.assertEqual(slavedict,
            dict(buildslaveid=30, name='zero', slaveinfo={'a':'b'},
                configured_on=[
                    {'masterid': 11, 'builderid': 20},
                ], connected_to=[]))

    @defer.inlineCallbacks
    def test_getBuildslave_by_name_with_multiple_masters_builderid_masterid(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        slavedict = yield self.db.buildslaves.getBuildslave(name='zero',
                builderid=20, masterid=11)
        validation.verifyDbDict(self, 'buildslavedict', slavedict)
        self.assertEqual(slavedict,
            dict(buildslaveid=30, name='zero', slaveinfo={'a':'b'},
                configured_on=[
                    {'masterid': 11, 'builderid': 20},
                ], connected_to=[]))

    @defer.inlineCallbacks
    def test_getBuildslaves_no_config(self):
        yield self.insertTestData(self.baseRows)
        slavedicts = yield self.db.buildslaves.getBuildslaves()
        [ validation.verifyDbDict(self, 'buildslavedict', slavedict)
          for slavedict in slavedicts ]
        self.assertEqual(sorted(slavedicts), sorted([
            dict(buildslaveid=30, name='zero', slaveinfo={'a':'b'},
                configured_on=[], connected_to=[]),
            dict(buildslaveid=31, name='one', slaveinfo={'a':'b'},
                configured_on=[], connected_to=[]),
        ]))

    @defer.inlineCallbacks
    def test_getBuildslaves_with_config(self):
        yield self.insertTestData(self.baseRows+self.multipleMasters)
        slavedicts = yield self.db.buildslaves.getBuildslaves()
        for slavedict in slavedicts:
            validation.verifyDbDict(self, 'buildslavedict', slavedict)
            slavedict['configured_on'].sort()
        self.assertEqual(sorted(slavedicts), sorted([
            dict(buildslaveid=30, name='zero', slaveinfo={'a':'b'},
                configured_on=sorted([
                    {'masterid': 10, 'builderid': 20},
                    {'masterid': 10, 'builderid': 21},
                    {'masterid': 11, 'builderid': 20},
                ]), connected_to=[10]),
            dict(buildslaveid=31, name='one', slaveinfo={'a':'b'},
                configured_on=sorted([
                    {'masterid': 11, 'builderid': 20},
                    {'masterid': 11, 'builderid': 22},
                ]), connected_to=[11]),
        ]))

    @defer.inlineCallbacks
    def test_getBuildslaves_empty(self):
        yield self.insertTestData(self.baseRows+self.multipleMasters)
        slavedicts = yield self.db.buildslaves.getBuildslaves(masterid=11, builderid=21)
        for slavedict in slavedicts:
            validation.verifyDbDict(self, 'buildslavedict', slavedict)
            slavedict['configured_on'].sort()
        self.assertEqual(sorted(slavedicts), [])

    @defer.inlineCallbacks
    def test_getBuildslaves_with_config_builderid(self):
        yield self.insertTestData(self.baseRows+self.multipleMasters)
        slavedicts = yield self.db.buildslaves.getBuildslaves(builderid=20)
        for slavedict in slavedicts:
            validation.verifyDbDict(self, 'buildslavedict', slavedict)
            slavedict['configured_on'].sort()
        self.assertEqual(sorted(slavedicts), sorted([
            dict(buildslaveid=30, name='zero', slaveinfo={'a':'b'},
                configured_on=sorted([
                    {'masterid': 10, 'builderid': 20},
                    {'masterid': 11, 'builderid': 20},
                ]), connected_to=[10]),
            dict(buildslaveid=31, name='one', slaveinfo={'a':'b'},
                configured_on=sorted([
                    {'masterid': 11, 'builderid': 20},
                ]), connected_to=[11]),
        ]))

    @defer.inlineCallbacks
    def test_getBuildslaves_with_config_masterid_10(self):
        yield self.insertTestData(self.baseRows+self.multipleMasters)
        slavedicts = yield self.db.buildslaves.getBuildslaves(masterid=10)
        for slavedict in slavedicts:
            validation.verifyDbDict(self, 'buildslavedict', slavedict)
            slavedict['configured_on'].sort()
        self.assertEqual(sorted(slavedicts), sorted([
            dict(buildslaveid=30, name='zero', slaveinfo={'a':'b'},
                configured_on=sorted([
                    {'masterid': 10, 'builderid': 20},
                    {'masterid': 10, 'builderid': 21},
                ]), connected_to=[10]),
        ]))

    @defer.inlineCallbacks
    def test_getBuildslaves_with_config_masterid_11(self):
        yield self.insertTestData(self.baseRows+self.multipleMasters)
        slavedicts = yield self.db.buildslaves.getBuildslaves(masterid=11)
        for slavedict in slavedicts:
            validation.verifyDbDict(self, 'buildslavedict', slavedict)
            slavedict['configured_on'].sort()
        self.assertEqual(sorted(slavedicts), sorted([
            dict(buildslaveid=30, name='zero', slaveinfo={'a':'b'},
                configured_on=sorted([
                    {'masterid': 11, 'builderid': 20},
                ]), connected_to=[]),
            dict(buildslaveid=31, name='one', slaveinfo={'a':'b'},
                configured_on=sorted([
                    {'masterid': 11, 'builderid': 20},
                    {'masterid': 11, 'builderid': 22},
                ]), connected_to=[11]),
        ]))

    @defer.inlineCallbacks
    def test_getBuildslaves_with_config_masterid_11_builderid_22(self):
        yield self.insertTestData(self.baseRows+self.multipleMasters)
        slavedicts = yield self.db.buildslaves.getBuildslaves(
                masterid=11, builderid=22)
        for slavedict in slavedicts:
            validation.verifyDbDict(self, 'buildslavedict', slavedict)
            slavedict['configured_on'].sort()
        self.assertEqual(sorted(slavedicts), sorted([
            dict(buildslaveid=31, name='one', slaveinfo={'a':'b'},
                configured_on=sorted([
                    {'masterid': 11, 'builderid': 22},
            ]), connected_to=[11]),
        ]))

    def test_updateBuildslave_existing(self):
        d = self.insertTestData(self.buildslave1_rows)

        NEW_INFO = { 'other': [ 1, 2, 3] }

        @d.addCallback
        def update(_):
            return self.db.buildslaves.updateBuildslave(
                    buildslaveid=self.BS1_ID, slaveinfo=NEW_INFO)

        @d.addCallback
        def get(_):
            return self.db.buildslaves.getBuildslave(self.BS1_ID)

        @d.addCallback
        def check(res):
            self.assertEqual(res['buildslaveid'], self.BS1_ID)
            self.assertEqual(res['name'], self.BS1_NAME)
            self.assertEqual(res['slaveinfo'], NEW_INFO)

        return d

    def test_updateBuildslave_badJson(self):
        d = self.insertTestData(self.buildslave1_rows)

        @d.addCallback
        def corrupt(_):
            BAD_JSON = {
                'key': object(),  # something json won't serialize
            }
            return self.db.buildslaves.updateBuildslave(
                buildslaveid=self.BS1_ID,
                slaveinfo=BAD_JSON)

        # don't really care what exception this is..
        self.assertFailure(d, Exception)


class RealTests(Tests):

    # tests that only "real" implementations will pass

    pass


class TestFakeDB(unittest.TestCase, Tests):

    def setUp(self):
        self.master = fakemaster.make_master()
        self.db = fakedb.FakeDBConnector(self.master, self)
        self.insertTestData = self.db.insertTestData


class TestRealDB(unittest.TestCase,
        connector_component.ConnectorComponentMixin,
        RealTests):

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['buildslaves', 'masters', 'builders',
                'builder_masters', 'connected_buildslaves',
                'configured_buildslaves'])

        @d.addCallback
        def finish_setup(_):
            self.db.buildslaves = \
                    buildslaves.BuildslavesConnectorComponent(self.db)
        return d


    def tearDown(self):
        return self.tearDownConnectorComponent()
