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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from future.builtins import range

import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.db import workers
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import connector_component
from buildbot.test.util import interfaces
from buildbot.test.util import querylog
from buildbot.test.util import validation
from buildbot.test.util.warnings import assertProducesWarning
from buildbot.worker_transition import DeprecatedWorkerNameWarning


def workerKey(worker):
    return worker['id']


def configuredOnKey(worker):
    return (worker['builderid'], worker['masterid'])


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

    # sample worker data, with id's avoiding the postgres id sequence

    BOGUS_NAME = 'bogus'

    W1_NAME, W1_ID, W1_INFO = 'w1', 100, {'a': 1}
    worker1_rows = [
        fakedb.Worker(id=W1_ID, name=W1_NAME, info=W1_INFO),
    ]

    W2_NAME, W2_ID, W2_INFO = 'w2', 200, {'a': 1, 'b': 2}
    worker2_rows = [
        fakedb.Worker(id=W2_ID, name=W2_NAME, info=W2_INFO),
    ]

    # tests

    def test_signature_findWorkerId(self):
        @self.assertArgSpecMatches(self.db.workers.findWorkerId)
        def findWorkerId(self, name):
            pass

    def test_signature_getWorker(self):
        @self.assertArgSpecMatches(self.db.workers.getWorker)
        def getWorker(self, workerid=None, name=None,
                      masterid=None, builderid=None):
            pass

    def test_signature_getWorkers(self):
        @self.assertArgSpecMatches(self.db.workers.getWorkers)
        def getWorkers(self, masterid=None, builderid=None):
            pass

    def test_signature_workerConnected(self):
        @self.assertArgSpecMatches(self.db.workers.workerConnected)
        def workerConnected(self, workerid, masterid, workerinfo):
            pass

    def test_signature_workerDisconnected(self):
        @self.assertArgSpecMatches(self.db.workers.workerDisconnected)
        def workerDisconnected(self, workerid, masterid):
            pass

    def test_signature_workerConfigured(self):
        @self.assertArgSpecMatches(self.db.workers.workerConfigured)
        def workerConfigured(self, workerid, masterid, builderids):
            pass

    def test_signature_deconfigureAllWorkersForMaster(self):
        @self.assertArgSpecMatches(self.db.workers.deconfigureAllWorkersForMaster)
        def deconfigureAllWorkersForMaster(self, masterid):
            pass

    @defer.inlineCallbacks
    def test_findWorkerId_insert(self):
        id = yield self.db.workers.findWorkerId(name=u"xyz")
        worker = yield self.db.workers.getWorker(workerid=id)
        self.assertEqual(worker['name'], 'xyz')
        self.assertEqual(worker['workerinfo'], {})

    @defer.inlineCallbacks
    def test_findWorkerId_existing(self):
        yield self.insertTestData(self.baseRows)
        id = yield self.db.workers.findWorkerId(name=u"one")
        self.assertEqual(id, 31)

    @defer.inlineCallbacks
    def test_getWorker_no_such(self):
        yield self.insertTestData(self.baseRows)
        workerdict = yield self.db.workers.getWorker(workerid=99)
        self.assertEqual(workerdict, None)

    @defer.inlineCallbacks
    def test_getWorker_by_name_no_such(self):
        yield self.insertTestData(self.baseRows)
        workerdict = yield self.db.workers.getWorker(name='NOSUCH')
        self.assertEqual(workerdict, None)

    @defer.inlineCallbacks
    def test_getWorker_not_configured(self):
        yield self.insertTestData(self.baseRows)
        workerdict = yield self.db.workers.getWorker(workerid=30)
        validation.verifyDbDict(self, 'workerdict', workerdict)
        self.assertEqual(workerdict,
                         dict(id=30, name='zero', workerinfo={'a': 'b'},
                              connected_to=[], configured_on=[]))

    @defer.inlineCallbacks
    def test_getWorker_connected_not_configured(self):
        yield self.insertTestData(self.baseRows + [
            # the worker is connected to this master, but not configured.
            # weird, but the DB should represent it.
            fakedb.Worker(id=32, name='two'),
            fakedb.ConnectedWorker(workerid=32, masterid=11),
        ])
        workerdict = yield self.db.workers.getWorker(workerid=32)
        validation.verifyDbDict(self, 'workerdict', workerdict)
        self.assertEqual(workerdict,
                         dict(id=32, name='two', workerinfo={'a': 'b'},
                              connected_to=[11], configured_on=[]))

    @defer.inlineCallbacks
    def test_getWorker_multiple_connections(self):
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
        workerdict = yield self.db.workers.getWorker(workerid=32)
        validation.verifyDbDict(self, 'workerdict', workerdict)
        self.assertEqual(workerdict,
                         dict(id=32, name='two', workerinfo={'a': 'b'},
                              connected_to=[10, 11], configured_on=[
                                  {'builderid': 20, 'masterid': 10},
                                  {'builderid': 20, 'masterid': 11},
                         ]))

    @defer.inlineCallbacks
    def test_getWorker_by_name_not_configured(self):
        yield self.insertTestData(self.baseRows)
        workerdict = yield self.db.workers.getWorker(name='zero')
        validation.verifyDbDict(self, 'workerdict', workerdict)
        self.assertEqual(workerdict,
                         dict(id=30, name='zero', workerinfo={'a': 'b'},
                              connected_to=[], configured_on=[]))

    @defer.inlineCallbacks
    def test_getWorker_not_connected(self):
        yield self.insertTestData(self.baseRows + [
            fakedb.BuilderMaster(id=12, builderid=20, masterid=10),
            fakedb.ConfiguredWorker(workerid=30, buildermasterid=12),
        ])
        workerdict = yield self.db.workers.getWorker(workerid=30)
        validation.verifyDbDict(self, 'workerdict', workerdict)
        self.assertEqual(workerdict,
                         dict(id=30, name='zero', workerinfo={'a': 'b'},
                              configured_on=[
                                  {'masterid': 10, 'builderid': 20}],
                              connected_to=[]))

    @defer.inlineCallbacks
    def test_getWorker_connected(self):
        yield self.insertTestData(self.baseRows + [
            fakedb.BuilderMaster(id=12, builderid=20, masterid=10),
            fakedb.ConfiguredWorker(workerid=30, buildermasterid=12),
            fakedb.ConnectedWorker(workerid=30, masterid=10),
        ])
        workerdict = yield self.db.workers.getWorker(workerid=30)
        validation.verifyDbDict(self, 'workerdict', workerdict)
        self.assertEqual(workerdict,
                         dict(id=30, name='zero', workerinfo={'a': 'b'},
                              configured_on=[
                                  {'masterid': 10, 'builderid': 20}],
                              connected_to=[10]))

    @defer.inlineCallbacks
    def test_getWorker_with_multiple_masters(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        workerdict = yield self.db.workers.getWorker(workerid=30)
        validation.verifyDbDict(self, 'workerdict', workerdict)
        workerdict['configured_on'] = sorted(
            workerdict['configured_on'], key=configuredOnKey)
        self.assertEqual(workerdict,
                         dict(id=30, name='zero', workerinfo={'a': 'b'},
                              configured_on=sorted([
                                  {'masterid': 10, 'builderid': 20},
                                  {'masterid': 10, 'builderid': 21},
                                  {'masterid': 11, 'builderid': 20},
                              ], key=configuredOnKey), connected_to=[10]))

    @defer.inlineCallbacks
    def test_getWorker_with_multiple_masters_builderid(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        workerdict = yield self.db.workers.getWorker(workerid=30, builderid=20)
        validation.verifyDbDict(self, 'workerdict', workerdict)
        workerdict['configured_on'] = sorted(
            workerdict['configured_on'], key=configuredOnKey)
        self.assertEqual(workerdict,
                         dict(id=30, name='zero', workerinfo={'a': 'b'},
                              configured_on=sorted([
                                  {'masterid': 10, 'builderid': 20},
                                  {'masterid': 11, 'builderid': 20},
                              ], key=configuredOnKey), connected_to=[10]))

    @defer.inlineCallbacks
    def test_getWorker_with_multiple_masters_masterid(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        workerdict = yield self.db.workers.getWorker(workerid=30, masterid=11)
        validation.verifyDbDict(self, 'workerdict', workerdict)
        self.assertEqual(workerdict,
                         dict(id=30, name='zero', workerinfo={'a': 'b'},
                              configured_on=[
                                  {'masterid': 11, 'builderid': 20},
                         ], connected_to=[]))

    @defer.inlineCallbacks
    def test_getWorker_with_multiple_masters_builderid_masterid(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        workerdict = yield self.db.workers.getWorker(workerid=30,
                                                     builderid=20, masterid=11)
        validation.verifyDbDict(self, 'workerdict', workerdict)
        self.assertEqual(workerdict,
                         dict(id=30, name='zero', workerinfo={'a': 'b'},
                              configured_on=[
                                  {'masterid': 11, 'builderid': 20},
                         ], connected_to=[]))

    @defer.inlineCallbacks
    def test_getWorker_by_name_with_multiple_masters_builderid_masterid(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        workerdict = yield self.db.workers.getWorker(name='zero',
                                                     builderid=20, masterid=11)
        validation.verifyDbDict(self, 'workerdict', workerdict)
        self.assertEqual(workerdict,
                         dict(id=30, name='zero', workerinfo={'a': 'b'},
                              configured_on=[
                                  {'masterid': 11, 'builderid': 20},
                         ], connected_to=[]))

    @defer.inlineCallbacks
    def test_getWorkers_no_config(self):
        yield self.insertTestData(self.baseRows)
        workerdicts = yield self.db.workers.getWorkers()
        [validation.verifyDbDict(self, 'workerdict', workerdict)
         for workerdict in workerdicts]
        self.assertEqual(sorted(workerdicts, key=workerKey), sorted([
            dict(id=30, name='zero', workerinfo={'a': 'b'},
                 configured_on=[], connected_to=[]),
            dict(id=31, name='one', workerinfo={'a': 'b'},
                 configured_on=[], connected_to=[]),
        ], key=workerKey))

    @defer.inlineCallbacks
    def test_getWorkers_with_config(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        workerdicts = yield self.db.workers.getWorkers()
        for workerdict in workerdicts:
            validation.verifyDbDict(self, 'workerdict', workerdict)
            workerdict['configured_on'] = sorted(
                workerdict['configured_on'], key=configuredOnKey)
        self.assertEqual(sorted(workerdicts, key=workerKey), sorted([
            dict(id=30, name='zero', workerinfo={'a': 'b'},
                 configured_on=sorted([
                     {'masterid': 10, 'builderid': 20},
                     {'masterid': 10, 'builderid': 21},
                     {'masterid': 11, 'builderid': 20},
                 ], key=configuredOnKey), connected_to=[10]),
            dict(id=31, name='one', workerinfo={'a': 'b'},
                 configured_on=sorted([
                     {'masterid': 11, 'builderid': 20},
                     {'masterid': 11, 'builderid': 22},
                 ], key=configuredOnKey), connected_to=[11]),
        ], key=workerKey))

    @defer.inlineCallbacks
    def test_getWorkers_empty(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        workerdicts = yield self.db.workers.getWorkers(masterid=11, builderid=21)
        for workerdict in workerdicts:
            validation.verifyDbDict(self, 'workerdict', workerdict)
            workerdict['configured_on'] = sorted(
                workerdict['configured_on'], key=configuredOnKey)
        self.assertEqual(sorted(workerdicts, key=workerKey), [])

    @defer.inlineCallbacks
    def test_getWorkers_with_config_builderid(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        workerdicts = yield self.db.workers.getWorkers(builderid=20)
        for workerdict in workerdicts:
            validation.verifyDbDict(self, 'workerdict', workerdict)
            workerdict['configured_on'] = sorted(
                workerdict['configured_on'], key=configuredOnKey)
        self.assertEqual(sorted(workerdicts, key=workerKey), sorted([
            dict(id=30, name='zero', workerinfo={'a': 'b'},
                 configured_on=sorted([
                     {'masterid': 10, 'builderid': 20},
                     {'masterid': 11, 'builderid': 20},
                 ], key=configuredOnKey), connected_to=[10]),
            dict(id=31, name='one', workerinfo={'a': 'b'},
                 configured_on=sorted([
                     {'masterid': 11, 'builderid': 20},
                 ], key=configuredOnKey), connected_to=[11]),
        ], key=workerKey))

    @defer.inlineCallbacks
    def test_getWorkers_with_config_masterid_10(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        workerdicts = yield self.db.workers.getWorkers(masterid=10)
        for workerdict in workerdicts:
            validation.verifyDbDict(self, 'workerdict', workerdict)
            workerdict['configured_on'] = sorted(
                workerdict['configured_on'], key=configuredOnKey)
        self.assertEqual(sorted(workerdicts, key=workerKey), sorted([
            dict(id=30, name='zero', workerinfo={'a': 'b'},
                 configured_on=sorted([
                     {'masterid': 10, 'builderid': 20},
                     {'masterid': 10, 'builderid': 21},
                 ], key=configuredOnKey), connected_to=[10]),
        ], key=workerKey))

    @defer.inlineCallbacks
    def test_getWorkers_with_config_masterid_11(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        workerdicts = yield self.db.workers.getWorkers(masterid=11)
        for workerdict in workerdicts:
            validation.verifyDbDict(self, 'workerdict', workerdict)
            workerdict['configured_on'] = sorted(
                workerdict['configured_on'], key=configuredOnKey)
        self.assertEqual(sorted(workerdicts, key=workerKey), sorted([
            dict(id=30, name='zero', workerinfo={'a': 'b'},
                 configured_on=sorted([
                     {'masterid': 11, 'builderid': 20},
                 ], key=configuredOnKey), connected_to=[]),
            dict(id=31, name='one', workerinfo={'a': 'b'},
                 configured_on=sorted([
                     {'masterid': 11, 'builderid': 20},
                     {'masterid': 11, 'builderid': 22},
                 ], key=configuredOnKey), connected_to=[11]),
        ], key=workerKey))

    @defer.inlineCallbacks
    def test_getWorkers_with_config_masterid_11_builderid_22(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)
        workerdicts = yield self.db.workers.getWorkers(
            masterid=11, builderid=22)
        for workerdict in workerdicts:
            validation.verifyDbDict(self, 'workerdict', workerdict)
            workerdict['configured_on'] = sorted(
                workerdict['configured_on'], key=configuredOnKey)
        self.assertEqual(sorted(workerdicts, key=workerKey), sorted([
            dict(id=31, name='one', workerinfo={'a': 'b'},
                 configured_on=sorted([
                     {'masterid': 11, 'builderid': 22},
                 ], key=configuredOnKey), connected_to=[11]),
        ], key=workerKey))

    @defer.inlineCallbacks
    def test_workerConnected_existing(self):
        yield self.insertTestData(self.baseRows + self.worker1_rows)

        NEW_INFO = {'other': [1, 2, 3]}

        yield self.db.workers.workerConnected(
            workerid=self.W1_ID, masterid=11, workerinfo=NEW_INFO)

        w = yield self.db.workers.getWorker(self.W1_ID)
        self.assertEqual(w, {
            'id': self.W1_ID,
            'name': self.W1_NAME,
            'workerinfo': NEW_INFO,
            'configured_on': [],
            'connected_to': [11]})

    @defer.inlineCallbacks
    def test_workerConnected_already_connected(self):
        yield self.insertTestData(self.baseRows + self.worker1_rows + [
            fakedb.ConnectedWorker(id=888,
                                   workerid=self.W1_ID, masterid=11),
        ])
        yield self.db.workers.workerConnected(
            workerid=self.W1_ID, masterid=11, workerinfo={})

        w = yield self.db.workers.getWorker(self.W1_ID)
        self.assertEqual(w['connected_to'], [11])

    @defer.inlineCallbacks
    def test_workerDisconnected(self):
        yield self.insertTestData(self.baseRows + self.worker1_rows + [
            fakedb.ConnectedWorker(id=888,
                                   workerid=self.W1_ID, masterid=10),
            fakedb.ConnectedWorker(id=889,
                                   workerid=self.W1_ID, masterid=11),
        ])
        yield self.db.workers.workerDisconnected(
            workerid=self.W1_ID, masterid=11)

        w = yield self.db.workers.getWorker(self.W1_ID)
        self.assertEqual(w['connected_to'], [10])

    @defer.inlineCallbacks
    def test_workerDisconnected_already_disconnected(self):
        yield self.insertTestData(self.baseRows + self.worker1_rows)
        yield self.db.workers.workerDisconnected(
            workerid=self.W1_ID, masterid=11)

        w = yield self.db.workers.getWorker(self.W1_ID)
        self.assertEqual(w['connected_to'], [])

    @defer.inlineCallbacks
    def test_workerConfigured(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)

        # should remove builder 21, and add 22
        yield self.db.workers.deconfigureAllWorkersForMaster(masterid=10)

        yield self.db.workers.workerConfigured(
            workerid=30, masterid=10, builderids=[20, 22])

        w = yield self.db.workers.getWorker(30)
        self.assertEqual(sorted(w['configured_on'], key=configuredOnKey), sorted([
            {'builderid': 20, 'masterid': 11},
            {'builderid': 20, 'masterid': 10},
            {'builderid': 22, 'masterid': 10}], key=configuredOnKey))

    @defer.inlineCallbacks
    def test_workerConfiguredTwice(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)

        # should remove builder 21, and add 22
        yield self.db.workers.deconfigureAllWorkersForMaster(masterid=10)

        yield self.db.workers.workerConfigured(
            workerid=30, masterid=10, builderids=[20, 22])

        # configure again (should eat the duplicate insertion errors)
        yield self.db.workers.workerConfigured(
            workerid=30, masterid=10, builderids=[20, 21, 22])

        w = yield self.db.workers.getWorker(30)
        x1 = sorted(w['configured_on'], key=configuredOnKey)
        x2 = sorted([{'builderid': 20, 'masterid': 11},
                     {'builderid': 20, 'masterid': 10},
                     {'builderid': 21, 'masterid': 10},
                     {'builderid': 22, 'masterid': 10}],
                    key=configuredOnKey)
        self.assertEqual(x1, x2)

    @defer.inlineCallbacks
    def test_workerReConfigured(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)

        # should remove builder 21, and add 22
        yield self.db.workers.workerConfigured(
            workerid=30, masterid=10, builderids=[20, 22])

        w = yield self.db.workers.getWorker(30)
        w['configured_on'] = sorted(w['configured_on'], key=configuredOnKey)
        self.assertEqual(w['configured_on'],
                         sorted([{'builderid': 20, 'masterid': 11},
                                 {'builderid': 20, 'masterid': 10},
                                 {'builderid': 22, 'masterid': 10}],
                                key=configuredOnKey))

    @defer.inlineCallbacks
    def test_workerUnconfigured(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)

        # should remove all builders from master 10
        yield self.db.workers.workerConfigured(
            workerid=30, masterid=10, builderids=[])

        w = yield self.db.workers.getWorker(30)
        w['configured_on'] = sorted(w['configured_on'], key=configuredOnKey)
        expected = sorted([
            {'builderid': 20, 'masterid': 11}], key=configuredOnKey)
        self.assertEqual(w['configured_on'], expected)

    @defer.inlineCallbacks
    def test_nothingConfigured(self):
        yield self.insertTestData(self.baseRows + self.multipleMasters)

        # should remove builder 21, and add 22
        yield self.db.workers.deconfigureAllWorkersForMaster(masterid=10)
        yield self.db.workers.workerConfigured(
            workerid=30, masterid=10, builderids=[])

        # should only keep builder for master 11
        w = yield self.db.workers.getWorker(30)
        self.assertEqual(sorted(w['configured_on']), sorted([
            {'builderid': 20, 'masterid': 11}]))

    @defer.inlineCallbacks
    def test_deconfiguredAllWorkers(self):
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
                 RealTests, querylog.SqliteMaxVariableMixin):

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['workers', 'masters', 'builders',
                         'builder_masters', 'connected_workers',
                         'configured_workers'])

        @d.addCallback
        def finish_setup(_):
            self.db.workers = \
                workers.WorkersConnectorComponent(self.db)
        return d

    @defer.inlineCallbacks
    def test_workerConfiguredMany(self):
        manyWorkers = [
            fakedb.BuilderMaster(id=1000, builderid=20, masterid=10),
        ] + [
            fakedb.Worker(id=50 + n, name='zero' + str(n))
            for n in range(1000)
        ] + [
            fakedb.ConfiguredWorker(
                id=n + 3000, workerid=50 + n, buildermasterid=1000)
            for n in range(1000)
        ]
        yield self.insertTestData(self.baseRows + manyWorkers)

        # should successfully remove all ConfiguredWorker rows
        with self.assertNoMaxVariables():
            yield self.db.workers.deconfigureAllWorkersForMaster(masterid=10)

        w = yield self.db.workers.getWorker(30)
        self.assertEqual(sorted(w['configured_on']), [])

    @defer.inlineCallbacks
    def test_workerConfiguredManyBuilders(self):
        manyWorkers = [
            fakedb.Builder(id=100 + n, name=u'a' + str(n))
            for n in range(1000)
        ] + [
            fakedb.Worker(id=50 + n, name='zero' + str(n))
            for n in range(2000)
        ] + [
            fakedb.BuilderMaster(id=1000 + n, builderid=100 + n, masterid=10)
            for n in range(1000)
        ] + [
            fakedb.ConfiguredWorker(
                id=n + 3000, workerid=50 + n, buildermasterid=int(1000 + n / 2))
            for n in range(2000)
        ]
        yield self.insertTestData(self.baseRows + manyWorkers)

        # should successfully remove all ConfiguredWorker rows
        with self.assertNoMaxVariables():
            yield self.db.workers.deconfigureAllWorkersForMaster(masterid=10)
        w = yield self.db.workers.getWorker(30)
        self.assertEqual(sorted(w['configured_on']), [])

    def tearDown(self):
        return self.tearDownConnectorComponent()


class TestWorkerTransition(unittest.TestCase):

    def test_BuildslavesConnectorComponent_deprecated(self):
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="BuildslavesConnectorComponent was deprecated"):
            from buildbot.db.buildslaves import BuildslavesConnectorComponent

        self.assertIdentical(BuildslavesConnectorComponent,
                             workers.WorkersConnectorComponent)

    def test_getWorkers_old_api(self):
        method = mock.Mock(return_value='dummy')
        with mock.patch(
                'buildbot.db.workers.WorkersConnectorComponent.getWorkers',
                method):
            m = workers.WorkersConnectorComponent(mock.Mock())
            with assertProducesWarning(
                    DeprecatedWorkerNameWarning,
                    message_pattern="'getBuildslaves' method is deprecated"):
                dummy = m.getBuildslaves()
        self.assertEqual(dummy, 'dummy')
        method.assert_called_once_with()
