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

from buildbot.db import masters
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.util import epoch2datetime

SOMETIME = 1348971992
SOMETIME_DT = epoch2datetime(SOMETIME)
OTHERTIME = 1008971992
OTHERTIME_DT = epoch2datetime(OTHERTIME)


class Tests(TestReactorMixin, unittest.TestCase):
    # common sample data

    master_row = [
        fakedb.Master(id=7, active=1, last_active=SOMETIME),
    ]

    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.reactor.advance(SOMETIME)
        self.master = yield fakemaster.make_master(self, wantDb=True)
        self.db = self.master.db

    @defer.inlineCallbacks
    def test_findMasterId_new(self):
        id = yield self.db.masters.findMasterId('master-7')
        masterdict = yield self.db.masters.getMaster(id)
        self.assertEqual(
            masterdict,
            masters.MasterModel(id=id, name='master-7', active=False, last_active=SOMETIME_DT),
        )

    @defer.inlineCallbacks
    def test_findMasterId_new_name_differs_only_by_case(self):
        yield self.db.insert_test_data([
            fakedb.Master(id=7, name='some:master'),
        ])
        id = yield self.db.masters.findMasterId('some:Master')
        masterdict = yield self.db.masters.getMaster(id)
        self.assertEqual(
            masterdict,
            masters.MasterModel(id=id, name='some:Master', active=False, last_active=SOMETIME_DT),
        )

    @defer.inlineCallbacks
    def test_findMasterId_exists(self):
        yield self.db.insert_test_data([
            fakedb.Master(id=7, name='some:master'),
        ])
        id = yield self.db.masters.findMasterId('some:master')
        self.assertEqual(id, 7)

    @defer.inlineCallbacks
    def test_setMasterState_when_missing(self):
        activated = yield self.db.masters.setMasterState(masterid=7, active=True)
        self.assertFalse(activated)

    @defer.inlineCallbacks
    def test_setMasterState_true_when_active(self):
        yield self.db.insert_test_data([
            fakedb.Master(id=7, active=1, last_active=OTHERTIME),
        ])
        activated = yield self.db.masters.setMasterState(masterid=7, active=True)
        self.assertFalse(activated)  # it was already active
        masterdict = yield self.db.masters.getMaster(7)
        self.assertEqual(
            masterdict,
            masters.MasterModel(id=7, name='master-7', active=True, last_active=SOMETIME_DT),
        )  # timestamp updated

    @defer.inlineCallbacks
    def test_setMasterState_true_when_inactive(self):
        yield self.db.insert_test_data([
            fakedb.Master(id=7, active=0, last_active=OTHERTIME),
        ])
        activated = yield self.db.masters.setMasterState(masterid=7, active=True)
        self.assertTrue(activated)
        masterdict = yield self.db.masters.getMaster(7)
        self.assertEqual(
            masterdict,
            masters.MasterModel(id=7, name='master-7', active=True, last_active=SOMETIME_DT),
        )

    @defer.inlineCallbacks
    def test_setMasterState_false_when_active(self):
        yield self.db.insert_test_data([
            fakedb.Master(id=7, active=1, last_active=OTHERTIME),
        ])
        deactivated = yield self.db.masters.setMasterState(masterid=7, active=False)
        self.assertTrue(deactivated)
        masterdict = yield self.db.masters.getMaster(7)
        self.assertEqual(
            masterdict,
            masters.MasterModel(id=7, name='master-7', active=False, last_active=OTHERTIME_DT),
        )

    @defer.inlineCallbacks
    def test_setMasterState_false_when_inactive(self):
        yield self.db.insert_test_data([
            fakedb.Master(id=7, active=0, last_active=OTHERTIME),
        ])
        deactivated = yield self.db.masters.setMasterState(masterid=7, active=False)
        self.assertFalse(deactivated)
        masterdict = yield self.db.masters.getMaster(7)
        self.assertEqual(
            masterdict,
            masters.MasterModel(id=7, name='master-7', active=False, last_active=OTHERTIME_DT),
        )

    @defer.inlineCallbacks
    def test_getMaster(self):
        yield self.db.insert_test_data([
            fakedb.Master(id=7, active=0, last_active=SOMETIME),
        ])
        masterdict = yield self.db.masters.getMaster(7)
        self.assertIsInstance(masterdict, masters.MasterModel)
        self.assertEqual(
            masterdict,
            masters.MasterModel(id=7, name='master-7', active=False, last_active=SOMETIME_DT),
        )

    @defer.inlineCallbacks
    def test_getMaster_missing(self):
        masterdict = yield self.db.masters.getMaster(7)
        self.assertEqual(masterdict, None)

    @defer.inlineCallbacks
    def test_getMasters(self):
        yield self.db.insert_test_data([
            fakedb.Master(id=7, active=0, last_active=SOMETIME),
            fakedb.Master(id=8, active=1, last_active=OTHERTIME),
        ])
        masterlist = yield self.db.masters.getMasters()
        for masterdict in masterlist:
            self.assertIsInstance(masterdict, masters.MasterModel)

        def masterKey(master):
            return master.id

        expected = sorted(
            [
                masters.MasterModel(id=7, name='master-7', active=0, last_active=SOMETIME_DT),
                masters.MasterModel(id=8, name='master-8', active=1, last_active=OTHERTIME_DT),
            ],
            key=masterKey,
        )
        self.assertEqual(sorted(masterlist, key=masterKey), expected)

    @defer.inlineCallbacks
    def test_setMasterState_false_deletes_links(self):
        yield self.db.insert_test_data([
            fakedb.Master(id=7, name='some:master', active=1, last_active=OTHERTIME),
            fakedb.Scheduler(id=21),
            fakedb.SchedulerMaster(schedulerid=21, masterid=7),
        ])
        deactivated = yield self.db.masters.setMasterState(masterid=7, active=False)
        self.assertTrue(deactivated)

        # check that the scheduler_masters row was deleted
        def thd(conn):
            tbl = self.db.model.scheduler_masters
            self.assertEqual(conn.execute(tbl.select()).fetchall(), [])

        yield self.db.pool.do(thd)
