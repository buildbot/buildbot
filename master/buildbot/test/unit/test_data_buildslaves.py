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

from buildbot.data import buildslaves
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import endpoint
from buildbot.test.util import interfaces
from twisted.internet import defer
from twisted.trial import unittest

testData = [
    fakedb.Builder(id=40, name=u'b1'),
    fakedb.Builder(id=41, name=u'b2'),
    fakedb.Master(id=13),
    fakedb.Master(id=14),
    fakedb.BuilderMaster(id=4013, builderid=40, masterid=13),
    fakedb.BuilderMaster(id=4014, builderid=40, masterid=14),
    fakedb.BuilderMaster(id=4113, builderid=41, masterid=13),

    fakedb.Buildslave(id=1, name=u'linux', info={}),
    fakedb.ConfiguredBuildslave(id=14013,
                                buildslaveid=1, buildermasterid=4013),
    fakedb.ConfiguredBuildslave(id=14014,
                                buildslaveid=1, buildermasterid=4014),
    fakedb.ConnectedBuildslave(id=113, masterid=13, buildslaveid=1),

    fakedb.Buildslave(id=2, name=u'windows', info={"a": "b"}),
    fakedb.ConfiguredBuildslave(id=24013,
                                buildslaveid=2, buildermasterid=4013),
    fakedb.ConfiguredBuildslave(id=24014,
                                buildslaveid=2, buildermasterid=4014),
    fakedb.ConfiguredBuildslave(id=24113,
                                buildslaveid=2, buildermasterid=4113),
    fakedb.ConnectedBuildslave(id=214, masterid=14, buildslaveid=2),
]


def _filt(bs, builderid, masterid):
    bs['connected_to'] = sorted(
        [d for d in bs['connected_to']
         if not masterid or masterid == d['masterid']])
    bs['configured_on'] = sorted(
        [d for d in bs['configured_on']
         if (not masterid or masterid == d['masterid'])
         and (not builderid or builderid == d['builderid'])])
    return bs


def bs1(builderid=None, masterid=None):
    return _filt({
        'buildslaveid': 1,
        'name': 'linux',
        'slaveinfo': {},
        'connected_to': [
            {'masterid': 13},
        ],
        'configured_on': sorted([
            {'builderid': 40, 'masterid': 13},
            {'builderid': 40, 'masterid': 14},
        ]),
    }, builderid, masterid)


def bs2(builderid=None, masterid=None):
    return _filt({
        'buildslaveid': 2,
        'name': 'windows',
        'slaveinfo': {'a': 'b'},
        'connected_to': [
            {'masterid': 14},
        ],
        'configured_on': sorted([
            {'builderid': 40, 'masterid': 13},
            {'builderid': 41, 'masterid': 13},
            {'builderid': 40, 'masterid': 14},
        ]),
    }, builderid, masterid)


class BuildslaveEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = buildslaves.BuildslaveEndpoint
    resourceTypeClass = buildslaves.Buildslave

    def setUp(self):
        self.setUpEndpoint()
        return self.db.insertTestData(testData)

    def tearDown(self):
        self.tearDownEndpoint()

    def test_get_existing(self):
        d = self.callGet(('buildslaves', 2))

        @d.addCallback
        def check(buildslave):
            self.validateData(buildslave)
            buildslave['configured_on'].sort()
            self.assertEqual(buildslave, bs2())
        return d

    def test_get_existing_name(self):
        d = self.callGet(('buildslaves', 'linux'))

        @d.addCallback
        def check(buildslave):
            self.validateData(buildslave)
            buildslave['configured_on'].sort()
            self.assertEqual(buildslave, bs1())
        return d

    def test_get_existing_masterid(self):
        d = self.callGet(('masters', 14, 'buildslaves', 2))

        @d.addCallback
        def check(buildslave):
            self.validateData(buildslave)
            buildslave['configured_on'].sort()
            self.assertEqual(buildslave, bs2(masterid=14))
        return d

    def test_get_existing_builderid(self):
        d = self.callGet(('builders', 40, 'buildslaves', 2))

        @d.addCallback
        def check(buildslave):
            self.validateData(buildslave)
            buildslave['configured_on'].sort()
            self.assertEqual(buildslave, bs2(builderid=40))
        return d

    def test_get_existing_masterid_builderid(self):
        d = self.callGet(('masters', 13, 'builders', 40, 'buildslaves', 2))

        @d.addCallback
        def check(buildslave):
            self.validateData(buildslave)
            buildslave['configured_on'].sort()
            self.assertEqual(buildslave, bs2(masterid=13, builderid=40))
        return d

    def test_get_missing(self):
        d = self.callGet(('buildslaves', 99))

        @d.addCallback
        def check(buildslave):
            self.assertEqual(buildslave, None)
        return d


class BuildslavesEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = buildslaves.BuildslavesEndpoint
    resourceTypeClass = buildslaves.Buildslave

    def setUp(self):
        self.setUpEndpoint()
        return self.db.insertTestData(testData)

    def tearDown(self):
        self.tearDownEndpoint()

    def test_get(self):
        d = self.callGet(('buildslaves',))

        @d.addCallback
        def check(buildslaves):
            [self.validateData(b) for b in buildslaves]
            [b['configured_on'].sort() for b in buildslaves]
            self.assertEqual(sorted(buildslaves), sorted([bs1(), bs2()]))
        return d

    def test_get_masterid(self):
        d = self.callGet(('masters', '13', 'buildslaves',))

        @d.addCallback
        def check(buildslaves):
            [self.validateData(b) for b in buildslaves]
            [b['configured_on'].sort() for b in buildslaves]
            self.assertEqual(sorted(buildslaves),
                             sorted([bs1(masterid=13), bs2(masterid=13)]))
        return d

    def test_get_builderid(self):
        d = self.callGet(('builders', '41', 'buildslaves',))

        @d.addCallback
        def check(buildslaves):
            [self.validateData(b) for b in buildslaves]
            [b['configured_on'].sort() for b in buildslaves]
            self.assertEqual(sorted(buildslaves),
                             sorted([bs2(builderid=41)]))
        return d

    def test_get_masterid_builderid(self):
        d = self.callGet(('masters', '13', 'builders', '41', 'buildslaves',))

        @d.addCallback
        def check(buildslaves):
            [self.validateData(b) for b in buildslaves]
            [b['configured_on'].sort() for b in buildslaves]
            self.assertEqual(sorted(buildslaves),
                             sorted([bs2(masterid=13, builderid=41)]))
        return d


class Buildslave(interfaces.InterfaceTests, unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self,
                                             wantMq=True, wantDb=True, wantData=True)
        self.rtype = buildslaves.Buildslave(self.master)
        return self.master.db.insertTestData([
            fakedb.Master(id=13),
            fakedb.Master(id=14),
        ])

    def test_signature_findBuildslaveId(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.findBuildslaveId,  # fake
            self.rtype.findBuildslaveId)  # real
        def findBuildslaveId(self, name):
            pass

    def test_signature_buildslaveConfigured(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.buildslaveConfigured,  # fake
            self.rtype.buildslaveConfigured)  # real
        def buildslaveConfigured(self, buildslaveid, masterid, builderids):
            pass

    def test_findBuildslaveId(self):
        # this just passes through to the db method, so test that
        rv = defer.succeed(None)
        self.master.db.buildslaves.findBuildslaveId = \
            mock.Mock(return_value=rv)
        self.assertIdentical(self.rtype.findBuildslaveId(u'foo'), rv)

    def test_findBuildslaveId_not_id(self):
        self.assertRaises(ValueError, self.rtype.findBuildslaveId, 'foo')
        self.assertRaises(ValueError, self.rtype.findBuildslaveId, u'123/foo')
