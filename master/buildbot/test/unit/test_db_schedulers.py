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

from buildbot.db import schedulers
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import connector_component
from buildbot.test.util import db
from buildbot.test.util import interfaces
from buildbot.test.util import validation


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

    @defer.inlineCallbacks
    def test_enable(self):
        yield self.insertTestData([self.scheduler24, self.master13,
                                   self.scheduler24master])
        sch = yield self.db.schedulers.getScheduler(24)
        validation.verifyDbDict(self, 'schedulerdict', sch)
        self.assertEqual(sch, dict(
            id=24,
            name='schname',
            enabled=True,
            masterid=13))

        yield self.db.schedulers.enable(24, False)
        sch = yield self.db.schedulers.getScheduler(24)
        validation.verifyDbDict(self, 'schedulerdict', sch)
        self.assertEqual(sch, dict(
            id=24,
            name='schname',
            enabled=False,
            masterid=13))

        yield self.db.schedulers.enable(24, True)
        sch = yield self.db.schedulers.getScheduler(24)
        validation.verifyDbDict(self, 'schedulerdict', sch)
        self.assertEqual(sch, dict(
            id=24,
            name='schname',
            enabled=True,
            masterid=13))

    def test_signature_classifyChanges(self):
        @self.assertArgSpecMatches(self.db.schedulers.classifyChanges)
        def classifyChanges(self, schedulerid, classifications):
            pass

    @defer.inlineCallbacks
    def test_classifyChanges(self):
        yield self.insertTestData([self.ss92, self.change3, self.change4,
                                   self.scheduler24])
        yield self.db.schedulers.classifyChanges(24,
                                                 {3: False, 4: True})
        res = yield self.db.schedulers.getChangeClassifications(24)
        self.assertEqual(res, {3: False, 4: True})

    @defer.inlineCallbacks
    def test_classifyChanges_again(self):
        # test reclassifying changes, which may happen during some timing
        # conditions.  It's important that this test uses multiple changes,
        # only one of which already exists
        yield self.insertTestData([
            self.ss92,
            self.change3,
            self.change4,
            self.change5,
            self.change6,
            self.scheduler24,
            fakedb.SchedulerChange(schedulerid=24, changeid=5, important=0),
        ])
        yield self.db.schedulers.classifyChanges(
            24, {3: True, 4: False, 5: True, 6: False})
        res = yield self.db.schedulers.getChangeClassifications(24)
        self.assertEqual(res, {3: True, 4: False, 5: True, 6: False})

    def test_signature_flushChangeClassifications(self):
        @self.assertArgSpecMatches(
            self.db.schedulers.flushChangeClassifications)
        def flushChangeClassifications(self, schedulerid, less_than=None):
            pass

    @defer.inlineCallbacks
    def test_flushChangeClassifications(self):
        yield self.insertTestData([self.ss92, self.change3, self.change4,
                                   self.change5, self.scheduler24])
        yield self.addClassifications(24,
                                      (3, 1), (4, 0), (5, 1))
        res = yield self.db.schedulers.getChangeClassifications(24)
        self.assertEqual(res, {3: True, 4: False, 5: True})
        yield self.db.schedulers.flushChangeClassifications(24)
        res = yield self.db.schedulers.getChangeClassifications(24)
        self.assertEqual(res, {})

    @defer.inlineCallbacks
    def test_flushChangeClassifications_less_than(self):
        yield self.insertTestData([self.ss92, self.change3,
                                   self.change4, self.change5, self.scheduler24])
        yield self.addClassifications(24,
                                      (3, 1), (4, 0), (5, 1))
        yield self.db.schedulers.flushChangeClassifications(24, less_than=5)
        res = yield self.db.schedulers.getChangeClassifications(24)
        self.assertEqual(res, {5: True})

    def test_signature_getChangeClassifications(self):
        @self.assertArgSpecMatches(self.db.schedulers.getChangeClassifications)
        def getChangeClassifications(self, schedulerid, branch=-1,
                                     repository=-1, project=-1, codebase=-1):
            pass

    @defer.inlineCallbacks
    def test_getChangeClassifications(self):
        yield self.insertTestData([self.ss92, self.change3, self.change4,
                                   self.change5, self.change6, self.scheduler24])
        yield self.addClassifications(24,
                                      (3, 1), (4, 0), (5, 1), (6, 1))
        res = yield self.db.schedulers.getChangeClassifications(24)
        self.assertEqual(res, {3: True, 4: False, 5: True, 6: True})

    @defer.inlineCallbacks
    def test_getChangeClassifications_branch(self):
        yield self.insertTestData([self.ss92, self.change3, self.change4,
                                   self.change5, self.change6, self.scheduler24])
        yield self.addClassifications(24,
                                      (3, 1), (4, 0), (5, 1), (6, 1))
        res = yield self.db.schedulers.getChangeClassifications(24,
                                                                branch='sql')
        self.assertEqual(res, {6: True})

    def test_signature_findSchedulerId(self):
        @self.assertArgSpecMatches(self.db.schedulers.findSchedulerId)
        def findSchedulerId(self, name):
            pass

    @defer.inlineCallbacks
    def test_findSchedulerId_new(self):
        id = yield self.db.schedulers.findSchedulerId('schname')
        sch = yield self.db.schedulers.getScheduler(id)
        self.assertEqual(sch['name'], 'schname')

    @defer.inlineCallbacks
    def test_findSchedulerId_existing(self):
        id = yield self.db.schedulers.findSchedulerId('schname')
        id2 = yield self.db.schedulers.findSchedulerId('schname')
        self.assertEqual(id, id2)

    def test_signature_setSchedulerMaster(self):
        @self.assertArgSpecMatches(self.db.schedulers.setSchedulerMaster)
        def setSchedulerMaster(self, schedulerid, masterid):
            pass

    @defer.inlineCallbacks
    def test_setSchedulerMaster_fresh(self):
        yield self.insertTestData([self.scheduler24, self.master13])
        yield self.db.schedulers.setSchedulerMaster(24, 13)
        sch = yield self.db.schedulers.getScheduler(24)
        self.assertEqual(sch['masterid'], 13)

    def test_setSchedulerMaster_inactive_but_linked(self):
        d = self.insertTestData([
            self.master13,
            self.scheduler25, self.master14, self.scheduler25master,
        ])
        d.addCallback(lambda _:
                      self.db.schedulers.setSchedulerMaster(25, 13))
        self.assertFailure(d, schedulers.SchedulerAlreadyClaimedError)
        return d

    def test_setSchedulerMaster_inactive_but_linked_to_this_master(self):
        d = self.insertTestData([
            self.scheduler25, self.master14, self.scheduler25master,
        ])
        d.addCallback(lambda _:
                      self.db.schedulers.setSchedulerMaster(25, 14))
        return d

    def test_setSchedulerMaster_active(self):
        d = self.insertTestData([
            self.scheduler24, self.master13, self.scheduler24master,
        ])
        d.addCallback(lambda _:
                      self.db.schedulers.setSchedulerMaster(24, 14))
        self.assertFailure(d, schedulers.SchedulerAlreadyClaimedError)
        return d

    @defer.inlineCallbacks
    def test_setSchedulerMaster_None(self):
        yield self.insertTestData([
            self.scheduler25, self.master14, self.scheduler25master,
        ])
        yield self.db.schedulers.setSchedulerMaster(25, None)
        sch = yield self.db.schedulers.getScheduler(25)
        self.assertEqual(sch['masterid'], None)

    @defer.inlineCallbacks
    def test_setSchedulerMaster_None_unowned(self):
        yield self.insertTestData([self.scheduler25])
        yield self.db.schedulers.setSchedulerMaster(25, None)
        sch = yield self.db.schedulers.getScheduler(25)
        self.assertEqual(sch['masterid'], None)

    def test_signature_getScheduler(self):
        @self.assertArgSpecMatches(self.db.schedulers.getScheduler)
        def getScheduler(self, schedulerid):
            pass

    @defer.inlineCallbacks
    def test_getScheduler(self):
        yield self.insertTestData([self.scheduler24])
        sch = yield self.db.schedulers.getScheduler(24)
        validation.verifyDbDict(self, 'schedulerdict', sch)
        self.assertEqual(sch, dict(
            id=24,
            name='schname',
            enabled=True,
            masterid=None))

    @defer.inlineCallbacks
    def test_getScheduler_missing(self):
        sch = yield self.db.schedulers.getScheduler(24)
        self.assertEqual(sch, None)

    @defer.inlineCallbacks
    def test_getScheduler_active(self):
        yield self.insertTestData([self.scheduler24, self.master13,
                                   self.scheduler24master])
        sch = yield self.db.schedulers.getScheduler(24)
        validation.verifyDbDict(self, 'schedulerdict', sch)
        self.assertEqual(sch, dict(
            id=24,
            name='schname',
            enabled=True,
            masterid=13))

    @defer.inlineCallbacks
    def test_getScheduler_inactive_but_linked(self):
        yield self.insertTestData([self.scheduler25, self.master14,
                                   self.scheduler25master])
        sch = yield self.db.schedulers.getScheduler(25)
        validation.verifyDbDict(self, 'schedulerdict', sch)
        self.assertEqual(sch, dict(
            id=25,
            name='schname2',
            enabled=True,
            masterid=14))  # row exists, but marked inactive

    def test_signature_getSchedulers(self):
        @self.assertArgSpecMatches(self.db.schedulers.getSchedulers)
        def getSchedulers(self, active=None, masterid=None):
            pass

    @defer.inlineCallbacks
    def test_getSchedulers(self):
        yield self.insertTestData([
            self.scheduler24, self.master13, self.scheduler24master,
            self.scheduler25,
        ])

        def schKey(sch):
            return sch['id']

        schlist = yield self.db.schedulers.getSchedulers()
        [validation.verifyDbDict(self, 'schedulerdict', sch)
         for sch in schlist]
        self.assertEqual(sorted(schlist, key=schKey), sorted([
            dict(id=24, name='schname', enabled=True, masterid=13),
            dict(id=25, name='schname2', enabled=True, masterid=None),
        ], key=schKey))

    @defer.inlineCallbacks
    def test_getSchedulers_masterid(self):
        yield self.insertTestData([
            self.scheduler24, self.master13, self.scheduler24master,
            self.scheduler25,
        ])
        schlist = yield self.db.schedulers.getSchedulers(masterid=13)
        [validation.verifyDbDict(self, 'schedulerdict', sch)
         for sch in schlist]
        self.assertEqual(sorted(schlist), sorted([
            dict(id=24, name='schname', enabled=True, masterid=13),
        ]))

    @defer.inlineCallbacks
    def test_getSchedulers_active(self):
        yield self.insertTestData([
            self.scheduler24, self.master13, self.scheduler24master,
            self.scheduler25
        ])
        schlist = yield self.db.schedulers.getSchedulers(active=True)
        [validation.verifyDbDict(self, 'schedulerdict', sch)
         for sch in schlist]
        self.assertEqual(sorted(schlist), sorted([
            dict(id=24, name='schname', enabled=True, masterid=13),
        ]))

    @defer.inlineCallbacks
    def test_getSchedulers_active_masterid(self):
        yield self.insertTestData([
            self.scheduler24, self.master13, self.scheduler24master,
            self.scheduler25
        ])
        schlist = yield self.db.schedulers.getSchedulers(
            active=True, masterid=13)
        [validation.verifyDbDict(self, 'schedulerdict', sch)
         for sch in schlist]
        self.assertEqual(sorted(schlist), sorted([
            dict(id=24, name='schname', enabled=True, masterid=13),
        ]))

        schlist = yield self.db.schedulers.getSchedulers(
            active=True, masterid=14)
        [validation.verifyDbDict(self, 'schedulerdict', sch)
         for sch in schlist]
        self.assertEqual(sorted(schlist), [])

    @defer.inlineCallbacks
    def test_getSchedulers_inactive(self):
        yield self.insertTestData([
            self.scheduler24, self.master13, self.scheduler24master,
            self.scheduler25
        ])
        schlist = yield self.db.schedulers.getSchedulers(active=False)
        [validation.verifyDbDict(self, 'schedulerdict', sch)
         for sch in schlist]
        self.assertEqual(sorted(schlist), sorted([
            dict(id=25, name='schname2', enabled=True, masterid=None),
        ]))

    @defer.inlineCallbacks
    def test_getSchedulers_inactive_masterid(self):
        yield self.insertTestData([
            self.scheduler24, self.master13, self.scheduler24master,
            self.scheduler25
        ])
        schlist = yield self.db.schedulers.getSchedulers(
            active=False, masterid=13)
        [validation.verifyDbDict(self, 'schedulerdict', sch)
         for sch in schlist]
        self.assertEqual(sorted(schlist), [])

        schlist = yield self.db.schedulers.getSchedulers(
            active=False, masterid=14)
        [validation.verifyDbDict(self, 'schedulerdict', sch)
         for sch in schlist]
        self.assertEqual(sorted(schlist), [])   # always returns [] by spec!


class RealTests(Tests):

    # tests that only "real" implementations will pass
    pass


class TestFakeDB(unittest.TestCase, Tests):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self, wantDb=True)
        self.db = self.master.db
        self.db.checkForeignKeys = True
        self.insertTestData = self.db.insertTestData

    def addClassifications(self, schedulerid, *classifications):
        self.db.schedulers.fakeClassifications(schedulerid,
                                               dict(classifications))
        return defer.succeed(None)


class TestRealDB(db.TestCase,
                 connector_component.ConnectorComponentMixin,
                 RealTests):

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['changes', 'schedulers', 'masters',
                         'sourcestamps', 'patches', 'scheduler_masters',
                         'scheduler_changes'])

        def finish_setup(_):
            self.db.schedulers = \
                schedulers.SchedulersConnectorComponent(self.db)
        d.addCallback(finish_setup)

        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()

    def addClassifications(self, schedulerid, *classifications):
        def thd(conn):
            q = self.db.model.scheduler_changes.insert()
            conn.execute(q, [
                dict(changeid=c[0], schedulerid=schedulerid, important=c[1])
                for c in classifications])
        return self.db.pool.do(thd)
