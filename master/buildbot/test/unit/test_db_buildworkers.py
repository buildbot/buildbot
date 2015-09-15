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

from buildbot.db import buildworkers
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import connector_component
from buildbot.test.util import interfaces
from buildbot.test.util import validation
from twisted.internet import defer
from twisted.trial import unittest


class Tests(interfaces.InterfaceTests):

    # common sample data

    baseRows = [
        fakedb.Master(id=10, name='m10'),
        fakedb.Master(id=11, name='m11'),
        fakedb.Builder(id=20, name=u'a'),
        fakedb.Builder(id=21, name=u'b'),
        fakedb.Builder(id=22, name=u'c'),
        fakedb.Buildworker(id=30, name='zero'),
        fakedb.Buildworker(id=31, name='one'),
    ]

    multipleMasters = [
        fakedb.BuilderMaster(id=12, builderid=20, masterid=10),
        fakedb.BuilderMaster(id=13, builderid=21, masterid=10),
        fakedb.BuilderMaster(id=14, builderid=20, masterid=11),
        fakedb.BuilderMaster(id=15, builderid=22, masterid=11),
        fakedb.BuilderMaster(id=16, builderid=22, masterid=10),
        fakedb.ConfiguredBuildworker(
            id=3012, buildworkerid=30, buildermasterid=12),
        fakedb.ConfiguredBuildworker(
            id=3013, buildworkerid=30, buildermasterid=13),
        fakedb.ConfiguredBuildworker(
            id=3014, buildworkerid=30, buildermasterid=14),
        fakedb.ConfiguredBuildworker(
            id=3114, buildworkerid=31, buildermasterid=14),
        fakedb.ConfiguredBuildworker(
            id=3115, buildworkerid=31, buildermasterid=15),
        fakedb.ConnectedBuildworker(id=3010, buildworkerid=30, masterid=10),
        fakedb.ConnectedBuildworker(id=3111, buildworkerid=31, masterid=11),
    ]

    # sample buildworker data, with id's avoiding the postgres id sequence

    BOGUS_NAME = 'bogus'

    BS1_NAME, BS1_ID, BS1_INFO = 'bs1', 100, {'a': 1}
    buildworker1_rows = [
        fakedb.Buildworker(id=BS1_ID, name=BS1_NAME, info=BS1_INFO),
    ]

    BS2_NAME, BS2_ID, BS2_INFO = 'bs2', 200, {'a': 1, 'b': 2}
    buildworker2_rows = [
        fakedb.Buildworker(id=BS2_ID, name=BS2_NAME, info=BS2_INFO),
    ]

    # tests

    def test_signature_findBuildworkerId(self):
        @self.assertArgSpecMatches(self.db.buildworkers.findBuildworkerId)
        def findBuildworkerId(self, name):
            pass

    def test_signature_getBuildworker(self):
        @self.assertArgSpecMatches(self.db.buildworkers.getBuildworker)
        def getBuildworker(self, buildworkerid=None, name=None,
                          masterid=None, builderid=None):
            pass

    def test_signature_getBuildworkers(self):
        @self.assertArgSpecMatches(self.db.buildworkers.getBuildworkers)
        def getBuildworkers(self, masterid=None, builderid=None):
            pass

    def test_signature_buildworkerConnected(self):
        @self.assertArgSpecMatches(self.db.buildworkers.buildworkerConnected)
        def buildworkerConnected(self, buildworkerid, masterid, workerinfo):
            pass

    def test_signature_buildworkerDisconnected(self):
        @self.assertArgSpecMatches(self.db.buildworkers.buildworkerDisconnected)
        def buildworkerDisconnected(self, buildworkerid, masterid):
            pass

    def test_signature_buildworkerConfigured(self):
        @self.assertArgSpecMatches(self.db.buildworkers.buildworkerConfigured)
        def buildworkerConfigured(self, buildworkerid, masterid, builderids):
            pass

    def test_signature_deconfigureAllBuidworkersForMaster(self):
        @self.assertArgSpecMatches(self.db.buildworkers.deconfigureAllBuidworkersForMaster)
        def deconfigureAllBuidworkersForMaster(self, masterid):
            pass

    @defer.inlineCallbacks
    def test_findBuildworkerId_insert(self):
        id = yield self.db.buildworkers.findBuildworkerId(name=u"xyz")
        bworker = yield self.db.buildworkers.getBuildworker(buildworkerid=id)
        self.assertEqual(bworker['name'], 'xyz')
        self.assertEqual(bworker['workerinfo'], {})

    @defer.inlineCallbacks
    def test_findBuildworkerId_existing(self):
        yield self.insertTestData(self.baseRows)
        id = yield self.db.buildworkers.findBuildworkerId(name=u"one")
        self.assertEqual(id, 31)

    @defer.inlineCallbacks
    def test_getBuildworker_no_such(self):
        yield self.insertTestData(self.baseRows)
        workerdict = yield self.db.buildworkers.getBuildworker(buildworkerid=99)
        self.assertEqual(workerdict, None)

    @defer.inlineCallbacks
    def test_getBuildworker_by_name_no_such(self):
        yield self.insertTestData(self.baseRows)
        workerdict = yield self.db.buildworkers.getBuildworker(name='NOSUCH')
        self.assertEqual(workerdict, None)

    @defer.inlineCallbacks
    def test_getBuildworker_not_configured(self):
        yield self.insertTestData(self.baseRows)
        workerdict = yield self.db.buildworkers.getBuildworker(buildworkerid=30)
        validation.verifyDbDict(self, 'buildworkerdict', workerdict)
        self.assertEqual(workerdict,
                         dict(id=30, name='zero', workerinfo={'a': 'b'},
                              connected_to=[], configured_on=[]))

    @defer.inlineCallbacks
    def test_getBuildworker_connected_not_configured(self):
        yield self.insertTestData(self.baseRows + [
            # the worker is connected to this master, but not configured.
            # weird, but the DB should represent it.
            fakedb.Buildworker(id=32, name='two'),
            fakedb.ConnectedBuildworker(buildworkerid=32, masterid=11),
        ])
        workerdict = yield self.db.buildworkers.getBuildworker(buildworkerid=32)
        validation.verifyDbDict(self, 'buildworkerdict', workerdict)
        self.assertEqual(workerdict,
                         dict(id=32, name='two', workerinfo={'a': 'b'},
                              connected_to=[11], configured_on=[]))

    @defer.inlineCallbacks
    def test_getBuildworker_multiple_connections(self):
        yield self.insertTestData(self.baseRows + [
            # the worker is connected to two masters at once.
            # weird, but the DB should represent it.
            fakedb.Buildworker(id=32, name='two'),
            fakedb.ConnectedBuildworker(buildworkerid=32, masterid=10),
            fakedb.ConnectedBuildworker(buildworkerid=32, masterid=11),
            fakedb.BuilderMaster(id=24, builderid=20, masterid=10),
            fakedb.BuilderMaster(id=25, builderid=20, masterid=11),
            fakedb.ConfiguredBuildworker(buildworkerid=32, buildermasterid=24),
            fakedb.ConfiguredBuildworker(buildworkerid=32, buildermasterid=25),
        ])
        workerdict = yield self.db.buildworkers.getBuildworker(buildworkerid=32)
        validation.verifyDbDict(self, 'buildworkerdict', workerdict)
        self.assertEqual(workerdict,
                         dict(id=32, name='two', workerinfo={'a': 'b'},
                              connected_to=[10, 11], configured_on=[
                                  {'builderid': 20, 'masterid': 10},
                                  {'builderid': 20, 'masterid': 11},
                                  ]))

    @defer.inlineCallbacks
    def test_getBuildworker_by_name_not_configured(self):
        yield self.insertTestData(self.baseRows)
        workerdict = yield self.db.buildworkers.getBuildworker(name='zero')
        validation.verifyDbDict(self, 'buildworkerdict', workerdict)
        self.assertEqual(workerdict,
                         dict(id=30, name='zero', workerinfo={'a': 'b'},
                              connected_to=[], configured_on=[]))

    @defer.inlineCallbacks
    def test_getBuildworker_not_connected(self):
        yield self.insertTestData(self.baseRows + [
            fakedb.BuilderMaster(id=12, builderid=20, masterid=10),
            fakedb.ConfiguredBuildworker(buildworkerid=30, buildermasterid=12),
        ])
        workerdict = yield self.db.buildworkers.getBuildworker(buildworkerid=30)
        validation.verifyDbDict(self, 'buildworkerdict', workerdict)
        self.assertEqual(workerdict,
                         dict(id=30, name='zero', workerinfo={'a': 'b'},
                              configured_on=[
                                  {'masterid': 10, 'builderid': 20}],
                              connected_to=[]))

    @defer.inlineCallbacks
    def test_getBuildworker_connected(self):
        yield self.insertTestData(self.baseRows + [
            fakedb.BuilderMaster(id=12, builderid=20, masterid=10),
            fakedb.ConfiguredBuildworker(buildworkerid=30, buildermasterid=12),
            fakedb.ConnectedBuildworker(buildworkerid=30, masterid=10),
        ])
        workerdict = yield self.db.buildworkers.getBuildworker(buildworkerid=30)
        validation.verifyDbDict(self, 'buildworkerdict', workerdict)
        self.assertEqual(workerdict,
                         dict(id=30, name='zero', workerinfo={'a': 'b'},
                              configured_on=[
                                  {'masterid': 10, 'builderid': 20}],
                              connected_to=[10]))

    @defer.inlineCallbacks
    def test_getBuildworker_with_multiple_masters(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        workerdict = yield self.db.buildworkers.getBuildworker(buildworkerid=30)
        validation.verifyDbDict(self, 'buildworkerdict', workerdict)
        workerdict['configured_on'].sort()
        self.assertEqual(workerdict,
                         dict(id=30, name='zero', workerinfo={'a': 'b'},
                              configured_on=sorted([
                                  {'masterid': 10, 'builderid': 20},
                                  {'masterid': 10, 'builderid': 21},
                                  {'masterid': 11, 'builderid': 20},
                              ]), connected_to=[10]))

    @defer.inlineCallbacks
    def test_getBuildworker_with_multiple_masters_builderid(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        workerdict = yield self.db.buildworkers.getBuildworker(buildworkerid=30, builderid=20)
        validation.verifyDbDict(self, 'buildworkerdict', workerdict)
        workerdict['configured_on'].sort()
        self.assertEqual(workerdict,
                         dict(id=30, name='zero', workerinfo={'a': 'b'},
                              configured_on=sorted([
                                  {'masterid': 10, 'builderid': 20},
                                  {'masterid': 11, 'builderid': 20},
                              ]), connected_to=[10]))

    @defer.inlineCallbacks
    def test_getBuildworker_with_multiple_masters_masterid(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        workerdict = yield self.db.buildworkers.getBuildworker(buildworkerid=30, masterid=11)
        validation.verifyDbDict(self, 'buildworkerdict', workerdict)
        self.assertEqual(workerdict,
                         dict(id=30, name='zero', workerinfo={'a': 'b'},
                              configured_on=[
                                  {'masterid': 11, 'builderid': 20},
                                  ], connected_to=[]))

    @defer.inlineCallbacks
    def test_getBuildworker_with_multiple_masters_builderid_masterid(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        workerdict = yield self.db.buildworkers.getBuildworker(buildworkerid=30,
                                                            builderid=20, masterid=11)
        validation.verifyDbDict(self, 'buildworkerdict', workerdict)
        self.assertEqual(workerdict,
                         dict(id=30, name='zero', workerinfo={'a': 'b'},
                              configured_on=[
                                  {'masterid': 11, 'builderid': 20},
                                  ], connected_to=[]))

    @defer.inlineCallbacks
    def test_getBuildworker_by_name_with_multiple_masters_builderid_masterid(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        workerdict = yield self.db.buildworkers.getBuildworker(name='zero',
                                                            builderid=20, masterid=11)
        validation.verifyDbDict(self, 'buildworkerdict', workerdict)
        self.assertEqual(workerdict,
                         dict(id=30, name='zero', workerinfo={'a': 'b'},
                              configured_on=[
                                  {'masterid': 11, 'builderid': 20},
                                  ], connected_to=[]))

    @defer.inlineCallbacks
    def test_getBuildworkers_no_config(self):
        yield self.insertTestData(self.baseRows)
        workerdicts = yield self.db.buildworkers.getBuildworkers()
        [validation.verifyDbDict(self, 'buildworkerdict', workerdict)
         for workerdict in workerdicts]
        self.assertEqual(sorted(workerdicts), sorted([
            dict(id=30, name='zero', workerinfo={'a': 'b'},
                 configured_on=[], connected_to=[]),
            dict(id=31, name='one', workerinfo={'a': 'b'},
                 configured_on=[], connected_to=[]),
        ]))

    @defer.inlineCallbacks
    def test_getBuildworkers_with_config(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        workerdicts = yield self.db.buildworkers.getBuildworkers()
        for workerdict in workerdicts:
            validation.verifyDbDict(self, 'buildworkerdict', workerdict)
            workerdict['configured_on'].sort()
        self.assertEqual(sorted(workerdicts), sorted([
            dict(id=30, name='zero', workerinfo={'a': 'b'},
                 configured_on=sorted([
                     {'masterid': 10, 'builderid': 20},
                     {'masterid': 10, 'builderid': 21},
                     {'masterid': 11, 'builderid': 20},
                 ]), connected_to=[10]),
            dict(id=31, name='one', workerinfo={'a': 'b'},
                 configured_on=sorted([
                     {'masterid': 11, 'builderid': 20},
                     {'masterid': 11, 'builderid': 22},
                 ]), connected_to=[11]),
        ]))

    @defer.inlineCallbacks
    def test_getBuildworkers_empty(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        workerdicts = yield self.db.buildworkers.getBuildworkers(masterid=11, builderid=21)
        for workerdict in workerdicts:
            validation.verifyDbDict(self, 'buildworkerdict', workerdict)
            workerdict['configured_on'].sort()
        self.assertEqual(sorted(workerdicts), [])

    @defer.inlineCallbacks
    def test_getBuildworkers_with_config_builderid(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        workerdicts = yield self.db.buildworkers.getBuildworkers(builderid=20)
        for workerdict in workerdicts:
            validation.verifyDbDict(self, 'buildworkerdict', workerdict)
            workerdict['configured_on'].sort()
        self.assertEqual(sorted(workerdicts), sorted([
            dict(id=30, name='zero', workerinfo={'a': 'b'},
                 configured_on=sorted([
                     {'masterid': 10, 'builderid': 20},
                     {'masterid': 11, 'builderid': 20},
                 ]), connected_to=[10]),
            dict(id=31, name='one', workerinfo={'a': 'b'},
                 configured_on=sorted([
                     {'masterid': 11, 'builderid': 20},
                 ]), connected_to=[11]),
        ]))

    @defer.inlineCallbacks
    def test_getBuildworkers_with_config_masterid_10(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        workerdicts = yield self.db.buildworkers.getBuildworkers(masterid=10)
        for workerdict in workerdicts:
            validation.verifyDbDict(self, 'buildworkerdict', workerdict)
            workerdict['configured_on'].sort()
        self.assertEqual(sorted(workerdicts), sorted([
            dict(id=30, name='zero', workerinfo={'a': 'b'},
                 configured_on=sorted([
                     {'masterid': 10, 'builderid': 20},
                     {'masterid': 10, 'builderid': 21},
                 ]), connected_to=[10]),
        ]))

    @defer.inlineCallbacks
    def test_getBuildworkers_with_config_masterid_11(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        workerdicts = yield self.db.buildworkers.getBuildworkers(masterid=11)
        for workerdict in workerdicts:
            validation.verifyDbDict(self, 'buildworkerdict', workerdict)
            workerdict['configured_on'].sort()
        self.assertEqual(sorted(workerdicts), sorted([
            dict(id=30, name='zero', workerinfo={'a': 'b'},
                 configured_on=sorted([
                     {'masterid': 11, 'builderid': 20},
                 ]), connected_to=[]),
            dict(id=31, name='one', workerinfo={'a': 'b'},
                 configured_on=sorted([
                     {'masterid': 11, 'builderid': 20},
                     {'masterid': 11, 'builderid': 22},
                 ]), connected_to=[11]),
        ]))

    @defer.inlineCallbacks
    def test_getBuildworkers_with_config_masterid_11_builderid_22(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        workerdicts = yield self.db.buildworkers.getBuildworkers(
            masterid=11, builderid=22)
        for workerdict in workerdicts:
            validation.verifyDbDict(self, 'buildworkerdict', workerdict)
            workerdict['configured_on'].sort()
        self.assertEqual(sorted(workerdicts), sorted([
            dict(id=31, name='one', workerinfo={'a': 'b'},
                 configured_on=sorted([
                     {'masterid': 11, 'builderid': 22},
                 ]), connected_to=[11]),
        ]))

    @defer.inlineCallbacks
    def test_buildworkerConnected_existing(self):
        yield self.insertTestData(self.baseRows + self.buildworker1_rows)

        NEW_INFO = {'other': [1, 2, 3]}

        yield self.db.buildworkers.buildworkerConnected(
            buildworkerid=self.BS1_ID, masterid=11, workerinfo=NEW_INFO)

        bs = yield self.db.buildworkers.getBuildworker(self.BS1_ID)
        self.assertEqual(bs, {
            'id': self.BS1_ID,
            'name': self.BS1_NAME,
            'workerinfo': NEW_INFO,
            'configured_on': [],
            'connected_to': [11]})

    @defer.inlineCallbacks
    def test_buildworkerConnected_already_connected(self):
        yield self.insertTestData(self.baseRows + self.buildworker1_rows + [
            fakedb.ConnectedBuildworker(id=888,
                                       buildworkerid=self.BS1_ID, masterid=11),
        ])
        yield self.db.buildworkers.buildworkerConnected(
            buildworkerid=self.BS1_ID, masterid=11, workerinfo={})

        bs = yield self.db.buildworkers.getBuildworker(self.BS1_ID)
        self.assertEqual(bs['connected_to'], [11])

    @defer.inlineCallbacks
    def test_buildworkerDisconnected(self):
        yield self.insertTestData(self.baseRows + self.buildworker1_rows + [
            fakedb.ConnectedBuildworker(id=888,
                                       buildworkerid=self.BS1_ID, masterid=10),
            fakedb.ConnectedBuildworker(id=889,
                                       buildworkerid=self.BS1_ID, masterid=11),
        ])
        yield self.db.buildworkers.buildworkerDisconnected(
            buildworkerid=self.BS1_ID, masterid=11)

        bs = yield self.db.buildworkers.getBuildworker(self.BS1_ID)
        self.assertEqual(bs['connected_to'], [10])

    @defer.inlineCallbacks
    def test_buildworkerDisconnected_already_disconnected(self):
        yield self.insertTestData(self.baseRows + self.buildworker1_rows)
        yield self.db.buildworkers.buildworkerDisconnected(
            buildworkerid=self.BS1_ID, masterid=11)

        bs = yield self.db.buildworkers.getBuildworker(self.BS1_ID)
        self.assertEqual(bs['connected_to'], [])

    @defer.inlineCallbacks
    def test_buildworkerConfigured(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)

        # should remove builder 21, and add 22
        yield self.db.buildworkers.deconfigureAllBuidworkersForMaster(masterid=10)

        yield self.db.buildworkers.buildworkerConfigured(
            buildworkerid=30, masterid=10, builderids=[20, 22])

        bs = yield self.db.buildworkers.getBuildworker(30)
        self.assertEqual(sorted(bs['configured_on']), sorted([
            {'builderid': 20, 'masterid': 11},
            {'builderid': 20, 'masterid': 10},
            {'builderid': 22, 'masterid': 10}]))

    @defer.inlineCallbacks
    def test_buildworkerConfiguredTwice(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)

        # should remove builder 21, and add 22
        yield self.db.buildworkers.deconfigureAllBuidworkersForMaster(masterid=10)

        yield self.db.buildworkers.buildworkerConfigured(
            buildworkerid=30, masterid=10, builderids=[20, 22])

        # configure again (should eat the duplicate insertion errors)
        yield self.db.buildworkers.buildworkerConfigured(
            buildworkerid=30, masterid=10, builderids=[20, 21, 22])

        bs = yield self.db.buildworkers.getBuildworker(30)
        self.assertEqual(sorted(bs['configured_on']), sorted([
            {'builderid': 20, 'masterid': 11},
            {'builderid': 20, 'masterid': 10},
            {'builderid': 21, 'masterid': 10},
            {'builderid': 22, 'masterid': 10}]))

    @defer.inlineCallbacks
    def test_nothingConfigured(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)

        # should remove builder 21, and add 22
        yield self.db.buildworkers.deconfigureAllBuidworkersForMaster(masterid=10)
        yield self.db.buildworkers.buildworkerConfigured(
            buildworkerid=30, masterid=10, builderids=[])

        # should only keep builder for master 11
        bs = yield self.db.buildworkers.getBuildworker(30)
        self.assertEqual(sorted(bs['configured_on']), sorted([
            {'builderid': 20, 'masterid': 11}]))

    @defer.inlineCallbacks
    def test_deconfiguredAllWorkers(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)

        res = yield self.db.buildworkers.getBuildworkers(masterid=11)
        self.assertEqual(len(res), 2)

        # should remove all worker configured for masterid 11
        yield self.db.buildworkers.deconfigureAllBuidworkersForMaster(masterid=11)

        res = yield self.db.buildworkers.getBuildworkers(masterid=11)
        self.assertEqual(len(res), 0)


class RealTests(Tests):

    # tests that only "real" implementations will pass
    pass


class TestFakeDB(unittest.TestCase, Tests):

    def setUp(self):
        self.master = fakemaster.make_master()
        self.db = fakedb.FakeDBConnector(self)
        self.db.setServiceParent(self.master)
        self.db.checkForeignKeys = True
        self.insertTestData = self.db.insertTestData


class TestRealDB(unittest.TestCase,
                 connector_component.ConnectorComponentMixin,
                 RealTests):

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['buildworkers', 'masters', 'builders',
                         'builder_masters', 'connected_buildworkers',
                         'configured_buildworkers'])

        @d.addCallback
        def finish_setup(_):
            self.db.buildworkers = \
                buildworkers.BuildworkersConnectorComponent(self.db)
        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()
