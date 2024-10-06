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

from buildbot.db import schedulers
from buildbot.test import fakedb
from buildbot.test.util import connector_component
from buildbot.test.util import db
from buildbot.test.util import interfaces


class Tests(interfaces.InterfaceTests):
    # test data

    ss92 = fakedb.SourceStamp(id=92)
    change3 = fakedb.Change(changeid=3)
    change4 = fakedb.Change(changeid=4)
    change5 = fakedb.Change(changeid=5)
    change6 = fakedb.Change(changeid=6, branch='sql')

    scheduler24 = fakedb.Scheduler(id=24, name='schname')
    master13 = fakedb.Master(id=13, name='m1', active=1)
    scheduler24master = fakedb.SchedulerMaster(schedulerid=24, masterid=13)

    scheduler25 = fakedb.Scheduler(id=25, name='schname2')
    master14 = fakedb.Master(id=14, name='m2', active=0)
    scheduler25master = fakedb.SchedulerMaster(schedulerid=25, masterid=14)

    # tests

    def test_signature_enable(self):
        @self.assertArgSpecMatches(self.db.schedulers.enable)
        def enable(self, schedulerid, v):
            pass

    async def test_enable(self):
        await self.insert_test_data([self.scheduler24, self.master13, self.scheduler24master])
        sch = await self.db.schedulers.getScheduler(24)
        self.assertIsInstance(sch, schedulers.SchedulerModel)
        self.assertEqual(
            sch, schedulers.SchedulerModel(id=24, name='schname', enabled=True, masterid=13)
        )

        await self.db.schedulers.enable(24, False)
        sch = await self.db.schedulers.getScheduler(24)
        self.assertIsInstance(sch, schedulers.SchedulerModel)
        self.assertEqual(
            sch, schedulers.SchedulerModel(id=24, name='schname', enabled=False, masterid=13)
        )

        await self.db.schedulers.enable(24, True)
        sch = await self.db.schedulers.getScheduler(24)
        self.assertIsInstance(sch, schedulers.SchedulerModel)
        self.assertEqual(
            sch, schedulers.SchedulerModel(id=24, name='schname', enabled=True, masterid=13)
        )

    def test_signature_classifyChanges(self):
        @self.assertArgSpecMatches(self.db.schedulers.classifyChanges)
        def classifyChanges(self, schedulerid, classifications):
            pass

    async def test_classifyChanges(self):
        await self.insert_test_data([self.ss92, self.change3, self.change4, self.scheduler24])
        await self.db.schedulers.classifyChanges(24, {3: False, 4: True})
        res = await self.db.schedulers.getChangeClassifications(24)
        self.assertEqual(res, {3: False, 4: True})

    async def test_classifyChanges_again(self):
        # test reclassifying changes, which may happen during some timing
        # conditions.  It's important that this test uses multiple changes,
        # only one of which already exists
        await self.insert_test_data([
            self.ss92,
            self.change3,
            self.change4,
            self.change5,
            self.change6,
            self.scheduler24,
            fakedb.SchedulerChange(schedulerid=24, changeid=5, important=0),
        ])
        await self.db.schedulers.classifyChanges(24, {3: True, 4: False, 5: True, 6: False})
        res = await self.db.schedulers.getChangeClassifications(24)
        self.assertEqual(res, {3: True, 4: False, 5: True, 6: False})

    def test_signature_flushChangeClassifications(self):
        @self.assertArgSpecMatches(self.db.schedulers.flushChangeClassifications)
        def flushChangeClassifications(self, schedulerid, less_than=None):
            pass

    async def test_flushChangeClassifications(self):
        await self.insert_test_data([
            self.ss92,
            self.change3,
            self.change4,
            self.change5,
            self.scheduler24,
        ])
        await self.addClassifications(24, (3, 1), (4, 0), (5, 1))
        res = await self.db.schedulers.getChangeClassifications(24)
        self.assertEqual(res, {3: True, 4: False, 5: True})
        await self.db.schedulers.flushChangeClassifications(24)
        res = await self.db.schedulers.getChangeClassifications(24)
        self.assertEqual(res, {})

    async def test_flushChangeClassifications_less_than(self):
        await self.insert_test_data([
            self.ss92,
            self.change3,
            self.change4,
            self.change5,
            self.scheduler24,
        ])
        await self.addClassifications(24, (3, 1), (4, 0), (5, 1))
        await self.db.schedulers.flushChangeClassifications(24, less_than=5)
        res = await self.db.schedulers.getChangeClassifications(24)
        self.assertEqual(res, {5: True})

    def test_signature_getChangeClassifications(self):
        @self.assertArgSpecMatches(self.db.schedulers.getChangeClassifications)
        def getChangeClassifications(
            self, schedulerid, branch=-1, repository=-1, project=-1, codebase=-1
        ):
            pass

    async def test_getChangeClassifications(self):
        await self.insert_test_data([
            self.ss92,
            self.change3,
            self.change4,
            self.change5,
            self.change6,
            self.scheduler24,
        ])
        await self.addClassifications(24, (3, 1), (4, 0), (5, 1), (6, 1))
        res = await self.db.schedulers.getChangeClassifications(24)
        self.assertEqual(res, {3: True, 4: False, 5: True, 6: True})

    async def test_getChangeClassifications_branch(self):
        await self.insert_test_data([
            self.ss92,
            self.change3,
            self.change4,
            self.change5,
            self.change6,
            self.scheduler24,
        ])
        await self.addClassifications(24, (3, 1), (4, 0), (5, 1), (6, 1))
        res = await self.db.schedulers.getChangeClassifications(24, branch='sql')
        self.assertEqual(res, {6: True})

    def test_signature_findSchedulerId(self):
        @self.assertArgSpecMatches(self.db.schedulers.findSchedulerId)
        def findSchedulerId(self, name):
            pass

    async def test_findSchedulerId_new(self):
        id = await self.db.schedulers.findSchedulerId('schname')
        sch = await self.db.schedulers.getScheduler(id)
        self.assertEqual(sch.name, 'schname')

    async def test_findSchedulerId_existing(self):
        id = await self.db.schedulers.findSchedulerId('schname')
        id2 = await self.db.schedulers.findSchedulerId('schname')
        self.assertEqual(id, id2)

    def test_signature_setSchedulerMaster(self):
        @self.assertArgSpecMatches(self.db.schedulers.setSchedulerMaster)
        def setSchedulerMaster(self, schedulerid, masterid):
            pass

    async def test_setSchedulerMaster_fresh(self):
        await self.insert_test_data([self.scheduler24, self.master13])
        await self.db.schedulers.setSchedulerMaster(24, 13)
        sch = await self.db.schedulers.getScheduler(24)
        self.assertEqual(sch.masterid, 13)

    async def test_setSchedulerMaster_inactive_but_linked(self):
        d = self.insert_test_data([
            self.master13,
            self.scheduler25,
            self.master14,
            self.scheduler25master,
        ])
        d.addCallback(lambda _: self.db.schedulers.setSchedulerMaster(25, 13))
        await self.assertFailure(d, schedulers.SchedulerAlreadyClaimedError)

    async def test_setSchedulerMaster_inactive_but_linked_to_this_master(self):
        await self.insert_test_data([
            self.scheduler25,
            self.master14,
            self.scheduler25master,
        ])
        await self.db.schedulers.setSchedulerMaster(25, 14)

    async def test_setSchedulerMaster_active(self):
        d = self.insert_test_data([
            self.scheduler24,
            self.master13,
            self.scheduler24master,
        ])
        d.addCallback(lambda _: self.db.schedulers.setSchedulerMaster(24, 14))
        await self.assertFailure(d, schedulers.SchedulerAlreadyClaimedError)

    async def test_setSchedulerMaster_None(self):
        await self.insert_test_data([
            self.scheduler25,
            self.master14,
            self.scheduler25master,
        ])
        await self.db.schedulers.setSchedulerMaster(25, None)
        sch = await self.db.schedulers.getScheduler(25)
        self.assertEqual(sch.masterid, None)

    async def test_setSchedulerMaster_None_unowned(self):
        await self.insert_test_data([self.scheduler25])
        await self.db.schedulers.setSchedulerMaster(25, None)
        sch = await self.db.schedulers.getScheduler(25)
        self.assertEqual(sch.masterid, None)

    def test_signature_getScheduler(self):
        @self.assertArgSpecMatches(self.db.schedulers.getScheduler)
        def getScheduler(self, schedulerid):
            pass

    async def test_getScheduler(self):
        await self.insert_test_data([self.scheduler24])
        sch = await self.db.schedulers.getScheduler(24)
        self.assertIsInstance(sch, schedulers.SchedulerModel)
        self.assertEqual(
            sch, schedulers.SchedulerModel(id=24, name='schname', enabled=True, masterid=None)
        )

    async def test_getScheduler_missing(self):
        sch = await self.db.schedulers.getScheduler(24)
        self.assertEqual(sch, None)

    async def test_getScheduler_active(self):
        await self.insert_test_data([self.scheduler24, self.master13, self.scheduler24master])
        sch = await self.db.schedulers.getScheduler(24)
        self.assertIsInstance(sch, schedulers.SchedulerModel)
        self.assertEqual(
            sch, schedulers.SchedulerModel(id=24, name='schname', enabled=True, masterid=13)
        )

    async def test_getScheduler_inactive_but_linked(self):
        await self.insert_test_data([self.scheduler25, self.master14, self.scheduler25master])
        sch = await self.db.schedulers.getScheduler(25)
        self.assertIsInstance(sch, schedulers.SchedulerModel)
        self.assertEqual(
            sch, schedulers.SchedulerModel(id=25, name='schname2', enabled=True, masterid=14)
        )  # row exists, but marked inactive

    def test_signature_getSchedulers(self):
        @self.assertArgSpecMatches(self.db.schedulers.getSchedulers)
        def getSchedulers(self, active=None, masterid=None):
            pass

    async def test_getSchedulers(self):
        await self.insert_test_data([
            self.scheduler24,
            self.master13,
            self.scheduler24master,
            self.scheduler25,
        ])

        def schKey(sch):
            return sch.id

        schlist = await self.db.schedulers.getSchedulers()

        for sch in schlist:
            self.assertIsInstance(sch, schedulers.SchedulerModel)

        self.assertEqual(
            sorted(schlist, key=schKey),
            sorted(
                [
                    schedulers.SchedulerModel(id=24, name='schname', enabled=True, masterid=13),
                    schedulers.SchedulerModel(id=25, name='schname2', enabled=True, masterid=None),
                ],
                key=schKey,
            ),
        )

    async def test_getSchedulers_masterid(self):
        await self.insert_test_data([
            self.scheduler24,
            self.master13,
            self.scheduler24master,
            self.scheduler25,
        ])
        schlist = await self.db.schedulers.getSchedulers(masterid=13)

        for sch in schlist:
            self.assertIsInstance(sch, schedulers.SchedulerModel)

        self.assertEqual(
            sorted(schlist),
            sorted([
                schedulers.SchedulerModel(id=24, name='schname', enabled=True, masterid=13),
            ]),
        )

    async def test_getSchedulers_active(self):
        await self.insert_test_data([
            self.scheduler24,
            self.master13,
            self.scheduler24master,
            self.scheduler25,
        ])
        schlist = await self.db.schedulers.getSchedulers(active=True)

        for sch in schlist:
            self.assertIsInstance(sch, schedulers.SchedulerModel)

        self.assertEqual(
            sorted(schlist),
            sorted([
                schedulers.SchedulerModel(id=24, name='schname', enabled=True, masterid=13),
            ]),
        )

    async def test_getSchedulers_active_masterid(self):
        await self.insert_test_data([
            self.scheduler24,
            self.master13,
            self.scheduler24master,
            self.scheduler25,
        ])
        schlist = await self.db.schedulers.getSchedulers(active=True, masterid=13)

        for sch in schlist:
            self.assertIsInstance(sch, schedulers.SchedulerModel)

        self.assertEqual(
            sorted(schlist),
            sorted([
                schedulers.SchedulerModel(id=24, name='schname', enabled=True, masterid=13),
            ]),
        )

        schlist = await self.db.schedulers.getSchedulers(active=True, masterid=14)

        for sch in schlist:
            self.assertIsInstance(sch, schedulers.SchedulerModel)

        self.assertEqual(sorted(schlist), [])

    async def test_getSchedulers_inactive(self):
        await self.insert_test_data([
            self.scheduler24,
            self.master13,
            self.scheduler24master,
            self.scheduler25,
        ])
        schlist = await self.db.schedulers.getSchedulers(active=False)

        for sch in schlist:
            self.assertIsInstance(sch, schedulers.SchedulerModel)

        self.assertEqual(
            sorted(schlist),
            sorted([
                schedulers.SchedulerModel(id=25, name='schname2', enabled=True, masterid=None),
            ]),
        )

    async def test_getSchedulers_inactive_masterid(self):
        await self.insert_test_data([
            self.scheduler24,
            self.master13,
            self.scheduler24master,
            self.scheduler25,
        ])
        schlist = await self.db.schedulers.getSchedulers(active=False, masterid=13)

        for sch in schlist:
            self.assertIsInstance(sch, schedulers.SchedulerModel)

        self.assertEqual(sorted(schlist), [])

        schlist = await self.db.schedulers.getSchedulers(active=False, masterid=14)

        for sch in schlist:
            self.assertIsInstance(sch, schedulers.SchedulerModel)

        self.assertEqual(sorted(schlist), [])  # always returns [] by spec!


class RealTests(Tests):
    # tests that only "real" implementations will pass
    pass


class TestFakeDB(unittest.TestCase, connector_component.FakeConnectorComponentMixin, Tests):
    async def setUp(self):
        await self.setUpConnectorComponent()

    def addClassifications(self, schedulerid, *classifications):
        self.db.schedulers.fakeClassifications(schedulerid, dict(classifications))
        return defer.succeed(None)


class TestRealDB(db.TestCase, connector_component.ConnectorComponentMixin, RealTests):
    async def setUp(self):
        await self.setUpConnectorComponent(
            table_names=[
                'changes',
                'schedulers',
                'masters',
                'sourcestamps',
                'patches',
                'scheduler_masters',
                'scheduler_changes',
            ]
        )

        self.db.schedulers = schedulers.SchedulersConnectorComponent(self.db)

    def tearDown(self):
        return self.tearDownConnectorComponent()

    async def addClassifications(self, schedulerid, *classifications):
        def thd(conn):
            q = self.db.model.scheduler_changes.insert()
            conn.execute(
                q,
                [
                    {"changeid": c[0], "schedulerid": schedulerid, "important": c[1]}
                    for c in classifications
                ],
            )

        await self.db.pool.do_with_transaction(thd)
