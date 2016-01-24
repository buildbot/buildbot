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
import mock

from buildbot.db import worker
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import connector_component
from buildbot.test.util import interfaces
from buildbot.test.util import validation
from buildbot.test.util.warnings import assertProducesWarning
from buildbot.test.util.warnings import ignoreWarning
from buildbot.worker_transition import DeprecatedWorkerModuleWarning
from buildbot.worker_transition import DeprecatedWorkerNameWarning
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
        fakedb.Worker(id=30, name='zero'),
        fakedb.Worker(id=31, name='one'),
    ]

    multipleMasters = [
        fakedb.BuilderMaster(id=12, builderid=20, masterid=10),
        fakedb.BuilderMaster(id=13, builderid=21, masterid=10),
        fakedb.BuilderMaster(id=14, builderid=20, masterid=11),
        fakedb.BuilderMaster(id=15, builderid=22, masterid=11),
        fakedb.BuilderMaster(id=16, builderid=22, masterid=10),
        fakedb.ConfiguredWorker(
            id=3012, workerid=30, buildermasterid=12),
        fakedb.ConfiguredWorker(
            id=3013, workerid=30, buildermasterid=13),
        fakedb.ConfiguredWorker(
            id=3014, workerid=30, buildermasterid=14),
        fakedb.ConfiguredWorker(
            id=3114, workerid=31, buildermasterid=14),
        fakedb.ConfiguredWorker(
            id=3115, workerid=31, buildermasterid=15),
        fakedb.ConnectedWorker(id=3010, workerid=30, masterid=10),
        fakedb.ConnectedWorker(id=3111, workerid=31, masterid=11),
    ]

    # sample buildslave data, with id's avoiding the postgres id sequence

    BOGUS_NAME = 'bogus'

    BS1_NAME, BS1_ID, BS1_INFO = 'bs1', 100, {'a': 1}
    buildslave1_rows = [
        fakedb.Worker(id=BS1_ID, name=BS1_NAME, info=BS1_INFO),
    ]

    BS2_NAME, BS2_ID, BS2_INFO = 'bs2', 200, {'a': 1, 'b': 2}
    buildslave2_rows = [
        fakedb.Worker(id=BS2_ID, name=BS2_NAME, info=BS2_INFO),
    ]

    # tests

    def test_signature_findWorkerId(self):
        @self.assertArgSpecMatches(self.db.workers.findWorkerId)
        def findWorkerId(self, name):
            pass

    def test_signature_getBuildslave(self):
        @self.assertArgSpecMatches(self.db.workers.getWorker)
        def getWorker(self, workerid=None, name=None,
                      masterid=None, builderid=None):
            pass

    def test_signature_getBuildslaves(self):
        @self.assertArgSpecMatches(self.db.workers.getWorkers)
        def getWorkers(self, masterid=None, builderid=None):
            pass

    def test_signature_buildslaveConnected(self):
        @self.assertArgSpecMatches(self.db.workers.workerConnected)
        def workerConnected(self, workerid, masterid, workerinfo):
            pass

    def test_signature_buildslaveDisconnected(self):
        @self.assertArgSpecMatches(self.db.workers.workerDisconnected)
        def workerDisconnected(self, workerid, masterid):
            pass

    def test_signature_buildslaveConfigured(self):
        @self.assertArgSpecMatches(self.db.workers.workerConfigured)
        def workerConfigured(self, workerid, masterid, builderids):
            pass

    def test_signature_deconfigureAllBuidslavesForMaster(self):
        @self.assertArgSpecMatches(self.db.workers.deconfigureAllWorkersForMaster)
        def deconfigureAllWorkersForMaster(self, masterid):
            pass

    @defer.inlineCallbacks
    def test_findWorkerId_insert(self):
        id = yield self.db.workers.findWorkerId(name=u"xyz")
        bslave = yield self.db.workers.getWorker(workerid=id)
        self.assertEqual(bslave['name'], 'xyz')
        self.assertEqual(bslave['slaveinfo'], {})

    @defer.inlineCallbacks
    def test_findWorkerId_existing(self):
        yield self.insertTestData(self.baseRows)
        id = yield self.db.workers.findWorkerId(name=u"one")
        self.assertEqual(id, 31)

    @defer.inlineCallbacks
    def test_getBuildslave_no_such(self):
        yield self.insertTestData(self.baseRows)
        slavedict = yield self.db.workers.getWorker(workerid=99)
        self.assertEqual(slavedict, None)

    @defer.inlineCallbacks
    def test_getBuildslave_by_name_no_such(self):
        yield self.insertTestData(self.baseRows)
        slavedict = yield self.db.workers.getWorker(name='NOSUCH')
        self.assertEqual(slavedict, None)

    @defer.inlineCallbacks
    def test_getBuildslave_not_configured(self):
        yield self.insertTestData(self.baseRows)
        slavedict = yield self.db.workers.getWorker(workerid=30)
        validation.verifyDbDict(self, 'workerdict', slavedict)
        self.assertEqual(slavedict,
                         dict(id=30, name='zero', slaveinfo={'a': 'b'},
                              connected_to=[], configured_on=[]))

    @defer.inlineCallbacks
    def test_getBuildslave_connected_not_configured(self):
        yield self.insertTestData(self.baseRows + [
            # the worker is connected to this master, but not configured.
            # weird, but the DB should represent it.
            fakedb.Worker(id=32, name='two'),
            fakedb.ConnectedWorker(workerid=32, masterid=11),
        ])
        slavedict = yield self.db.workers.getWorker(workerid=32)
        validation.verifyDbDict(self, 'workerdict', slavedict)
        self.assertEqual(slavedict,
                         dict(id=32, name='two', slaveinfo={'a': 'b'},
                              connected_to=[11], configured_on=[]))

    @defer.inlineCallbacks
    def test_getBuildslave_multiple_connections(self):
        yield self.insertTestData(self.baseRows + [
            # the worker is connected to two masters at once.
            # weird, but the DB should represent it.
            fakedb.Worker(id=32, name='two'),
            fakedb.ConnectedWorker(workerid=32, masterid=10),
            fakedb.ConnectedWorker(workerid=32, masterid=11),
            fakedb.BuilderMaster(id=24, builderid=20, masterid=10),
            fakedb.BuilderMaster(id=25, builderid=20, masterid=11),
            fakedb.ConfiguredWorker(workerid=32, buildermasterid=24),
            fakedb.ConfiguredWorker(workerid=32, buildermasterid=25),
        ])
        slavedict = yield self.db.workers.getWorker(workerid=32)
        validation.verifyDbDict(self, 'workerdict', slavedict)
        self.assertEqual(slavedict,
                         dict(id=32, name='two', slaveinfo={'a': 'b'},
                              connected_to=[10, 11], configured_on=[
                                  {'builderid': 20, 'masterid': 10},
                                  {'builderid': 20, 'masterid': 11},
                                  ]))

    @defer.inlineCallbacks
    def test_getBuildslave_by_name_not_configured(self):
        yield self.insertTestData(self.baseRows)
        slavedict = yield self.db.workers.getWorker(name='zero')
        validation.verifyDbDict(self, 'workerdict', slavedict)
        self.assertEqual(slavedict,
                         dict(id=30, name='zero', slaveinfo={'a': 'b'},
                              connected_to=[], configured_on=[]))

    @defer.inlineCallbacks
    def test_getBuildslave_not_connected(self):
        yield self.insertTestData(self.baseRows + [
            fakedb.BuilderMaster(id=12, builderid=20, masterid=10),
            fakedb.ConfiguredWorker(workerid=30, buildermasterid=12),
        ])
        slavedict = yield self.db.workers.getWorker(workerid=30)
        validation.verifyDbDict(self, 'workerdict', slavedict)
        self.assertEqual(slavedict,
                         dict(id=30, name='zero', slaveinfo={'a': 'b'},
                              configured_on=[
                                  {'masterid': 10, 'builderid': 20}],
                              connected_to=[]))

    @defer.inlineCallbacks
    def test_getBuildslave_connected(self):
        yield self.insertTestData(self.baseRows + [
            fakedb.BuilderMaster(id=12, builderid=20, masterid=10),
            fakedb.ConfiguredWorker(workerid=30, buildermasterid=12),
            fakedb.ConnectedWorker(workerid=30, masterid=10),
        ])
        slavedict = yield self.db.workers.getWorker(workerid=30)
        validation.verifyDbDict(self, 'workerdict', slavedict)
        self.assertEqual(slavedict,
                         dict(id=30, name='zero', slaveinfo={'a': 'b'},
                              configured_on=[
                                  {'masterid': 10, 'builderid': 20}],
                              connected_to=[10]))

    @defer.inlineCallbacks
    def test_getBuildslave_with_multiple_masters(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        slavedict = yield self.db.workers.getWorker(workerid=30)
        validation.verifyDbDict(self, 'workerdict', slavedict)
        slavedict['configured_on'].sort()
        self.assertEqual(slavedict,
                         dict(id=30, name='zero', slaveinfo={'a': 'b'},
                              configured_on=sorted([
                                  {'masterid': 10, 'builderid': 20},
                                  {'masterid': 10, 'builderid': 21},
                                  {'masterid': 11, 'builderid': 20},
                              ]), connected_to=[10]))

    @defer.inlineCallbacks
    def test_getBuildslave_with_multiple_masters_builderid(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        slavedict = yield self.db.workers.getWorker(workerid=30, builderid=20)
        validation.verifyDbDict(self, 'workerdict', slavedict)
        slavedict['configured_on'].sort()
        self.assertEqual(slavedict,
                         dict(id=30, name='zero', slaveinfo={'a': 'b'},
                              configured_on=sorted([
                                  {'masterid': 10, 'builderid': 20},
                                  {'masterid': 11, 'builderid': 20},
                              ]), connected_to=[10]))

    @defer.inlineCallbacks
    def test_getBuildslave_with_multiple_masters_masterid(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        slavedict = yield self.db.workers.getWorker(workerid=30, masterid=11)
        validation.verifyDbDict(self, 'workerdict', slavedict)
        self.assertEqual(slavedict,
                         dict(id=30, name='zero', slaveinfo={'a': 'b'},
                              configured_on=[
                                  {'masterid': 11, 'builderid': 20},
                                  ], connected_to=[]))

    @defer.inlineCallbacks
    def test_getBuildslave_with_multiple_masters_builderid_masterid(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        slavedict = yield self.db.workers.getWorker(workerid=30,
                                                    builderid=20, masterid=11)
        validation.verifyDbDict(self, 'workerdict', slavedict)
        self.assertEqual(slavedict,
                         dict(id=30, name='zero', slaveinfo={'a': 'b'},
                              configured_on=[
                                  {'masterid': 11, 'builderid': 20},
                                  ], connected_to=[]))

    @defer.inlineCallbacks
    def test_getBuildslave_by_name_with_multiple_masters_builderid_masterid(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        slavedict = yield self.db.workers.getWorker(name='zero',
                                                    builderid=20, masterid=11)
        validation.verifyDbDict(self, 'workerdict', slavedict)
        self.assertEqual(slavedict,
                         dict(id=30, name='zero', slaveinfo={'a': 'b'},
                              configured_on=[
                                  {'masterid': 11, 'builderid': 20},
                                  ], connected_to=[]))

    @defer.inlineCallbacks
    def test_getBuildslaves_no_config(self):
        yield self.insertTestData(self.baseRows)
        slavedicts = yield self.db.workers.getWorkers()
        [validation.verifyDbDict(self, 'workerdict', slavedict)
         for slavedict in slavedicts]
        self.assertEqual(sorted(slavedicts), sorted([
            dict(id=30, name='zero', slaveinfo={'a': 'b'},
                 configured_on=[], connected_to=[]),
            dict(id=31, name='one', slaveinfo={'a': 'b'},
                 configured_on=[], connected_to=[]),
        ]))

    @defer.inlineCallbacks
    def test_getBuildslaves_with_config(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        slavedicts = yield self.db.workers.getWorkers()
        for slavedict in slavedicts:
            validation.verifyDbDict(self, 'workerdict', slavedict)
            slavedict['configured_on'].sort()
        self.assertEqual(sorted(slavedicts), sorted([
            dict(id=30, name='zero', slaveinfo={'a': 'b'},
                 configured_on=sorted([
                     {'masterid': 10, 'builderid': 20},
                     {'masterid': 10, 'builderid': 21},
                     {'masterid': 11, 'builderid': 20},
                 ]), connected_to=[10]),
            dict(id=31, name='one', slaveinfo={'a': 'b'},
                 configured_on=sorted([
                     {'masterid': 11, 'builderid': 20},
                     {'masterid': 11, 'builderid': 22},
                 ]), connected_to=[11]),
        ]))

    @defer.inlineCallbacks
    def test_getBuildslaves_empty(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        slavedicts = yield self.db.workers.getWorkers(masterid=11, builderid=21)
        for slavedict in slavedicts:
            validation.verifyDbDict(self, 'workerdict', slavedict)
            slavedict['configured_on'].sort()
        self.assertEqual(sorted(slavedicts), [])

    @defer.inlineCallbacks
    def test_getBuildslaves_with_config_builderid(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        slavedicts = yield self.db.workers.getWorkers(builderid=20)
        for slavedict in slavedicts:
            validation.verifyDbDict(self, 'workerdict', slavedict)
            slavedict['configured_on'].sort()
        self.assertEqual(sorted(slavedicts), sorted([
            dict(id=30, name='zero', slaveinfo={'a': 'b'},
                 configured_on=sorted([
                     {'masterid': 10, 'builderid': 20},
                     {'masterid': 11, 'builderid': 20},
                 ]), connected_to=[10]),
            dict(id=31, name='one', slaveinfo={'a': 'b'},
                 configured_on=sorted([
                     {'masterid': 11, 'builderid': 20},
                 ]), connected_to=[11]),
        ]))

    @defer.inlineCallbacks
    def test_getBuildslaves_with_config_masterid_10(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        slavedicts = yield self.db.workers.getWorkers(masterid=10)
        for slavedict in slavedicts:
            validation.verifyDbDict(self, 'workerdict', slavedict)
            slavedict['configured_on'].sort()
        self.assertEqual(sorted(slavedicts), sorted([
            dict(id=30, name='zero', slaveinfo={'a': 'b'},
                 configured_on=sorted([
                     {'masterid': 10, 'builderid': 20},
                     {'masterid': 10, 'builderid': 21},
                 ]), connected_to=[10]),
        ]))

    @defer.inlineCallbacks
    def test_getBuildslaves_with_config_masterid_11(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        slavedicts = yield self.db.workers.getWorkers(masterid=11)
        for slavedict in slavedicts:
            validation.verifyDbDict(self, 'workerdict', slavedict)
            slavedict['configured_on'].sort()
        self.assertEqual(sorted(slavedicts), sorted([
            dict(id=30, name='zero', slaveinfo={'a': 'b'},
                 configured_on=sorted([
                     {'masterid': 11, 'builderid': 20},
                 ]), connected_to=[]),
            dict(id=31, name='one', slaveinfo={'a': 'b'},
                 configured_on=sorted([
                     {'masterid': 11, 'builderid': 20},
                     {'masterid': 11, 'builderid': 22},
                 ]), connected_to=[11]),
        ]))

    @defer.inlineCallbacks
    def test_getBuildslaves_with_config_masterid_11_builderid_22(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        slavedicts = yield self.db.workers.getWorkers(
            masterid=11, builderid=22)
        for slavedict in slavedicts:
            validation.verifyDbDict(self, 'workerdict', slavedict)
            slavedict['configured_on'].sort()
        self.assertEqual(sorted(slavedicts), sorted([
            dict(id=31, name='one', slaveinfo={'a': 'b'},
                 configured_on=sorted([
                     {'masterid': 11, 'builderid': 22},
                 ]), connected_to=[11]),
        ]))

    @defer.inlineCallbacks
    def test_buildslaveConnected_existing(self):
        yield self.insertTestData(self.baseRows + self.buildslave1_rows)

        NEW_INFO = {'other': [1, 2, 3]}

        yield self.db.workers.workerConnected(
            workerid=self.BS1_ID, masterid=11, workerinfo=NEW_INFO)

        bs = yield self.db.workers.getWorker(self.BS1_ID)
        self.assertEqual(bs, {
            'id': self.BS1_ID,
            'name': self.BS1_NAME,
            'slaveinfo': NEW_INFO,
            'configured_on': [],
            'connected_to': [11]})

    @defer.inlineCallbacks
    def test_buildslaveConnected_already_connected(self):
        yield self.insertTestData(self.baseRows + self.buildslave1_rows + [
            fakedb.ConnectedWorker(id=888,
                                   workerid=self.BS1_ID, masterid=11),
        ])
        yield self.db.workers.workerConnected(
            workerid=self.BS1_ID, masterid=11, workerinfo={})

        bs = yield self.db.workers.getWorker(self.BS1_ID)
        self.assertEqual(bs['connected_to'], [11])

    @defer.inlineCallbacks
    def test_buildslaveDisconnected(self):
        yield self.insertTestData(self.baseRows + self.buildslave1_rows + [
            fakedb.ConnectedWorker(id=888,
                                   workerid=self.BS1_ID, masterid=10),
            fakedb.ConnectedWorker(id=889,
                                   workerid=self.BS1_ID, masterid=11),
        ])
        yield self.db.workers.workerDisconnected(
            workerid=self.BS1_ID, masterid=11)

        bs = yield self.db.workers.getWorker(self.BS1_ID)
        self.assertEqual(bs['connected_to'], [10])

    @defer.inlineCallbacks
    def test_buildslaveDisconnected_already_disconnected(self):
        yield self.insertTestData(self.baseRows + self.buildslave1_rows)
        yield self.db.workers.workerDisconnected(
            workerid=self.BS1_ID, masterid=11)

        bs = yield self.db.workers.getWorker(self.BS1_ID)
        self.assertEqual(bs['connected_to'], [])

    @defer.inlineCallbacks
    def test_buildslaveConfigured(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)

        # should remove builder 21, and add 22
        yield self.db.workers.deconfigureAllWorkersForMaster(masterid=10)

        yield self.db.workers.workerConfigured(
            workerid=30, masterid=10, builderids=[20, 22])

        bs = yield self.db.workers.getWorker(30)
        self.assertEqual(sorted(bs['configured_on']), sorted([
            {'builderid': 20, 'masterid': 11},
            {'builderid': 20, 'masterid': 10},
            {'builderid': 22, 'masterid': 10}]))

    @defer.inlineCallbacks
    def test_buildslaveConfiguredTwice(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)

        # should remove builder 21, and add 22
        yield self.db.workers.deconfigureAllWorkersForMaster(masterid=10)

        yield self.db.workers.workerConfigured(
            workerid=30, masterid=10, builderids=[20, 22])

        # configure again (should eat the duplicate insertion errors)
        yield self.db.workers.workerConfigured(
            workerid=30, masterid=10, builderids=[20, 21, 22])

        bs = yield self.db.workers.getWorker(30)
        self.assertEqual(sorted(bs['configured_on']), sorted([
            {'builderid': 20, 'masterid': 11},
            {'builderid': 20, 'masterid': 10},
            {'builderid': 21, 'masterid': 10},
            {'builderid': 22, 'masterid': 10}]))

    @defer.inlineCallbacks
    def test_workerReConfigured(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)

        # should remove builder 21, and add 22
        yield self.db.workers.workerConfigured(
            workerid=30, masterid=10, builderids=[20, 22])

        bs = yield self.db.workers.getWorker(30)
        self.assertEqual(sorted(bs['configured_on']), sorted([
            {'builderid': 20, 'masterid': 11},
            {'builderid': 20, 'masterid': 10},
            {'builderid': 22, 'masterid': 10}]))

    @defer.inlineCallbacks
    def test_workerUnconfigured(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)

        # should remove all builders from master 10
        yield self.db.workers.workerConfigured(
            workerid=30, masterid=10, builderids=[])

        bs = yield self.db.workers.getWorker(30)
        self.assertEqual(sorted(bs['configured_on']), sorted([
            {'builderid': 20, 'masterid': 11}]))

    @defer.inlineCallbacks
    def test_nothingConfigured(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)

        # should remove builder 21, and add 22
        yield self.db.workers.deconfigureAllWorkersForMaster(masterid=10)
        yield self.db.workers.workerConfigured(
            workerid=30, masterid=10, builderids=[])

        # should only keep builder for master 11
        bs = yield self.db.workers.getWorker(30)
        self.assertEqual(sorted(bs['configured_on']), sorted([
            {'builderid': 20, 'masterid': 11}]))

    @defer.inlineCallbacks
    def test_deconfiguredAllSlaves(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)

        res = yield self.db.workers.getWorkers(masterid=11)
        self.assertEqual(len(res), 2)

        # should remove all worker configured for masterid 11
        yield self.db.workers.deconfigureAllWorkersForMaster(masterid=11)

        res = yield self.db.workers.getWorkers(masterid=11)
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
            table_names=['workers', 'masters', 'builders',
                         'builder_masters', 'connected_workers',
                         'configured_workers'])

        @d.addCallback
        def finish_setup(_):
            self.db.workers = \
                worker.WorkersConnectorComponent(self.db)
        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()


class TestWorkerTransition(unittest.TestCase):

    def test_WorkerBuildStep(self):
        with ignoreWarning(DeprecatedWorkerModuleWarning):
            from buildbot.db.buildslave import BuildslavesConnectorComponent

        class C(BuildslavesConnectorComponent):

            def __init__(self):
                pass

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'BuildslavesConnectorComponent' class is deprecated"):
            c = C()
            self.assertIsInstance(c, worker.WorkersConnectorComponent)

    def test_getWorkers_old_api(self):
        method = mock.Mock(return_value='dummy')
        with mock.patch(
                'buildbot.db.worker.WorkersConnectorComponent.getWorkers',
                method):
            m = worker.WorkersConnectorComponent(mock.Mock())
            with assertProducesWarning(
                    DeprecatedWorkerNameWarning,
                    message_pattern="'getBuildslaves' method is deprecated"):
                dummy = m.getBuildslaves()
        self.assertEqual(dummy, 'dummy')
        method.assert_called_once_with()
