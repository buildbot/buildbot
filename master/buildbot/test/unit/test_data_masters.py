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
from twisted.internet import task, defer
from buildbot.data import masters
from buildbot.util import epoch2datetime
from buildbot.test.util import types, endpoint
from buildbot.test.fake import fakemaster, fakedb

SOMETIME = 1349016870
OTHERTIME = 1249016870

class Master(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = masters.MasterEndpoint

    def setUp(self):
        self.setUpEndpoint()
        self.master.name = "myname"
        self.db.insertTestData([
            fakedb.Master(id=13, name='some:master', active=False,
                            last_active=SOMETIME),
        ])


    def tearDown(self):
        self.tearDownEndpoint()


    def test_get_existing(self):
        d = self.callGet(dict(), dict(masterid=13))
        @d.addCallback
        def check(master):
            types.verifyData(self, 'master', {}, master)
            self.assertEqual(master['name'], 'some:master')
        return d


    def test_get_missing(self):
        d = self.callGet(dict(), dict(masterid=99))
        @d.addCallback
        def check(master):
            self.assertEqual(master, None)
        return d


class Masters(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = masters.MastersEndpoint

    def setUp(self):
        self.setUpEndpoint()
        self.master.name = "myname"
        self.db.insertTestData([
            fakedb.Master(id=13, name='some:master', active=False,
                            last_active=SOMETIME),
            fakedb.Master(id=14, name='other:master', active=True,
                            last_active=OTHERTIME),
        ])


    def tearDown(self):
        self.tearDownEndpoint()


    def test_get(self):
        d = self.callGet(dict(), dict())
        @d.addCallback
        def check(masters):
            [ types.verifyData(self, 'master', {}, m) for m in masters ]
            self.assertEqual(sorted([m['masterid'] for m in masters]),
                             [13, 14])
        return d

    def test_startConsuming(self):
        self.callStartConsuming({}, {},
                expected_filter=('master', None, None))


class MasterResourceType(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(wantMq=True, wantDb=True,
                                                testcase=self)
        self.rtype = masters.MasterResourceType(self.master)

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
            (('master', '13', 'started'),
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
            (('master', '13', 'started'),
             dict(masterid=13, name='myname', active=True)),
        ])
        self.master.mq.productions = []

    @defer.inlineCallbacks
    def test_masterStopped(self):
        clock = task.Clock()
        clock.advance(60)

        self.master.db.insertTestData([
            fakedb.Master(id=13, name=u'aname', active=1,
                            last_active=clock.seconds()),
        ])

        yield self.rtype.masterStopped(name=u'aname', masterid=13)
        self.assertEqual(self.master.mq.productions, [
            (('master', '13', 'stopped'),
             dict(masterid=13, name='aname', active=False)),
        ])

    @defer.inlineCallbacks
    def test_masterStopped_already(self):
        clock = task.Clock()
        clock.advance(60)

        self.master.db.insertTestData([
            fakedb.Master(id=13, name=u'aname', active=0,
                            last_active=0),
        ])

        yield self.rtype.masterStopped(name=u'aname', masterid=13)
        self.assertEqual(self.master.mq.productions, [])

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

        # check after 10 minutes, and see #14 deactivated; #15 gets deactivated
        # by another master, so it's not included here
        clock.advance(600)
        yield self.master.db.masters.markMasterInactive(15)
        yield self.rtype.expireMasters(_reactor=clock)
        master = yield self.master.db.masters.getMaster(14)
        self.assertEqual(master, dict(id=14, name='other',
                    active=False, last_active=epoch2datetime(0)))
        self.assertEqual(self.master.mq.productions, [
            (('master', '14', 'stopped'),
             dict(masterid=14, name='other', active=False)),
        ])
