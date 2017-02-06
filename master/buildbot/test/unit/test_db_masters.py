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
from twisted.internet import task
from twisted.trial import unittest

from buildbot.db import masters
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import connector_component
from buildbot.test.util import interfaces
from buildbot.test.util import validation
from buildbot.util import epoch2datetime

SOMETIME = 1348971992
SOMETIME_DT = epoch2datetime(SOMETIME)
OTHERTIME = 1008971992
OTHERTIME_DT = epoch2datetime(OTHERTIME)


class Tests(interfaces.InterfaceTests):

    # common sample data

    master_row = [
        fakedb.Master(id=7, name="some:master",
                      active=1, last_active=SOMETIME),
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

    @defer.inlineCallbacks
    def test_findMasterId_new(self):
        id = yield self.db.masters.findMasterId('some:master',
                                                _reactor=self.clock)
        masterdict = yield self.db.masters.getMaster(id)
        self.assertEqual(masterdict,
                         dict(id=id, name='some:master', active=False,
                              last_active=SOMETIME_DT))

    @defer.inlineCallbacks
    def test_findMasterId_exists(self):
        yield self.insertTestData([
            fakedb.Master(id=7, name='some:master'),
        ])
        id = yield self.db.masters.findMasterId('some:master')
        self.assertEqual(id, 7)

    @defer.inlineCallbacks
    def test_setMasterState_when_missing(self):
        activated = \
            yield self.db.masters.setMasterState(masterid=7, active=True)
        self.assertFalse(activated)

    @defer.inlineCallbacks
    def test_setMasterState_true_when_active(self):
        yield self.insertTestData([
            fakedb.Master(id=7, name='some:master',
                          active=1, last_active=OTHERTIME),
        ])
        activated = yield self.db.masters.setMasterState(
            masterid=7, active=True, _reactor=self.clock)
        self.assertFalse(activated)  # it was already active
        masterdict = yield self.db.masters.getMaster(7)
        self.assertEqual(masterdict,
                         dict(id=7, name='some:master', active=True,
                              last_active=SOMETIME_DT))  # timestamp updated

    @defer.inlineCallbacks
    def test_setMasterState_true_when_inactive(self):
        yield self.insertTestData([
            fakedb.Master(id=7, name='some:master',
                          active=0, last_active=OTHERTIME),
        ])
        activated = yield self.db.masters.setMasterState(
            masterid=7, active=True, _reactor=self.clock)
        self.assertTrue(activated)
        masterdict = yield self.db.masters.getMaster(7)
        self.assertEqual(masterdict,
                         dict(id=7, name='some:master', active=True,
                              last_active=SOMETIME_DT))

    @defer.inlineCallbacks
    def test_setMasterState_false_when_active(self):
        yield self.insertTestData([
            fakedb.Master(id=7, name='some:master',
                          active=1, last_active=OTHERTIME),
        ])
        deactivated = yield self.db.masters.setMasterState(
            masterid=7, active=False, _reactor=self.clock)
        self.assertTrue(deactivated)
        masterdict = yield self.db.masters.getMaster(7)
        self.assertEqual(masterdict,
                         dict(id=7, name='some:master', active=False,
                              last_active=OTHERTIME_DT))

    @defer.inlineCallbacks
    def test_setMasterState_false_when_inactive(self):
        yield self.insertTestData([
            fakedb.Master(id=7, name='some:master',
                          active=0, last_active=OTHERTIME),
        ])
        deactivated = yield self.db.masters.setMasterState(
            masterid=7, active=False, _reactor=self.clock)
        self.assertFalse(deactivated)
        masterdict = yield self.db.masters.getMaster(7)
        self.assertEqual(masterdict,
                         dict(id=7, name='some:master', active=False,
                              last_active=OTHERTIME_DT))

    @defer.inlineCallbacks
    def test_getMaster(self):
        yield self.insertTestData([
            fakedb.Master(id=7, name='some:master',
                          active=0, last_active=SOMETIME),
        ])
        masterdict = yield self.db.masters.getMaster(7)
        validation.verifyDbDict(self, 'masterdict', masterdict)
        self.assertEqual(masterdict, dict(id=7, name='some:master',
                                          active=False, last_active=SOMETIME_DT))

    @defer.inlineCallbacks
    def test_getMaster_missing(self):
        masterdict = yield self.db.masters.getMaster(7)
        self.assertEqual(masterdict, None)

    @defer.inlineCallbacks
    def test_getMasters(self):
        yield self.insertTestData([
            fakedb.Master(id=7, name='some:master',
                          active=0, last_active=SOMETIME),
            fakedb.Master(id=8, name='other:master',
                          active=1, last_active=OTHERTIME),
        ])
        masterlist = yield self.db.masters.getMasters()
        for masterdict in masterlist:
            validation.verifyDbDict(self, 'masterdict', masterdict)

        def masterKey(master):
            return master['id']

        expected = sorted([
            dict(id=7, name='some:master',
                 active=0, last_active=SOMETIME_DT),
            dict(id=8, name='other:master',
                 active=1, last_active=OTHERTIME_DT),
        ], key=masterKey)
        self.assertEqual(sorted(masterlist, key=masterKey), expected)


class RealTests(Tests):

    # tests that only "real" implementations will pass

    @defer.inlineCallbacks
    def test_setMasterState_false_deletes_links(self):
        yield self.insertTestData([
            fakedb.Master(id=7, name='some:master',
                          active=1, last_active=OTHERTIME),
            fakedb.Scheduler(id=21),
            fakedb.SchedulerMaster(schedulerid=21, masterid=7),
        ])
        deactivated = yield self.db.masters.setMasterState(
            masterid=7, active=False, _reactor=self.clock)
        self.assertTrue(deactivated)

        # check that the scheduler_masters row was deleted
        def thd(conn):
            tbl = self.db.model.scheduler_masters
            self.assertEqual(conn.execute(tbl.select()).fetchall(), [])
        yield self.db.pool.do(thd)


class TestFakeDB(unittest.TestCase, Tests):

    def setUp(self):
        self.clock = task.Clock()
        self.clock.advance(SOMETIME)
        self.master = fakemaster.make_master(wantDb=True, testcase=self)
        self.db = self.master.db
        self.db.checkForeignKeys = True
        self.insertTestData = self.db.insertTestData


class TestRealDB(unittest.TestCase,
                 connector_component.ConnectorComponentMixin,
                 RealTests):

    def setUp(self):
        self.clock = task.Clock()
        self.clock.advance(SOMETIME)

        d = self.setUpConnectorComponent(
            table_names=['masters', 'schedulers', 'scheduler_masters'])

        @d.addCallback
        def finish_setup(_):
            self.db.masters = masters.MastersConnectorComponent(self.db)
        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()
