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

from twisted.internet import defer
from twisted.python import failure
from twisted.trial import unittest

from buildbot.data import changesources
from buildbot.db.changesources import ChangeSourceAlreadyClaimedError
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import endpoint
from buildbot.test.util import interfaces
from buildbot.test.util.misc import TestReactorMixin


class ChangeSourceEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = changesources.ChangeSourceEndpoint
    resourceTypeClass = changesources.ChangeSource

    def setUp(self):
        self.setUpEndpoint()

        self.db.insertTestData([
            fakedb.Master(id=22, active=0),
            fakedb.Master(id=33, active=1),
            fakedb.ChangeSource(id=13, name='some:changesource'),
            fakedb.ChangeSourceMaster(changesourceid=13, masterid=None),
            fakedb.ChangeSource(id=14, name='other:changesource'),
            fakedb.ChangeSourceMaster(changesourceid=14, masterid=22),
            fakedb.ChangeSource(id=15, name='another:changesource'),
            fakedb.ChangeSourceMaster(changesourceid=15, masterid=33),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    @defer.inlineCallbacks
    def test_get_existing(self):
        """get an existing changesource by id"""
        changesource = yield self.callGet(('changesources', 14))

        self.validateData(changesource)
        self.assertEqual(changesource['name'], 'other:changesource')

    @defer.inlineCallbacks
    def test_get_no_master(self):
        """get a changesource with no master"""
        changesource = yield self.callGet(('changesources', 13))

        self.validateData(changesource)
        self.assertEqual(changesource['master'], None),

    @defer.inlineCallbacks
    def test_get_masterid_existing(self):
        """get an existing changesource by id on certain master"""
        changesource = yield self.callGet(('masters', 22, 'changesources', 14))

        self.validateData(changesource)
        self.assertEqual(changesource['name'], 'other:changesource')

    @defer.inlineCallbacks
    def test_get_masterid_no_match(self):
        """get an existing changesource by id on the wrong master"""
        changesource = yield self.callGet(('masters', 33, 'changesources', 13))

        self.assertEqual(changesource, None)

    @defer.inlineCallbacks
    def test_get_masterid_missing(self):
        """get an existing changesource by id on an invalid master"""
        changesource = yield self.callGet(('masters', 25, 'changesources', 13))

        self.assertEqual(changesource, None)

    @defer.inlineCallbacks
    def test_get_missing(self):
        """get an invalid changesource by id"""
        changesource = yield self.callGet(('changesources', 99))

        self.assertEqual(changesource, None)


class ChangeSourcesEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = changesources.ChangeSourcesEndpoint
    resourceTypeClass = changesources.ChangeSource

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.Master(id=22, active=0),
            fakedb.Master(id=33, active=1),
            fakedb.ChangeSource(id=13, name='some:changesource'),
            fakedb.ChangeSourceMaster(changesourceid=13, masterid=None),
            fakedb.ChangeSource(id=14, name='other:changesource'),
            fakedb.ChangeSourceMaster(changesourceid=14, masterid=22),
            fakedb.ChangeSource(id=15, name='another:changesource'),
            fakedb.ChangeSourceMaster(changesourceid=15, masterid=33),
            fakedb.ChangeSource(id=16, name='wholenother:changesource'),
            fakedb.ChangeSourceMaster(changesourceid=16, masterid=33),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    @defer.inlineCallbacks
    def test_get(self):
        changesources = yield self.callGet(('changesources',))

        [self.validateData(cs) for cs in changesources]
        self.assertEqual(sorted([m['changesourceid'] for m in changesources]),
                         [13, 14, 15, 16])

    @defer.inlineCallbacks
    def test_get_masterid(self):
        changesources = yield self.callGet(('masters', 33, 'changesources'))

        [self.validateData(cs) for cs in changesources]
        self.assertEqual(sorted([m['changesourceid'] for m in changesources]),
                         [15, 16])

    @defer.inlineCallbacks
    def test_get_masterid_missing(self):
        changesources = yield self.callGet(('masters', 23, 'changesources'))

        self.assertEqual(changesources, [])


class ChangeSource(TestReactorMixin, interfaces.InterfaceTests,
                   unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        self.master = fakemaster.make_master(self, wantMq=True, wantDb=True,
                                             wantData=True)
        self.rtype = changesources.ChangeSource(self.master)

    def test_signature_findChangeSourceId(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.findChangeSourceId,  # fake
            self.rtype.findChangeSourceId)  # real
        def findChangeSourceId(self, name):
            pass

    @defer.inlineCallbacks
    def test_findChangeSourceId(self):
        self.master.db.changesources.findChangeSourceId = mock.Mock(
            return_value=defer.succeed(10))
        self.assertEqual((yield self.rtype.findChangeSourceId('cs')), 10)
        self.master.db.changesources.findChangeSourceId.assert_called_with(
            'cs')

    def test_signature_trySetChangeSourceMaster(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.trySetChangeSourceMaster,  # fake
            self.rtype.trySetChangeSourceMaster)  # real
        def trySetChangeSourceMaster(self, changesourceid, masterid):
            pass

    @defer.inlineCallbacks
    def test_trySetChangeSourceMaster_succeeds(self):
        self.master.db.changesources.setChangeSourceMaster = mock.Mock(
            return_value=defer.succeed(None))
        yield self.rtype.trySetChangeSourceMaster(10, 20)
        self.master.db.changesources.setChangeSourceMaster.assert_called_with(
            10, 20)

    @defer.inlineCallbacks
    def test_trySetChangeSourceMaster_fails(self):
        d = defer.fail(failure.Failure(
            ChangeSourceAlreadyClaimedError('oh noes')))

        self.master.db.changesources.setChangeSourceMaster = mock.Mock(
            return_value=d)
        result = yield self.rtype.trySetChangeSourceMaster(10, 20)

        self.assertFalse(result)

    @defer.inlineCallbacks
    def test_trySetChangeSourceMaster_raisesOddException(self):
        d = defer.fail(failure.Failure(RuntimeError('oh noes')))

        self.master.db.changesources.setChangeSourceMaster = mock.Mock(
            return_value=d)

        try:
            yield self.rtype.trySetChangeSourceMaster(10, 20)
        except RuntimeError:
            pass
        else:
            self.fail("The RuntimeError did not propagate")

    @defer.inlineCallbacks
    def test__masterDeactivated(self):
        yield self.master.db.insertTestData([
            fakedb.Master(id=22, active=0),
            fakedb.ChangeSource(id=13, name='some:changesource'),
            fakedb.ChangeSourceMaster(changesourceid=13, masterid=22),
            fakedb.ChangeSource(id=14, name='other:changesource'),
            fakedb.ChangeSourceMaster(changesourceid=14, masterid=22),
        ])
        yield self.rtype._masterDeactivated(22)
        self.master.db.changesources.assertChangeSourceMaster(13, None)
        self.master.db.changesources.assertChangeSourceMaster(14, None)
