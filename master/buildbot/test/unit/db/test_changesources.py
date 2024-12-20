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

from __future__ import annotations

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.db import changesources
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin


def changeSourceKey(changeSource: changesources.ChangeSourceModel):
    return changeSource.id


class Tests(TestReactorMixin, unittest.TestCase):
    # test data

    cs42 = fakedb.ChangeSource(id=42, name='cool_source')
    cs87 = fakedb.ChangeSource(id=87, name='lame_source')

    master13 = fakedb.Master(id=13, name='m1', active=1)
    cs42master13 = fakedb.ChangeSourceMaster(changesourceid=42, masterid=13)

    master14 = fakedb.Master(id=14, name='m2', active=0)
    cs87master14 = fakedb.ChangeSourceMaster(changesourceid=87, masterid=14)

    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantDb=True)
        self.db = self.master.db

    @defer.inlineCallbacks
    def test_findChangeSourceId_new(self):
        """findChangeSourceId for a new changesource creates it"""
        id = yield self.db.changesources.findChangeSourceId('csname')
        cs = yield self.db.changesources.getChangeSource(id)
        self.assertEqual(cs.name, 'csname')

    @defer.inlineCallbacks
    def test_findChangeSourceId_existing(self):
        """findChangeSourceId gives the same answer for the same inputs"""
        id1 = yield self.db.changesources.findChangeSourceId('csname')
        id2 = yield self.db.changesources.findChangeSourceId('csname')
        self.assertEqual(id1, id2)

    @defer.inlineCallbacks
    def test_setChangeSourceMaster_fresh(self):
        """setChangeSourceMaster with a good pair"""
        yield self.db.insert_test_data([self.cs42, self.master13])
        yield self.db.changesources.setChangeSourceMaster(42, 13)
        cs = yield self.db.changesources.getChangeSource(42)
        self.assertEqual(cs.masterid, 13)

    @defer.inlineCallbacks
    def test_setChangeSourceMaster_inactive_but_linked(self):
        """Inactive changesource but already claimed by an active master"""
        yield self.db.insert_test_data([
            self.cs87,
            self.master13,
            self.master14,
            self.cs87master14,
        ])
        with self.assertRaises(changesources.ChangeSourceAlreadyClaimedError):
            yield self.db.changesources.setChangeSourceMaster(87, 13)

    @defer.inlineCallbacks
    def test_setChangeSourceMaster_active(self):
        """Active changesource already claimed by an active master"""
        yield self.db.insert_test_data([
            self.cs42,
            self.master13,
            self.cs42master13,
        ])
        with self.assertRaises(changesources.ChangeSourceAlreadyClaimedError):
            yield self.db.changesources.setChangeSourceMaster(42, 14)

    @defer.inlineCallbacks
    def test_setChangeSourceMaster_None(self):
        """A 'None' master disconnects the changesource"""
        yield self.db.insert_test_data([
            self.cs87,
            self.master14,
            self.cs87master14,
        ])
        yield self.db.changesources.setChangeSourceMaster(87, None)
        cs = yield self.db.changesources.getChangeSource(87)
        self.assertEqual(cs.masterid, None)

    @defer.inlineCallbacks
    def test_setChangeSourceMaster_None_unowned(self):
        """A 'None' master for a disconnected changesource"""
        yield self.db.insert_test_data([self.cs87])
        yield self.db.changesources.setChangeSourceMaster(87, None)
        cs = yield self.db.changesources.getChangeSource(87)
        self.assertEqual(cs.masterid, None)

    @defer.inlineCallbacks
    def test_getChangeSource(self):
        """getChangeSource for a changesource that exists"""
        yield self.db.insert_test_data([self.cs87])
        cs = yield self.db.changesources.getChangeSource(87)
        self.assertIsInstance(cs, changesources.ChangeSourceModel)
        self.assertEqual(cs, changesources.ChangeSourceModel(id=87, name='lame_source'))

    @defer.inlineCallbacks
    def test_getChangeSource_missing(self):
        """getChangeSource for a changesource that doesn't exist"""
        cs = yield self.db.changesources.getChangeSource(87)
        self.assertEqual(cs, None)

    @defer.inlineCallbacks
    def test_getChangeSource_active(self):
        """getChangeSource for a changesource that exists and is active"""
        yield self.db.insert_test_data([self.cs42, self.master13, self.cs42master13])
        cs = yield self.db.changesources.getChangeSource(42)
        self.assertIsInstance(cs, changesources.ChangeSourceModel)
        self.assertEqual(
            cs, changesources.ChangeSourceModel(id=42, name='cool_source', masterid=13)
        )

    @defer.inlineCallbacks
    def test_getChangeSource_inactive_but_linked(self):
        """getChangeSource for a changesource that is assigned but is inactive"""
        yield self.db.insert_test_data([self.cs87, self.master14, self.cs87master14])
        cs = yield self.db.changesources.getChangeSource(87)
        self.assertIsInstance(cs, changesources.ChangeSourceModel)
        self.assertEqual(
            cs, changesources.ChangeSourceModel(id=87, name='lame_source', masterid=14)
        )
        # row exists, but marked inactive

    @defer.inlineCallbacks
    def test_getChangeSources(self):
        """getChangeSources returns all changesources"""
        yield self.db.insert_test_data([
            self.cs42,
            self.master13,
            self.cs42master13,
            self.cs87,
        ])
        cslist = yield self.db.changesources.getChangeSources()

        for cs in cslist:
            self.assertIsInstance(cs, changesources.ChangeSourceModel)

        self.assertEqual(
            sorted(cslist, key=changeSourceKey),
            sorted(
                [
                    changesources.ChangeSourceModel(id=42, name='cool_source', masterid=13),
                    changesources.ChangeSourceModel(id=87, name='lame_source', masterid=None),
                ],
                key=changeSourceKey,
            ),
        )

    @defer.inlineCallbacks
    def test_getChangeSources_masterid(self):
        """getChangeSources returns all changesources for a given master"""
        yield self.db.insert_test_data([
            self.cs42,
            self.master13,
            self.cs42master13,
            self.cs87,
        ])
        cslist = yield self.db.changesources.getChangeSources(masterid=13)

        for cs in cslist:
            self.assertIsInstance(cs, changesources.ChangeSourceModel)

        self.assertEqual(
            sorted(cslist, key=changeSourceKey),
            sorted(
                [
                    changesources.ChangeSourceModel(id=42, name='cool_source', masterid=13),
                ],
                key=changeSourceKey,
            ),
        )

    @defer.inlineCallbacks
    def test_getChangeSources_active(self):
        """getChangeSources for (active changesources, all masters)"""
        yield self.db.insert_test_data([self.cs42, self.master13, self.cs42master13, self.cs87])
        cslist = yield self.db.changesources.getChangeSources(active=True)

        for cs in cslist:
            self.assertIsInstance(cs, changesources.ChangeSourceModel)

        self.assertEqual(
            sorted(cslist),
            sorted([
                changesources.ChangeSourceModel(id=42, name='cool_source', masterid=13),
            ]),
        )

    @defer.inlineCallbacks
    def test_getChangeSources_active_masterid(self):
        """getChangeSources returns (active changesources, given masters)"""
        yield self.db.insert_test_data([self.cs42, self.master13, self.cs42master13, self.cs87])
        cslist = yield self.db.changesources.getChangeSources(active=True, masterid=13)

        for cs in cslist:
            self.assertIsInstance(cs, changesources.ChangeSourceModel)

        self.assertEqual(
            sorted(cslist),
            sorted([
                changesources.ChangeSourceModel(id=42, name='cool_source', masterid=13),
            ]),
        )

        cslist = yield self.db.changesources.getChangeSources(active=True, masterid=14)

        for cs in cslist:
            self.assertIsInstance(cs, changesources.ChangeSourceModel)

        self.assertEqual(sorted(cslist), [])

    @defer.inlineCallbacks
    def test_getChangeSources_inactive(self):
        """getChangeSources returns (inactive changesources, all masters)"""
        yield self.db.insert_test_data([self.cs42, self.master13, self.cs42master13, self.cs87])
        cslist = yield self.db.changesources.getChangeSources(active=False)

        for cs in cslist:
            self.assertIsInstance(cs, changesources.ChangeSourceModel)

        self.assertEqual(
            sorted(cslist),
            sorted([
                changesources.ChangeSourceModel(id=87, name='lame_source'),
            ]),
        )

    @defer.inlineCallbacks
    def test_getChangeSources_inactive_masterid(self):
        """getChangeSources returns (active changesources, given masters)"""
        yield self.db.insert_test_data([self.cs42, self.master13, self.cs42master13, self.cs87])
        cslist = yield self.db.changesources.getChangeSources(active=False, masterid=13)

        for cs in cslist:
            self.assertIsInstance(cs, changesources.ChangeSourceModel)

        self.assertEqual(sorted(cslist), [])

        cslist = yield self.db.changesources.getChangeSources(active=False, masterid=14)

        for cs in cslist:
            self.assertIsInstance(cs, changesources.ChangeSourceModel)

        self.assertEqual(sorted(cslist), [])  # always returns [] by spec!
