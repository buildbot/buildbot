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
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin


class Tests(TestReactorMixin, unittest.TestCase):
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

    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantDb=True)
        self.db = self.master.db

    @defer.inlineCallbacks
    def test_enable(self):
        yield self.db.insert_test_data([self.scheduler24, self.master13, self.scheduler24master])
        sch = yield self.db.schedulers.getScheduler(24)
        self.assertIsInstance(sch, schedulers.SchedulerModel)
        self.assertEqual(
            sch, schedulers.SchedulerModel(id=24, name='schname', enabled=True, masterid=13)
        )

        yield self.db.schedulers.enable(24, False)
        sch = yield self.db.schedulers.getScheduler(24)
        self.assertIsInstance(sch, schedulers.SchedulerModel)
        self.assertEqual(
            sch, schedulers.SchedulerModel(id=24, name='schname', enabled=False, masterid=13)
        )

        yield self.db.schedulers.enable(24, True)
        sch = yield self.db.schedulers.getScheduler(24)
        self.assertIsInstance(sch, schedulers.SchedulerModel)
        self.assertEqual(
            sch, schedulers.SchedulerModel(id=24, name='schname', enabled=True, masterid=13)
        )

    @defer.inlineCallbacks
    def test_classifyChanges(self):
        yield self.db.insert_test_data([self.ss92, self.change3, self.change4, self.scheduler24])
        yield self.db.schedulers.classifyChanges(24, {3: False, 4: True})
        res = yield self.db.schedulers.getChangeClassifications(24)
        self.assertEqual(res, {3: False, 4: True})

    @defer.inlineCallbacks
    def test_classifyChanges_again(self):
        # test reclassifying changes, which may happen during some timing
        # conditions.  It's important that this test uses multiple changes,
        # only one of which already exists
        yield self.db.insert_test_data([
            self.ss92,
            self.change3,
            self.change4,
            self.change5,
            self.change6,
            self.scheduler24,
            fakedb.SchedulerChange(schedulerid=24, changeid=5, important=0),
        ])
        yield self.db.schedulers.classifyChanges(24, {3: True, 4: False, 5: True, 6: False})
        res = yield self.db.schedulers.getChangeClassifications(24)
        self.assertEqual(res, {3: True, 4: False, 5: True, 6: False})

    @defer.inlineCallbacks
    def test_flushChangeClassifications(self):
        yield self.db.insert_test_data([
            self.ss92,
            self.change3,
            self.change4,
            self.change5,
            self.scheduler24,
        ])
        yield self.addClassifications(24, (3, 1), (4, 0), (5, 1))
        res = yield self.db.schedulers.getChangeClassifications(24)
        self.assertEqual(res, {3: True, 4: False, 5: True})
        yield self.db.schedulers.flushChangeClassifications(24)
        res = yield self.db.schedulers.getChangeClassifications(24)
        self.assertEqual(res, {})

    @defer.inlineCallbacks
    def test_flushChangeClassifications_less_than(self):
        yield self.db.insert_test_data([
            self.ss92,
            self.change3,
            self.change4,
            self.change5,
            self.scheduler24,
        ])
        yield self.addClassifications(24, (3, 1), (4, 0), (5, 1))
        yield self.db.schedulers.flushChangeClassifications(24, less_than=5)
        res = yield self.db.schedulers.getChangeClassifications(24)
        self.assertEqual(res, {5: True})

    @defer.inlineCallbacks
    def test_getChangeClassifications(self):
        yield self.db.insert_test_data([
            self.ss92,
            self.change3,
            self.change4,
            self.change5,
            self.change6,
            self.scheduler24,
        ])
        yield self.addClassifications(24, (3, 1), (4, 0), (5, 1), (6, 1))
        res = yield self.db.schedulers.getChangeClassifications(24)
        self.assertEqual(res, {3: True, 4: False, 5: True, 6: True})

    @defer.inlineCallbacks
    def test_getChangeClassifications_branch(self):
        yield self.db.insert_test_data([
            self.ss92,
            self.change3,
            self.change4,
            self.change5,
            self.change6,
            self.scheduler24,
        ])
        yield self.addClassifications(24, (3, 1), (4, 0), (5, 1), (6, 1))
        res = yield self.db.schedulers.getChangeClassifications(24, branch='sql')
        self.assertEqual(res, {6: True})

    @defer.inlineCallbacks
    def test_findSchedulerId_new(self):
        id = yield self.db.schedulers.findSchedulerId('schname')
        sch = yield self.db.schedulers.getScheduler(id)
        self.assertEqual(sch.name, 'schname')

    @defer.inlineCallbacks
    def test_findSchedulerId_existing(self):
        id = yield self.db.schedulers.findSchedulerId('schname')
        id2 = yield self.db.schedulers.findSchedulerId('schname')
        self.assertEqual(id, id2)

    @defer.inlineCallbacks
    def test_setSchedulerMaster_fresh(self):
        yield self.db.insert_test_data([self.scheduler24, self.master13])
        yield self.db.schedulers.setSchedulerMaster(24, 13)
        sch = yield self.db.schedulers.getScheduler(24)
        self.assertEqual(sch.masterid, 13)

    @defer.inlineCallbacks
    def test_setSchedulerMaster_inactive_but_linked(self):
        yield self.db.insert_test_data([
            self.master13,
            self.scheduler25,
            self.master14,
            self.scheduler25master,
        ])
        with self.assertRaises(schedulers.SchedulerAlreadyClaimedError):
            yield self.db.schedulers.setSchedulerMaster(25, 13)

    @defer.inlineCallbacks
    def test_setSchedulerMaster_inactive_but_linked_to_this_master(self):
        yield self.db.insert_test_data([
            self.scheduler25,
            self.master14,
            self.scheduler25master,
        ])
        yield self.db.schedulers.setSchedulerMaster(25, 14)

    @defer.inlineCallbacks
    def test_setSchedulerMaster_active(self):
        yield self.db.insert_test_data([
            self.scheduler24,
            self.master13,
            self.scheduler24master,
        ])
        with self.assertRaises(schedulers.SchedulerAlreadyClaimedError):
            yield self.db.schedulers.setSchedulerMaster(24, 14)

    @defer.inlineCallbacks
    def test_setSchedulerMaster_None(self):
        yield self.db.insert_test_data([
            self.scheduler25,
            self.master14,
            self.scheduler25master,
        ])
        yield self.db.schedulers.setSchedulerMaster(25, None)
        sch = yield self.db.schedulers.getScheduler(25)
        self.assertEqual(sch.masterid, None)

    @defer.inlineCallbacks
    def test_setSchedulerMaster_None_unowned(self):
        yield self.db.insert_test_data([self.scheduler25])
        yield self.db.schedulers.setSchedulerMaster(25, None)
        sch = yield self.db.schedulers.getScheduler(25)
        self.assertEqual(sch.masterid, None)

    @defer.inlineCallbacks
    def test_getScheduler(self):
        yield self.db.insert_test_data([self.scheduler24])
        sch = yield self.db.schedulers.getScheduler(24)
        self.assertIsInstance(sch, schedulers.SchedulerModel)
        self.assertEqual(
            sch, schedulers.SchedulerModel(id=24, name='schname', enabled=True, masterid=None)
        )

    @defer.inlineCallbacks
    def test_getScheduler_missing(self):
        sch = yield self.db.schedulers.getScheduler(24)
        self.assertEqual(sch, None)

    @defer.inlineCallbacks
    def test_getScheduler_active(self):
        yield self.db.insert_test_data([self.scheduler24, self.master13, self.scheduler24master])
        sch = yield self.db.schedulers.getScheduler(24)
        self.assertIsInstance(sch, schedulers.SchedulerModel)
        self.assertEqual(
            sch, schedulers.SchedulerModel(id=24, name='schname', enabled=True, masterid=13)
        )

    @defer.inlineCallbacks
    def test_getScheduler_inactive_but_linked(self):
        yield self.db.insert_test_data([self.scheduler25, self.master14, self.scheduler25master])
        sch = yield self.db.schedulers.getScheduler(25)
        self.assertIsInstance(sch, schedulers.SchedulerModel)
        self.assertEqual(
            sch, schedulers.SchedulerModel(id=25, name='schname2', enabled=True, masterid=14)
        )  # row exists, but marked inactive

    @defer.inlineCallbacks
    def test_getSchedulers(self):
        yield self.db.insert_test_data([
            self.scheduler24,
            self.master13,
            self.scheduler24master,
            self.scheduler25,
        ])

        def schKey(sch):
            return sch.id

        schlist = yield self.db.schedulers.getSchedulers()

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

    @defer.inlineCallbacks
    def test_getSchedulers_masterid(self):
        yield self.db.insert_test_data([
            self.scheduler24,
            self.master13,
            self.scheduler24master,
            self.scheduler25,
        ])
        schlist = yield self.db.schedulers.getSchedulers(masterid=13)

        for sch in schlist:
            self.assertIsInstance(sch, schedulers.SchedulerModel)

        self.assertEqual(
            sorted(schlist),
            sorted([
                schedulers.SchedulerModel(id=24, name='schname', enabled=True, masterid=13),
            ]),
        )

    @defer.inlineCallbacks
    def test_getSchedulers_active(self):
        yield self.db.insert_test_data([
            self.scheduler24,
            self.master13,
            self.scheduler24master,
            self.scheduler25,
        ])
        schlist = yield self.db.schedulers.getSchedulers(active=True)

        for sch in schlist:
            self.assertIsInstance(sch, schedulers.SchedulerModel)

        self.assertEqual(
            sorted(schlist),
            sorted([
                schedulers.SchedulerModel(id=24, name='schname', enabled=True, masterid=13),
            ]),
        )

    @defer.inlineCallbacks
    def test_getSchedulers_active_masterid(self):
        yield self.db.insert_test_data([
            self.scheduler24,
            self.master13,
            self.scheduler24master,
            self.scheduler25,
        ])
        schlist = yield self.db.schedulers.getSchedulers(active=True, masterid=13)

        for sch in schlist:
            self.assertIsInstance(sch, schedulers.SchedulerModel)

        self.assertEqual(
            sorted(schlist),
            sorted([
                schedulers.SchedulerModel(id=24, name='schname', enabled=True, masterid=13),
            ]),
        )

        schlist = yield self.db.schedulers.getSchedulers(active=True, masterid=14)

        for sch in schlist:
            self.assertIsInstance(sch, schedulers.SchedulerModel)

        self.assertEqual(sorted(schlist), [])

    @defer.inlineCallbacks
    def test_getSchedulers_inactive(self):
        yield self.db.insert_test_data([
            self.scheduler24,
            self.master13,
            self.scheduler24master,
            self.scheduler25,
        ])
        schlist = yield self.db.schedulers.getSchedulers(active=False)

        for sch in schlist:
            self.assertIsInstance(sch, schedulers.SchedulerModel)

        self.assertEqual(
            sorted(schlist),
            sorted([
                schedulers.SchedulerModel(id=25, name='schname2', enabled=True, masterid=None),
            ]),
        )

    @defer.inlineCallbacks
    def test_getSchedulers_inactive_masterid(self):
        yield self.db.insert_test_data([
            self.scheduler24,
            self.master13,
            self.scheduler24master,
            self.scheduler25,
        ])
        schlist = yield self.db.schedulers.getSchedulers(active=False, masterid=13)

        for sch in schlist:
            self.assertIsInstance(sch, schedulers.SchedulerModel)

        self.assertEqual(sorted(schlist), [])

        schlist = yield self.db.schedulers.getSchedulers(active=False, masterid=14)

        for sch in schlist:
            self.assertIsInstance(sch, schedulers.SchedulerModel)

        self.assertEqual(sorted(schlist), [])  # always returns [] by spec!

    @defer.inlineCallbacks
    def addClassifications(self, schedulerid, *classifications):
        def thd(conn):
            q = self.db.model.scheduler_changes.insert()
            conn.execute(
                q,
                [
                    {"changeid": c[0], "schedulerid": schedulerid, "important": c[1]}
                    for c in classifications
                ],
            )

        yield self.db.pool.do_with_transaction(thd)
