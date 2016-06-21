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

import mock

from twisted.internet import defer
from twisted.python import failure
from twisted.trial import unittest

from buildbot.data import schedulers
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import endpoint
from buildbot.test.util import interfaces


class SchedulerEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = schedulers.SchedulerEndpoint
    resourceTypeClass = schedulers.Scheduler

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.Master(id=22, active=0),
            fakedb.Master(id=33, active=1),
            fakedb.Scheduler(id=13, name='some:scheduler'),
            fakedb.SchedulerMaster(schedulerid=13, masterid=None),
            fakedb.Scheduler(id=14, name='other:scheduler'),
            fakedb.SchedulerMaster(schedulerid=14, masterid=22),
            fakedb.Scheduler(id=15, name='another:scheduler'),
            fakedb.SchedulerMaster(schedulerid=15, masterid=33),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    def test_get_existing(self):
        d = self.callGet(('schedulers', 14))

        @d.addCallback
        def check(scheduler):
            self.validateData(scheduler)
            self.assertEqual(scheduler['name'], 'other:scheduler')
        return d

    def test_get_no_master(self):
        d = self.callGet(('schedulers', 13))

        @d.addCallback
        def check(scheduler):
            self.validateData(scheduler)
            self.assertEqual(scheduler['master'], None),
        return d

    def test_get_masterid_existing(self):
        d = self.callGet(('masters', 22, 'schedulers', 14))

        @d.addCallback
        def check(scheduler):
            self.validateData(scheduler)
            self.assertEqual(scheduler['name'], 'other:scheduler')
        return d

    def test_get_masterid_no_match(self):
        d = self.callGet(('masters', 33, 'schedulers', 13))

        @d.addCallback
        def check(scheduler):
            self.assertEqual(scheduler, None)
        return d

    def test_get_masterid_missing(self):
        d = self.callGet(('masters', 99, 'schedulers', 13))

        @d.addCallback
        def check(scheduler):
            self.assertEqual(scheduler, None)
        return d

    def test_get_missing(self):
        d = self.callGet(('schedulers', 99))

        @d.addCallback
        def check(scheduler):
            self.assertEqual(scheduler, None)
        return d

    @defer.inlineCallbacks
    def test_action_enable(self):
        r = yield self.callControl("enable", {'enabled': False}, ('schedulers', 13))
        self.assertEqual(r, None)


class SchedulersEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = schedulers.SchedulersEndpoint
    resourceTypeClass = schedulers.Scheduler

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.Master(id=22, active=0),
            fakedb.Master(id=33, active=1),
            fakedb.Scheduler(id=13, name='some:scheduler'),
            fakedb.SchedulerMaster(schedulerid=13, masterid=None),
            fakedb.Scheduler(id=14, name='other:scheduler'),
            fakedb.SchedulerMaster(schedulerid=14, masterid=22),
            fakedb.Scheduler(id=15, name='another:scheduler'),
            fakedb.SchedulerMaster(schedulerid=15, masterid=33),
            fakedb.Scheduler(id=16, name='wholenother:scheduler'),
            fakedb.SchedulerMaster(schedulerid=16, masterid=33),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    def test_get(self):
        d = self.callGet(('schedulers',))

        @d.addCallback
        def check(schedulers):
            [self.validateData(m) for m in schedulers]
            self.assertEqual(sorted([m['schedulerid'] for m in schedulers]),
                             [13, 14, 15, 16])
        return d

    def test_get_masterid(self):
        d = self.callGet(('masters', 33, 'schedulers'))

        @d.addCallback
        def check(schedulers):
            [self.validateData(m) for m in schedulers]
            self.assertEqual(sorted([m['schedulerid'] for m in schedulers]),
                             [15, 16])
        return d

    def test_get_masterid_missing(self):
        d = self.callGet(('masters', 23, 'schedulers'))

        @d.addCallback
        def check(schedulers):
            self.assertEqual(schedulers, [])
        return d


class Scheduler(interfaces.InterfaceTests, unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(wantMq=True, wantDb=True,
                                             wantData=True, testcase=self)
        self.rtype = schedulers.Scheduler(self.master)

    def test_signature_schedulerEnable(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.schedulerEnable,
            self.rtype.schedulerEnable)
        def schedulerEnable(self, schedulerid, v):
            pass

    @defer.inlineCallbacks
    def test_schedulerEnable(self):
        SOMETIME = 1348971992
        yield self.master.db.insertTestData([
            fakedb.Master(id=22, active=0, last_active=SOMETIME),
            fakedb.Scheduler(id=13, name='some:scheduler'),
            fakedb.SchedulerMaster(schedulerid=13, masterid=22),
        ])
        yield self.rtype.schedulerEnable(13, False)
        self.master.mq.assertProductions(
            [(('schedulers', '13', 'updated'),
              {'enabled': False,
               'master': {'active': False,
                          'last_active': fakedb._mkdt(SOMETIME),
                          'masterid': 22,
                          'name': u'some:master'},
               'name': u'some:scheduler',
               'schedulerid': 13})])
        yield self.rtype.schedulerEnable(13, True)
        self.master.mq.assertProductions(
            [(('schedulers', '13', 'updated'),
              {'enabled': True,
               'master': {'active': False,
                          'last_active': fakedb._mkdt(SOMETIME),
                          'masterid': 22,
                          'name': u'some:master'},
               'name': u'some:scheduler',
               'schedulerid': 13})])

    def test_signature_findSchedulerId(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.findSchedulerId,  # fake
            self.rtype.findSchedulerId)  # real
        def findSchedulerId(self, name):
            pass

    @defer.inlineCallbacks
    def test_findSchedulerId(self):
        self.master.db.schedulers.findSchedulerId = mock.Mock(
            return_value=defer.succeed(10))
        self.assertEqual((yield self.rtype.findSchedulerId(u'sch')), 10)
        self.master.db.schedulers.findSchedulerId.assert_called_with(u'sch')

    def test_signature_trySetSchedulerMaster(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.trySetSchedulerMaster,  # fake
            self.rtype.trySetSchedulerMaster)  # real
        def trySetSchedulerMaster(self, schedulerid, masterid):
            pass

    @defer.inlineCallbacks
    def test_trySetSchedulerMaster_succeeds(self):
        self.master.db.schedulers.setSchedulerMaster = mock.Mock(
            return_value=defer.succeed(None))

        result = yield self.rtype.trySetSchedulerMaster(10, 20)

        self.assertTrue(result)
        self.master.db.schedulers.setSchedulerMaster.assert_called_with(10, 20)

    @defer.inlineCallbacks
    def test_trySetSchedulerMaster_fails(self):
        d = defer.fail(failure.Failure(
            schedulers.SchedulerAlreadyClaimedError('oh noes')))

        self.master.db.schedulers.setSchedulerMaster = mock.Mock(
            return_value=d)
        result = yield self.rtype.trySetSchedulerMaster(10, 20)

        self.assertFalse(result)

    @defer.inlineCallbacks
    def test_trySetSchedulerMaster_raisesOddException(self):
        d = defer.fail(failure.Failure(RuntimeError('oh noes')))

        self.master.db.schedulers.setSchedulerMaster = mock.Mock(
            return_value=d)

        try:
            yield self.rtype.trySetSchedulerMaster(10, 20)
        except RuntimeError:
            pass
        else:
            self.fail("The RuntimeError did not propogate")

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
