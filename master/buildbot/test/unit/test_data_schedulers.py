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
from twisted.trial import unittest
from twisted.internet import defer
from buildbot.data import schedulers
from buildbot.test.util import validation, endpoint, interfaces
from buildbot.test.fake import fakemaster, fakedb

class Scheduler(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = schedulers.SchedulerEndpoint

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.Master(id=22, active=0),
            fakedb.Master(id=33, active=1),
            fakedb.Scheduler(id=13, name='some:scheduler'),
            fakedb.SchedulerMaster(schedulerid=13, masterid=None),
            fakedb.Scheduler(id=14, name='other:scheduler'),
            fakedb.SchedulerMaster(schedulerid=14, masterid=22),
            fakedb.Scheduler(id=15, name='other:scheduler'),
            fakedb.SchedulerMaster(schedulerid=15, masterid=33),
        ])


    def tearDown(self):
        self.tearDownEndpoint()

    def test_get_existing(self):
        d = self.callGet(dict(), dict(schedulerid=14))
        @d.addCallback
        def check(scheduler):
            validation.verifyData(self, 'scheduler', {}, scheduler)
            self.assertEqual(scheduler['name'], 'other:scheduler')
        return d

    def test_get_no_master(self):
        d = self.callGet(dict(), dict(schedulerid=13))
        @d.addCallback
        def check(scheduler):
            validation.verifyData(self, 'scheduler', {}, scheduler)
            self.assertEqual(scheduler['master'], None),
        return d

    def test_get_masterid_existing(self):
        d = self.callGet(dict(), dict(schedulerid=14, masterid=22))
        @d.addCallback
        def check(scheduler):
            validation.verifyData(self, 'scheduler', {}, scheduler)
            self.assertEqual(scheduler['name'], 'other:scheduler')
        return d

    def test_get_masterid_no_match(self):
        d = self.callGet(dict(), dict(schedulerid=13, masterid=33))
        @d.addCallback
        def check(scheduler):
            self.assertEqual(scheduler, None)
        return d

    def test_get_masterid_missing(self):
        d = self.callGet(dict(), dict(schedulerid=13, masterid=25))
        @d.addCallback
        def check(scheduler):
            self.assertEqual(scheduler, None)
        return d

    def test_get_missing(self):
        d = self.callGet(dict(), dict(schedulerid=99))
        @d.addCallback
        def check(scheduler):
            self.assertEqual(scheduler, None)
        return d


class Schedulers(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = schedulers.SchedulersEndpoint

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.Master(id=22, active=0),
            fakedb.Master(id=33, active=1),
            fakedb.Scheduler(id=13, name='some:scheduler'),
            fakedb.SchedulerMaster(schedulerid=13, masterid=None),
            fakedb.Scheduler(id=14, name='other:scheduler'),
            fakedb.SchedulerMaster(schedulerid=14, masterid=22),
            fakedb.Scheduler(id=15, name='other:scheduler'),
            fakedb.SchedulerMaster(schedulerid=15, masterid=33),
            fakedb.Scheduler(id=16, name='other:scheduler'),
            fakedb.SchedulerMaster(schedulerid=16, masterid=33),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    def test_get(self):
        d = self.callGet(dict(), dict())
        @d.addCallback
        def check(schedulers):
            [ validation.verifyData(self, 'scheduler', {}, m)
                for m in schedulers ]
            self.assertEqual(sorted([m['schedulerid'] for m in schedulers]),
                             [13, 14, 15, 16])
        return d

    def test_get_masterid(self):
        d = self.callGet(dict(), dict(masterid=33))
        @d.addCallback
        def check(schedulers):
            [ validation.verifyData(self, 'scheduler', {}, m)
                for m in schedulers ]
            self.assertEqual(sorted([m['schedulerid'] for m in schedulers]),
                             [15, 16])
        return d

    def test_get_masterid_missing(self):
        d = self.callGet(dict(), dict(masterid=23))
        @d.addCallback
        def check(schedulers):
            self.assertEqual(schedulers, [])
        return d

    def test_startConsuming(self):
        self.callStartConsuming({}, {},
                expected_filter=('scheduler', None, None))


class SchedulerResourceType(interfaces.InterfaceTests, unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(wantMq=True, wantDb=True,
                                            wantData=True, testcase=self)
        self.rtype = schedulers.SchedulerResourceType(self.master)

    def test_signature_findSchedulerId(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.findSchedulerId, # fake
            self.rtype.findSchedulerId) # real
        def findSchedulerId(self, name):
            pass

    @defer.inlineCallbacks
    def test_findSchedulerId(self):
        self.master.db.schedulers.findSchedulerId = mock.Mock(
                                        return_value=defer.succeed(10))
        self.assertEqual((yield self.rtype.findSchedulerId(u'sch')), 10)
        self.master.db.schedulers.findSchedulerId.assert_called_with(u'sch')

    def test_signature_setSchedulerMaster(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.setSchedulerMaster, # fake
            self.rtype.setSchedulerMaster) # real
        def setSchedulerMaster(self, schedulerid, masterid):
            pass

    @defer.inlineCallbacks
    def test_setSchedulerMaster_succeeds(self):
        self.master.db.schedulers.setSchedulerMaster = mock.Mock(
                                        return_value=defer.succeed(None))
        yield self.rtype.setSchedulerMaster(10, 20)
        self.master.db.schedulers.setSchedulerMaster.assert_called_with(10, 20)

    @defer.inlineCallbacks
    def test__masterDeactivated(self):
        yield self.master.db.insertTestData([
            fakedb.Master(id=22, active=0),
            fakedb.Scheduler(id=13, name='some:scheduler'),
            fakedb.SchedulerMaster(schedulerid=13, masterid=22),
            fakedb.Scheduler(id=14, name='other:scheduler'),
            fakedb.SchedulerMaster(schedulerid=14, masterid=22),
        ])
        yield self.rtype._masterDeactivated(22)
        self.master.db.schedulers.assertSchedulerMaster(13, None)
        self.master.db.schedulers.assertSchedulerMaster(14, None)
