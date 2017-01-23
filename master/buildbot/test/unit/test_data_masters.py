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
from twisted.internet import task
from twisted.trial import unittest

from buildbot.data import masters
from buildbot.process.results import RETRY
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import endpoint
from buildbot.test.util import interfaces
from buildbot.util import epoch2datetime

SOMETIME = 1349016870
OTHERTIME = 1249016870


class MasterEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = masters.MasterEndpoint
    resourceTypeClass = masters.Master

    def setUp(self):
        self.setUpEndpoint()
        self.master.name = "myname"
        self.db.insertTestData([
            fakedb.Master(id=13, name='some:master', active=False,
                          last_active=SOMETIME),
            fakedb.Master(id=14, name='other:master', active=False,
                          last_active=SOMETIME),
            fakedb.Builder(id=23, name='bldr1'),
            fakedb.BuilderMaster(builderid=23, masterid=13),
            fakedb.Builder(id=24, name='bldr2'),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    def test_get_existing(self):
        d = self.callGet(('masters', 14))

        @d.addCallback
        def check(master):
            self.validateData(master)
            self.assertEqual(master['name'], 'other:master')
        return d

    def test_get_builderid_existing(self):
        d = self.callGet(('builders', 23, 'masters', 13))

        @d.addCallback
        def check(master):
            self.validateData(master)
            self.assertEqual(master['name'], 'some:master')
        return d

    def test_get_builderid_no_match(self):
        d = self.callGet(('builders', 24, 'masters', 13))

        @d.addCallback
        def check(master):
            self.assertEqual(master, None)
        return d

    def test_get_builderid_missing(self):
        d = self.callGet(('builders', 25, 'masters', 13))

        @d.addCallback
        def check(master):
            self.assertEqual(master, None)
        return d

    def test_get_missing(self):
        d = self.callGet(('masters', 99))

        @d.addCallback
        def check(master):
            self.assertEqual(master, None)
        return d


class MastersEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = masters.MastersEndpoint
    resourceTypeClass = masters.Master

    def setUp(self):
        self.setUpEndpoint()
        self.master.name = "myname"
        self.db.insertTestData([
            fakedb.Master(id=13, name='some:master', active=False,
                          last_active=SOMETIME),
            fakedb.Master(id=14, name='other:master', active=True,
                          last_active=OTHERTIME),
            fakedb.Builder(id=22),
            fakedb.BuilderMaster(masterid=13, builderid=22),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    def test_get(self):
        d = self.callGet(('masters',))

        @d.addCallback
        def check(masters):
            [self.validateData(m) for m in masters]
            self.assertEqual(sorted([m['masterid'] for m in masters]),
                             [13, 14])
        return d

    def test_get_builderid(self):
        d = self.callGet(('builders', 22, 'masters'))

        @d.addCallback
        def check(masters):
            [self.validateData(m) for m in masters]
            self.assertEqual(sorted([m['masterid'] for m in masters]),
                             [13])
        return d

    def test_get_builderid_missing(self):
        d = self.callGet(('builders', 23, 'masters'))

        @d.addCallback
        def check(masters):
            self.assertEqual(masters, [])
        return d


class Master(interfaces.InterfaceTests, unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(wantMq=True, wantDb=True,
                                             wantData=True, testcase=self)
        self.rtype = masters.Master(self.master)

    def test_signature_masterActive(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.masterActive,  # fake
            self.rtype.masterActive)  # real
        def masterActive(self, name, masterid):
            pass

    @defer.inlineCallbacks
    def test_masterActive(self):
        clock = task.Clock()
        clock.advance(60)

        self.master.db.insertTestData([
            fakedb.Master(id=13, name='myname', active=0,
                          last_active=0),
            fakedb.Master(id=14, name='other', active=1,
                          last_active=0),
            fakedb.Master(id=15, name='other2', active=1,
                          last_active=0),
        ])

        # initial checkin
        yield self.rtype.masterActive(
            name=u'myname', masterid=13, _reactor=clock)
        master = yield self.master.db.masters.getMaster(13)
        self.assertEqual(master, dict(id=13, name='myname',
                                      active=True, last_active=epoch2datetime(60)))
        self.assertEqual(self.master.mq.productions, [
            (('masters', '13', 'started'),
             dict(masterid=13, name='myname', active=True)),
        ])
        self.master.mq.productions = []

        # updated checkin time, re-activation
        clock.advance(60)
        yield self.master.db.masters.markMasterInactive(13)
        yield self.rtype.masterActive(
            u'myname', masterid=13, _reactor=clock)
        master = yield self.master.db.masters.getMaster(13)
        self.assertEqual(master, dict(id=13, name='myname',
                                      active=True, last_active=epoch2datetime(120)))
        self.assertEqual(self.master.mq.productions, [
            (('masters', '13', 'started'),
             dict(masterid=13, name='myname', active=True)),
        ])
        self.master.mq.productions = []

    def test_signature_masterStopped(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.masterStopped,  # fake
            self.rtype.masterStopped)  # real
        def masterStopped(self, name, masterid):
            pass

    @defer.inlineCallbacks
    def test_masterStopped(self):
        clock = task.Clock()
        clock.advance(60)

        self.master.db.insertTestData([
            fakedb.Master(id=13, name=u'aname', active=1,
                          last_active=clock.seconds()),
        ])

        self.rtype._masterDeactivated = mock.Mock()
        yield self.rtype.masterStopped(name=u'aname', masterid=13)
        self.rtype._masterDeactivated. \
            assert_called_with(13, 'aname')

    @defer.inlineCallbacks
    def test_masterStopped_already(self):
        clock = task.Clock()
        clock.advance(60)

        self.master.db.insertTestData([
            fakedb.Master(id=13, name=u'aname', active=0,
                          last_active=0),
        ])

        self.rtype._masterDeactivated = mock.Mock()
        yield self.rtype.masterStopped(name=u'aname', masterid=13)
        self.rtype._masterDeactivated.assert_not_called()

    def test_signature_expireMasters(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.expireMasters,  # fake
            self.rtype.expireMasters)  # real
        def expireMasters(self, forceHouseKeeping=False):
            pass

    @defer.inlineCallbacks
    def test_expireMasters(self):
        clock = task.Clock()
        clock.advance(60)

        self.master.db.insertTestData([
            fakedb.Master(id=14, name='other', active=1,
                          last_active=0),
            fakedb.Master(id=15, name='other', active=1,
                          last_active=0),
        ])

        self.rtype._masterDeactivated = mock.Mock()

        # check after 10 minutes, and see #14 deactivated; #15 gets deactivated
        # by another master, so it's not included here
        clock.advance(600)
        yield self.master.db.masters.markMasterInactive(15)
        yield self.rtype.expireMasters(_reactor=clock)
        master = yield self.master.db.masters.getMaster(14)
        self.assertEqual(master, dict(id=14, name='other',
                                      active=False, last_active=None))
        self.rtype._masterDeactivated. \
            assert_called_with(14, 'other')

    @defer.inlineCallbacks
    def test_masterDeactivated(self):
        self.master.db.insertTestData([
            fakedb.Master(id=14, name='other', active=0,
                          last_active=0),

            # set up a running build with some steps
            fakedb.Builder(id=77, name='b1'),
            fakedb.Worker(id=13, name='wrk'),
            fakedb.Buildset(id=8822),
            fakedb.BuildRequest(id=82, builderid=77, buildsetid=8822),
            fakedb.BuildRequestClaim(brid=82, masterid=14,
                                     claimed_at=SOMETIME),
            fakedb.Build(id=13, builderid=77, masterid=14, workerid=13,
                         buildrequestid=82, number=3, results=None),
            fakedb.Step(id=200, buildid=13),
            fakedb.Log(id=2000, stepid=200, num_lines=2),
            fakedb.LogChunk(logid=2000, first_line=1, last_line=2,
                            content=u'ab\ncd')
        ])

        # mock out the _masterDeactivated methods this will call
        for rtype in 'builder', 'scheduler', 'changesource':
            rtype_obj = getattr(self.master.data.rtypes, rtype)
            m = mock.Mock(name='%s._masterDeactivated' % rtype,
                          spec=rtype_obj._masterDeactivated)
            m.side_effect = lambda masterid: defer.succeed(None)
            rtype_obj._masterDeactivated = m

        # and the update methods..
        for meth in 'finishBuild', 'finishStep', 'finishLog':
            m = mock.create_autospec(getattr(self.master.data.updates, meth))
            m.side_effect = lambda *args, **kwargs: defer.succeed(None)
            setattr(self.master.data.updates, meth, m)

        yield self.rtype._masterDeactivated(14, 'other')

        self.master.data.rtypes.builder._masterDeactivated. \
            assert_called_with(masterid=14)
        self.master.data.rtypes.scheduler._masterDeactivated. \
            assert_called_with(masterid=14)
        self.master.data.rtypes.changesource._masterDeactivated. \
            assert_called_with(masterid=14)

        # see that we finished off that build and its steps and logs
        updates = self.master.data.updates
        updates.finishLog.assert_called_with(logid=2000)
        updates.finishStep.assert_called_with(
            stepid=200, results=RETRY, hidden=False)
        updates.finishBuild.assert_called_with(buildid=13, results=RETRY)

        self.assertEqual(self.master.mq.productions, [
            (('masters', '14', 'stopped'),
             dict(masterid=14, name='other', active=False)),
        ])
