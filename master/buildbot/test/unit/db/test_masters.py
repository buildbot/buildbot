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

from buildbot.db import masters
from buildbot.test import fakedb
from buildbot.test.util import connector_component
from buildbot.test.util import interfaces
from buildbot.util import epoch2datetime

SOMETIME = 1348971992
SOMETIME_DT = epoch2datetime(SOMETIME)
OTHERTIME = 1008971992
OTHERTIME_DT = epoch2datetime(OTHERTIME)


class Tests(interfaces.InterfaceTests):
    # common sample data

    master_row = [
        fakedb.Master(id=7, name="some:master", active=1, last_active=SOMETIME),
    ]

    # tests

    def test_signature_findMasterId(self):
        @self.assertArgSpecMatches(self.db.masters.findMasterId)
        def findMasterId(self, name):
            pass

    def test_signature_setMasterState(self):
        @self.assertArgSpecMatches(self.db.masters.setMasterState)
        def setMasterState(self, masterid, active):
            pass

    def test_signature_getMaster(self):
        @self.assertArgSpecMatches(self.db.masters.getMaster)
        def getMaster(self, masterid):
            pass

    def test_signature_getMasters(self):
        @self.assertArgSpecMatches(self.db.masters.getMasters)
        def getMasters(self):
            pass

    async def test_findMasterId_new(self):
        id = await self.db.masters.findMasterId('some:master')
        masterdict = await self.db.masters.getMaster(id)
        self.assertEqual(
            masterdict,
            masters.MasterModel(id=id, name='some:master', active=False, last_active=SOMETIME_DT),
        )

    async def test_findMasterId_new_name_differs_only_by_case(self):
        await self.insert_test_data([
            fakedb.Master(id=7, name='some:master'),
        ])
        id = await self.db.masters.findMasterId('some:Master')
        masterdict = await self.db.masters.getMaster(id)
        self.assertEqual(
            masterdict,
            masters.MasterModel(id=id, name='some:Master', active=False, last_active=SOMETIME_DT),
        )

    async def test_findMasterId_exists(self):
        await self.insert_test_data([
            fakedb.Master(id=7, name='some:master'),
        ])
        id = await self.db.masters.findMasterId('some:master')
        self.assertEqual(id, 7)

    async def test_setMasterState_when_missing(self):
        activated = await self.db.masters.setMasterState(masterid=7, active=True)
        self.assertFalse(activated)

    async def test_setMasterState_true_when_active(self):
        await self.insert_test_data([
            fakedb.Master(id=7, name='some:master', active=1, last_active=OTHERTIME),
        ])
        activated = await self.db.masters.setMasterState(masterid=7, active=True)
        self.assertFalse(activated)  # it was already active
        masterdict = await self.db.masters.getMaster(7)
        self.assertEqual(
            masterdict,
            masters.MasterModel(id=7, name='some:master', active=True, last_active=SOMETIME_DT),
        )  # timestamp updated

    async def test_setMasterState_true_when_inactive(self):
        await self.insert_test_data([
            fakedb.Master(id=7, name='some:master', active=0, last_active=OTHERTIME),
        ])
        activated = await self.db.masters.setMasterState(masterid=7, active=True)
        self.assertTrue(activated)
        masterdict = await self.db.masters.getMaster(7)
        self.assertEqual(
            masterdict,
            masters.MasterModel(id=7, name='some:master', active=True, last_active=SOMETIME_DT),
        )

    async def test_setMasterState_false_when_active(self):
        await self.insert_test_data([
            fakedb.Master(id=7, name='some:master', active=1, last_active=OTHERTIME),
        ])
        deactivated = await self.db.masters.setMasterState(masterid=7, active=False)
        self.assertTrue(deactivated)
        masterdict = await self.db.masters.getMaster(7)
        self.assertEqual(
            masterdict,
            masters.MasterModel(id=7, name='some:master', active=False, last_active=OTHERTIME_DT),
        )

    async def test_setMasterState_false_when_inactive(self):
        await self.insert_test_data([
            fakedb.Master(id=7, name='some:master', active=0, last_active=OTHERTIME),
        ])
        deactivated = await self.db.masters.setMasterState(masterid=7, active=False)
        self.assertFalse(deactivated)
        masterdict = await self.db.masters.getMaster(7)
        self.assertEqual(
            masterdict,
            masters.MasterModel(id=7, name='some:master', active=False, last_active=OTHERTIME_DT),
        )

    async def test_getMaster(self):
        await self.insert_test_data([
            fakedb.Master(id=7, name='some:master', active=0, last_active=SOMETIME),
        ])
        masterdict = await self.db.masters.getMaster(7)
        self.assertIsInstance(masterdict, masters.MasterModel)
        self.assertEqual(
            masterdict,
            masters.MasterModel(id=7, name='some:master', active=False, last_active=SOMETIME_DT),
        )

    async def test_getMaster_missing(self):
        masterdict = await self.db.masters.getMaster(7)
        self.assertEqual(masterdict, None)

    async def test_getMasters(self):
        await self.insert_test_data([
            fakedb.Master(id=7, name='some:master', active=0, last_active=SOMETIME),
            fakedb.Master(id=8, name='other:master', active=1, last_active=OTHERTIME),
        ])
        masterlist = await self.db.masters.getMasters()
        for masterdict in masterlist:
            self.assertIsInstance(masterdict, masters.MasterModel)

        def masterKey(master):
            return master.id

        expected = sorted(
            [
                masters.MasterModel(id=7, name='some:master', active=0, last_active=SOMETIME_DT),
                masters.MasterModel(id=8, name='other:master', active=1, last_active=OTHERTIME_DT),
            ],
            key=masterKey,
        )
        self.assertEqual(sorted(masterlist, key=masterKey), expected)


class RealTests(Tests):
    # tests that only "real" implementations will pass

    async def test_setMasterState_false_deletes_links(self):
        await self.insert_test_data([
            fakedb.Master(id=7, name='some:master', active=1, last_active=OTHERTIME),
            fakedb.Scheduler(id=21),
            fakedb.SchedulerMaster(schedulerid=21, masterid=7),
        ])
        deactivated = await self.db.masters.setMasterState(masterid=7, active=False)
        self.assertTrue(deactivated)

        # check that the scheduler_masters row was deleted
        def thd(conn):
            tbl = self.db.model.scheduler_masters
            self.assertEqual(conn.execute(tbl.select()).fetchall(), [])

        await self.db.pool.do(thd)


class TestFakeDB(unittest.TestCase, connector_component.FakeConnectorComponentMixin, Tests):
    async def setUp(self):
        await self.setUpConnectorComponent()
        self.reactor.advance(SOMETIME)


class TestRealDB(unittest.TestCase, connector_component.ConnectorComponentMixin, RealTests):
    async def setUp(self):
        await self.setUpConnectorComponent(
            table_names=['masters', 'schedulers', 'scheduler_masters']
        )

        self.reactor.advance(SOMETIME)

        self.db.masters = masters.MastersConnectorComponent(self.db)

    def tearDown(self):
        return self.tearDownConnectorComponent()
