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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.db import changesources
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import connector_component
from buildbot.test.util import db
from buildbot.test.util import interfaces
from buildbot.test.util import validation


def changeSourceKey(changeSource):
    return changeSource['id']


class Tests(interfaces.InterfaceTests):

    # test data

    cs42 = fakedb.ChangeSource(id=42, name='cool_source')
    cs87 = fakedb.ChangeSource(id=87, name='lame_source')

    master13 = fakedb.Master(id=13, name='m1', active=1)
    cs42master13 = fakedb.ChangeSourceMaster(changesourceid=42, masterid=13)

    master14 = fakedb.Master(id=14, name='m2', active=0)
    cs87master14 = fakedb.ChangeSourceMaster(changesourceid=87, masterid=14)

    # tests

    def test_signature_findChangeSourceId(self):
        """The signature of findChangeSourceId is correct"""
        @self.assertArgSpecMatches(self.db.changesources.findChangeSourceId)
        def findChangeSourceId(self, name):
            pass

    @defer.inlineCallbacks
    def test_findChangeSourceId_new(self):
        """findChangeSourceId for a new changesource creates it"""
        id = yield self.db.changesources.findChangeSourceId('csname')
        cs = yield self.db.changesources.getChangeSource(id)
        self.assertEqual(cs['name'], 'csname')

    @defer.inlineCallbacks
    def test_findChangeSourceId_existing(self):
        """findChangeSourceId gives the same answer for the same inputs"""
        id1 = yield self.db.changesources.findChangeSourceId('csname')
        id2 = yield self.db.changesources.findChangeSourceId('csname')
        self.assertEqual(id1, id2)

    def test_signature_setChangeSourceMaster(self):
        """setChangeSourceMaster has the right signature"""
        @self.assertArgSpecMatches(self.db.changesources.setChangeSourceMaster)
        def setChangeSourceMaster(self, changesourceid, masterid):
            pass

    @defer.inlineCallbacks
    def test_setChangeSourceMaster_fresh(self):
        """setChangeSourceMaster with a good pair"""
        yield self.insertTestData([self.cs42, self.master13])
        yield self.db.changesources.setChangeSourceMaster(42, 13)
        cs = yield self.db.changesources.getChangeSource(42)
        self.assertEqual(cs['masterid'], 13)

    def test_setChangeSourceMaster_inactive_but_linked(self):
        """Inactive changesource but already claimed by an active master"""
        d = self.insertTestData([
            self.cs87,
            self.master13, self.master14,
            self.cs87master14,
        ])
        d.addCallback(lambda _:
                      self.db.changesources.setChangeSourceMaster(87, 13))
        self.assertFailure(d, changesources.ChangeSourceAlreadyClaimedError)
        return d

    def test_setChangeSourceMaster_active(self):
        """Active changesource already claimed by an active master"""
        d = self.insertTestData([
            self.cs42, self.master13, self.cs42master13,
        ])
        d.addCallback(lambda _:
                      self.db.changesources.setChangeSourceMaster(42, 14))
        self.assertFailure(d, changesources.ChangeSourceAlreadyClaimedError)
        return d

    @defer.inlineCallbacks
    def test_setChangeSourceMaster_None(self):
        """A 'None' master disconnects the changesource"""
        yield self.insertTestData([
            self.cs87, self.master14, self.cs87master14,
        ])
        yield self.db.changesources.setChangeSourceMaster(87, None)
        cs = yield self.db.changesources.getChangeSource(87)
        self.assertEqual(cs['masterid'], None)

    @defer.inlineCallbacks
    def test_setChangeSourceMaster_None_unowned(self):
        """A 'None' master for a disconnected changesource"""
        yield self.insertTestData([self.cs87])
        yield self.db.changesources.setChangeSourceMaster(87, None)
        cs = yield self.db.changesources.getChangeSource(87)
        self.assertEqual(cs['masterid'], None)

    def test_signature_getChangeSource(self):
        """getChangeSource has the right signature"""
        @self.assertArgSpecMatches(self.db.changesources.getChangeSource)
        def getChangeSource(self, changesourceid):
            pass

    @defer.inlineCallbacks
    def test_getChangeSource(self):
        """getChangeSource for a changesource that exists"""
        yield self.insertTestData([self.cs87])
        cs = yield self.db.changesources.getChangeSource(87)
        validation.verifyDbDict(self, 'changesourcedict', cs)
        self.assertEqual(cs, dict(
            id=87,
            name='lame_source',
            masterid=None))

    @defer.inlineCallbacks
    def test_getChangeSource_missing(self):
        """getChangeSource for a changesource that doesn't exist"""
        cs = yield self.db.changesources.getChangeSource(87)
        self.assertEqual(cs, None)

    @defer.inlineCallbacks
    def test_getChangeSource_active(self):
        """getChangeSource for a changesource that exists and is active"""
        yield self.insertTestData([self.cs42, self.master13,
                                   self.cs42master13])
        cs = yield self.db.changesources.getChangeSource(42)
        validation.verifyDbDict(self, 'changesourcedict', cs)
        self.assertEqual(cs, dict(
            id=42,
            name='cool_source',
            masterid=13))

    @defer.inlineCallbacks
    def test_getChangeSource_inactive_but_linked(self):
        """getChangeSource for a changesource that is assigned but is inactive"""
        yield self.insertTestData([self.cs87, self.master14,
                                   self.cs87master14])
        cs = yield self.db.changesources.getChangeSource(87)
        validation.verifyDbDict(self, 'changesourcedict', cs)
        self.assertEqual(cs, dict(
            id=87,
            name='lame_source',
            masterid=14))  # row exists, but marked inactive

    def test_signature_getChangeSources(self):
        """getChangeSources has right signature"""
        @self.assertArgSpecMatches(self.db.changesources.getChangeSources)
        def getChangeSources(self, active=None, masterid=None):
            pass

    @defer.inlineCallbacks
    def test_getChangeSources(self):
        """getChangeSources returns all changesources"""
        yield self.insertTestData([
            self.cs42, self.master13, self.cs42master13,
            self.cs87,
        ])
        cslist = yield self.db.changesources.getChangeSources()
        [validation.verifyDbDict(self, 'changesourcedict', cs)
         for cs in cslist]
        self.assertEqual(sorted(cslist, key=changeSourceKey), sorted([
            dict(id=42, name='cool_source', masterid=13),
            dict(id=87, name='lame_source', masterid=None),
        ], key=changeSourceKey))

    @defer.inlineCallbacks
    def test_getChangeSources_masterid(self):
        """getChangeSources returns all changesources for a given master"""
        yield self.insertTestData([
            self.cs42, self.master13, self.cs42master13,
            self.cs87,
        ])
        cslist = yield self.db.changesources.getChangeSources(masterid=13)
        [validation.verifyDbDict(self, 'changesourcedict', cs)
         for cs in cslist]
        self.assertEqual(sorted(cslist, key=changeSourceKey), sorted([
            dict(id=42, name='cool_source', masterid=13),
        ], key=changeSourceKey))

    @defer.inlineCallbacks
    def test_getChangeSources_active(self):
        """getChangeSources for (active changesources, all masters)"""
        yield self.insertTestData([
            self.cs42, self.master13, self.cs42master13,
            self.cs87
        ])
        cslist = yield self.db.changesources.getChangeSources(active=True)
        [validation.verifyDbDict(self, 'changesourcedict', cs)
         for cs in cslist]
        self.assertEqual(sorted(cslist), sorted([
            dict(id=42, name='cool_source', masterid=13),
        ]))

    @defer.inlineCallbacks
    def test_getChangeSources_active_masterid(self):
        """getChangeSources returns (active changesources, given masters)"""
        yield self.insertTestData([
            self.cs42, self.master13, self.cs42master13,
            self.cs87
        ])
        cslist = yield self.db.changesources.getChangeSources(
            active=True, masterid=13)
        [validation.verifyDbDict(self, 'changesourcedict', cs)
         for cs in cslist]
        self.assertEqual(sorted(cslist), sorted([
            dict(id=42, name='cool_source', masterid=13),
        ]))

        cslist = yield self.db.changesources.getChangeSources(
            active=True, masterid=14)
        [validation.verifyDbDict(self, 'changesourcedict', cs)
         for cs in cslist]
        self.assertEqual(sorted(cslist), [])

    @defer.inlineCallbacks
    def test_getChangeSources_inactive(self):
        """getChangeSources returns (inactive changesources, all masters)"""
        yield self.insertTestData([
            self.cs42, self.master13, self.cs42master13,
            self.cs87
        ])
        cslist = yield self.db.changesources.getChangeSources(active=False)
        [validation.verifyDbDict(self, 'changesourcedict', cs)
         for cs in cslist]
        self.assertEqual(sorted(cslist), sorted([
            dict(id=87, name='lame_source', masterid=None),
        ]))

    @defer.inlineCallbacks
    def test_getChangeSources_inactive_masterid(self):
        """getChangeSources returns (active changesources, given masters)"""
        yield self.insertTestData([
            self.cs42, self.master13, self.cs42master13,
            self.cs87
        ])
        cslist = yield self.db.changesources.getChangeSources(
            active=False, masterid=13)
        [validation.verifyDbDict(self, 'changesourcedict', cs)
         for cs in cslist]
        self.assertEqual(sorted(cslist), [])

        cslist = yield self.db.changesources.getChangeSources(
            active=False, masterid=14)
        [validation.verifyDbDict(self, 'changesourcedict', cs)
         for cs in cslist]
        self.assertEqual(sorted(cslist), [])   # always returns [] by spec!


class RealTests(Tests):

    # tests that only "real" implementations will pass
    pass


class TestFakeDB(unittest.TestCase, Tests):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self, wantDb=True)
        self.db = self.master.db
        self.db.checkForeignKeys = True
        self.insertTestData = self.db.insertTestData


class TestRealDB(db.TestCase,
                 connector_component.ConnectorComponentMixin,
                 RealTests):

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['changes', 'changesources', 'masters',
                         'patches', 'sourcestamps', 'changesource_masters'])

        def finish_setup(_):
            self.db.changesources = \
                changesources.ChangeSourcesConnectorComponent(self.db)
        d.addCallback(finish_setup)

        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()
