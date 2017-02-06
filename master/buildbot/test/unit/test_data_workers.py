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
from __future__ import print_function

import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.data import workers
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import endpoint
from buildbot.test.util import interfaces

testData = [
    fakedb.Builder(id=40, name=u'b1'),
    fakedb.Builder(id=41, name=u'b2'),
    fakedb.Master(id=13),
    fakedb.Master(id=14),
    fakedb.BuilderMaster(id=4013, builderid=40, masterid=13),
    fakedb.BuilderMaster(id=4014, builderid=40, masterid=14),
    fakedb.BuilderMaster(id=4113, builderid=41, masterid=13),

    fakedb.Worker(id=1, name=u'linux', info={}),
    fakedb.ConfiguredWorker(id=14013,
                            workerid=1, buildermasterid=4013),
    fakedb.ConfiguredWorker(id=14014,
                            workerid=1, buildermasterid=4014),
    fakedb.ConnectedWorker(id=113, masterid=13, workerid=1),

    fakedb.Worker(id=2, name=u'windows', info={"a": "b"}),
    fakedb.ConfiguredWorker(id=24013,
                            workerid=2, buildermasterid=4013),
    fakedb.ConfiguredWorker(id=24014,
                            workerid=2, buildermasterid=4014),
    fakedb.ConfiguredWorker(id=24113,
                            workerid=2, buildermasterid=4113),
    fakedb.ConnectedWorker(id=214, masterid=14, workerid=2),
]


def configuredOnKey(worker):
    return (worker.get('masterid', 0),
            worker.get('builderid', 0))


def _filt(bs, builderid, masterid):
    bs['connected_to'] = sorted(
        [d for d in bs['connected_to']
         if not masterid or masterid == d['masterid']])
    bs['configured_on'] = sorted(
        [d for d in bs['configured_on']
         if (not masterid or masterid == d['masterid'])
         and (not builderid or builderid == d['builderid'])], key=configuredOnKey)
    return bs


def w1(builderid=None, masterid=None):
    return _filt({
        'workerid': 1,
        'name': 'linux',
        'workerinfo': {},
        'connected_to': [
            {'masterid': 13},
        ],
        'configured_on': sorted([
            {'builderid': 40, 'masterid': 13},
            {'builderid': 40, 'masterid': 14},
        ], key=configuredOnKey),
    }, builderid, masterid)


def w2(builderid=None, masterid=None):
    return _filt({
        'workerid': 2,
        'name': 'windows',
        'workerinfo': {'a': 'b'},
        'connected_to': [
            {'masterid': 14},
        ],
        'configured_on': sorted([
            {'builderid': 40, 'masterid': 13},
            {'builderid': 41, 'masterid': 13},
            {'builderid': 40, 'masterid': 14},
        ], key=configuredOnKey),
    }, builderid, masterid)


class WorkerEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = workers.WorkerEndpoint
    resourceTypeClass = workers.Worker

    def setUp(self):
        self.setUpEndpoint()
        return self.db.insertTestData(testData)

    def tearDown(self):
        self.tearDownEndpoint()

    def test_get_existing(self):
        d = self.callGet(('workers', 2))

        @d.addCallback
        def check(worker):
            self.validateData(worker)
            worker['configured_on'] = sorted(
                worker['configured_on'], key=configuredOnKey)
            self.assertEqual(worker, w2())
        return d

    def test_get_existing_name(self):
        d = self.callGet(('workers', 'linux'))

        @d.addCallback
        def check(worker):
            self.validateData(worker)
            worker['configured_on'] = sorted(
                worker['configured_on'], key=configuredOnKey)
            self.assertEqual(worker, w1())
        return d

    def test_get_existing_masterid(self):
        d = self.callGet(('masters', 14, 'workers', 2))

        @d.addCallback
        def check(worker):
            self.validateData(worker)
            worker['configured_on'] = sorted(
                worker['configured_on'], key=configuredOnKey)
            self.assertEqual(worker, w2(masterid=14))
        return d

    def test_get_existing_builderid(self):
        d = self.callGet(('builders', 40, 'workers', 2))

        @d.addCallback
        def check(worker):
            self.validateData(worker)
            worker['configured_on'] = sorted(
                worker['configured_on'], key=configuredOnKey)
            self.assertEqual(worker, w2(builderid=40))
        return d

    def test_get_existing_masterid_builderid(self):
        d = self.callGet(('masters', 13, 'builders', 40, 'workers', 2))

        @d.addCallback
        def check(worker):
            self.validateData(worker)
            worker['configured_on'] = sorted(
                worker['configured_on'], key=configuredOnKey)
            self.assertEqual(worker, w2(masterid=13, builderid=40))
        return d

    def test_get_missing(self):
        d = self.callGet(('workers', 99))

        @d.addCallback
        def check(worker):
            self.assertEqual(worker, None)
        return d


class WorkersEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = workers.WorkersEndpoint
    resourceTypeClass = workers.Worker

    def setUp(self):
        self.setUpEndpoint()
        return self.db.insertTestData(testData)

    def tearDown(self):
        self.tearDownEndpoint()

    def test_get(self):
        d = self.callGet(('workers',))

        @d.addCallback
        def check(workers):
            for b in workers:
                self.validateData(b)
                b['configured_on'] = sorted(b['configured_on'],
                                            key=configuredOnKey)
            self.assertEqual(sorted(workers, key=configuredOnKey),
                             sorted([w1(), w2()], key=configuredOnKey))
        return d

    def test_get_masterid(self):
        d = self.callGet(('masters', '13', 'workers',))

        @d.addCallback
        def check(workers):
            [self.validateData(b) for b in workers]
            [sorted(b['configured_on'], key=configuredOnKey) for b in workers]
            self.assertEqual(sorted(workers, key=configuredOnKey),
                             sorted([w1(masterid=13), w2(masterid=13)], key=configuredOnKey))
        return d

    def test_get_builderid(self):
        d = self.callGet(('builders', '41', 'workers',))

        @d.addCallback
        def check(workers):
            [self.validateData(b) for b in workers]
            [sorted(b['configured_on'], key=configuredOnKey) for b in workers]
            self.assertEqual(sorted(workers, key=configuredOnKey),
                             sorted([w2(builderid=41)], key=configuredOnKey))
        return d

    def test_get_masterid_builderid(self):
        d = self.callGet(('masters', '13', 'builders', '41', 'workers',))

        @d.addCallback
        def check(workers):
            [self.validateData(b) for b in workers]
            [sorted(b['configured_on'], key=configuredOnKey) for b in workers]
            self.assertEqual(sorted(workers, key=configuredOnKey),
                             sorted([w2(masterid=13, builderid=41)], key=configuredOnKey))
        return d


class Worker(interfaces.InterfaceTests, unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self,
                                             wantMq=True, wantDb=True, wantData=True)
        self.rtype = workers.Worker(self.master)
        return self.master.db.insertTestData([
            fakedb.Master(id=13),
            fakedb.Master(id=14),
        ])

    def test_signature_findWorkerId(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.findWorkerId,  # fake
            self.rtype.findWorkerId)  # real
        def findWorkerId(self, name):
            pass

    def test_signature_workerConfigured(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.workerConfigured,  # fake
            self.rtype.workerConfigured)  # real
        def workerConfigured(self, workerid, masterid, builderids):
            pass

    def test_findWorkerId(self):
        # this just passes through to the db method, so test that
        rv = defer.succeed(None)
        self.master.db.workers.findWorkerId = \
            mock.Mock(return_value=rv)
        self.assertIdentical(self.rtype.findWorkerId(u'foo'), rv)

    def test_findWorkerId_not_id(self):
        self.assertRaises(ValueError, self.rtype.findWorkerId, b'foo')
        self.assertRaises(ValueError, self.rtype.findWorkerId, u'123/foo')
