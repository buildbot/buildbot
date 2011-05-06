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

import os
import mock
from twisted.internet import defer
from twisted.trial import unittest
from buildbot import master
from buildbot.util import subscription
from buildbot.test.util import dirs
from buildbot.test.fake import fakedb

class Subscriptions(dirs.DirsMixin, unittest.TestCase):

    def setUp(self):
        basedir = os.path.abspath('basedir')
        d = self.setUpDirs(basedir)
        def set_master(_):
            self.master = master.BuildMaster(basedir)
            self.master.db_poll_interval = None
        d.addCallback(set_master)
        return d

    def tearDown(self):
        return self.tearDownDirs()

    def test_change_subscription(self):
        self.newchange = mock.Mock()
        self.master.db = mock.Mock()
        self.master.db.changes.addChange.return_value = \
            defer.succeed(self.newchange)

        cb = mock.Mock()
        sub = self.master.subscribeToChanges(cb)
        self.assertIsInstance(sub, subscription.Subscription)

        d = self.master.addChange(this='chdict')
        def check(change):
            # master called the right thing in the db component
            self.master.db.changes.addChange.assert_called_with(this='chdict')
            # addChange returned the right value
            self.failUnless(change is self.newchange) # addChange return value
            # and the notification sub was called correctly
            cb.assert_called_with(self.newchange)
        d.addCallback(check)
        return d

    def test_buildset_subscription(self):
        self.master.db = mock.Mock()
        self.master.db.buildsets.addBuildset.return_value = \
            defer.succeed((938593, dict(a=19,b=20)))

        cb = mock.Mock()
        sub = self.master.subscribeToBuildsets(cb)
        self.assertIsInstance(sub, subscription.Subscription)

        d = self.master.addBuildset(ssid=999)
        def check((bsid,brids)):
            # master called the right thing in the db component
            self.master.db.buildsets.addBuildset.assert_called_with(ssid=999)
            # addBuildset returned the right value
            self.assertEqual((bsid,brids), (938593, dict(a=19,b=20)))
            # and the notification sub was called correctly
            cb.assert_called_with(bsid=938593, ssid=999)
        d.addCallback(check)
        return d

    def test_buildset_completion_subscription(self):
        self.master.db = mock.Mock()

        cb = mock.Mock()
        sub = self.master.subscribeToBuildsetCompletions(cb)
        self.assertIsInstance(sub, subscription.Subscription)

        self.master._buildsetComplete(938593, 999)
        # assert the notification sub was called correctly
        cb.assert_called_with(938593, 999)

class Polling(dirs.DirsMixin, unittest.TestCase):

    def setUp(self):
        self.gotten_changes = []
        self.gotten_buildset_additions = []
        self.gotten_buildset_completions = []
        self.gotten_buildrequest_additions = []

        basedir = os.path.abspath('basedir')
        d = self.setUpDirs(basedir)
        def set_master(_):
            self.master = master.BuildMaster(basedir)

            self.db = self.master.db = fakedb.FakeDBConnector(self)

            self.master.db_poll_interval = 10

            # overridesubscription callbacks
            self.master._change_subs = sub = mock.Mock()
            sub.deliver = self.deliverChange
            self.master._new_buildset_subs = sub = mock.Mock()
            sub.deliver = self.deliverBuildsetAddition
            self.master._complete_buildset_subs = sub = mock.Mock()
            sub.deliver = self.deliverBuildsetCompletion
            self.master._new_buildrequest_subs = sub = mock.Mock()
            sub.deliver = self.deliverBuildRequestAddition

        d.addCallback(set_master)
        return d

    def tearDown(self):
        return self.tearDownDirs()

    def deliverChange(self, change):
        self.gotten_changes.append(change)

    def deliverBuildsetAddition(self, **kwargs):
        self.gotten_buildset_additions.append(kwargs)

    def deliverBuildsetCompletion(self, bsid, result):
        self.gotten_buildset_completions.append((bsid, result))

    def deliverBuildRequestAddition(self, notif):
        self.gotten_buildrequest_additions.append(notif)

    # tests

    def test_pollDatabaseChanges_empty(self):
        self.db.insertTestData([
            fakedb.Object(id=22, name='master',
                          class_name='buildbot.master.BuildMaster'),
        ])
        d = self.master.pollDatabaseChanges()
        def check(_):
            self.assertEqual(self.gotten_changes, [])
            self.assertEqual(self.gotten_buildset_additions, [])
            self.assertEqual(self.gotten_buildset_completions, [])
            self.db.state.assertState(22, last_processed_change=0)
        d.addCallback(check)
        return d

    def test_pollDatabaseChanges_catchup(self):
        # with no existing state, it should catch up to the most recent change,
        # but not process anything
        self.db.insertTestData([
            fakedb.Object(id=22, name='master',
                          class_name='buildbot.master.BuildMaster'),
            fakedb.Change(changeid=10),
            fakedb.Change(changeid=11),
        ])
        d = self.master.pollDatabaseChanges()
        def check(_):
            self.assertEqual(self.gotten_changes, [])
            self.assertEqual(self.gotten_buildset_additions, [])
            self.assertEqual(self.gotten_buildset_completions, [])
            self.db.state.assertState(22, last_processed_change=11)
        d.addCallback(check)
        return d

    def test_pollDatabaseChanges_multiple(self):
        self.db.insertTestData([
            fakedb.Object(id=53, name='master',
                          class_name='buildbot.master.BuildMaster'),
            fakedb.ObjectState(objectid=53, name='last_processed_change',
                               value_json='10'),
            fakedb.Change(changeid=10),
            fakedb.Change(changeid=11),
            fakedb.Change(changeid=12),
        ])
        d = self.master.pollDatabaseChanges()
        def check(_):
            self.assertEqual([ ch.number for ch in self.gotten_changes],
                             [ 11, 12 ]) # note 10 was already seen
            self.assertEqual(self.gotten_buildset_additions, [])
            self.assertEqual(self.gotten_buildset_completions, [])
            self.db.state.assertState(53, last_processed_change=12)
        d.addCallback(check)
        return d

    def test_pollDatabaseChanges_nothing_new(self):
        self.db.insertTestData([
            fakedb.Object(id=53, name='master',
                          class_name='buildbot.master.BuildMaster'),
            fakedb.ObjectState(objectid=53, name='last_processed_change',
                               value_json='10'),
            fakedb.Change(changeid=10),
        ])
        d = self.master.pollDatabaseChanges()
        def check(_):
            self.assertEqual(self.gotten_changes, [])
            self.assertEqual(self.gotten_buildset_additions, [])
            self.assertEqual(self.gotten_buildset_completions, [])
            self.db.state.assertState(53, last_processed_change=10)
        d.addCallback(check)
        return d

    def test_pollDatabaseBuildRequests_empty(self):
        d = self.master.pollDatabaseBuildRequests()
        def check(_):
            self.assertEqual(self.gotten_buildrequest_additions, [])
        d.addCallback(check)
        return d

    def test_pollDatabaseBuildRequests_new(self):
        self.db.insertTestData([
            fakedb.SourceStamp(id=127),
            fakedb.Buildset(bsid=99, sourcestampid=127),
            fakedb.BuildRequest(id=19, buildsetid=99, buildername='9teen'),
            fakedb.BuildRequest(id=20, buildsetid=99, buildername='twenty')
        ])
        d = self.master.pollDatabaseBuildRequests()
        def check(_):
            self.assertEqual(sorted(self.gotten_buildrequest_additions),
                    sorted([dict(bsid=99, brid=19, buildername='9teen'),
                            dict(bsid=99, brid=20, buildername='twenty')]))
        d.addCallback(check)
        return d

    def test_pollDatabaseBuildRequests_incremental(self):
        d = defer.succeed(None)
        def insert1(_):
            self.db.insertTestData([
                fakedb.SourceStamp(id=127),
                fakedb.Buildset(bsid=99, sourcestampid=127),
                fakedb.BuildRequest(id=11, buildsetid=9,
                                        buildername='eleventy'),
            ])
        d.addCallback(insert1)
        d.addCallback(lambda _ : self.master.pollDatabaseBuildRequests())
        def insert2_and_claim(_):
            self.gotten_buildrequest_additions.append('MARK')
            self.db.insertTestData([
                fakedb.BuildRequest(id=20, buildsetid=9,
                                        buildername='twenty'),
            ])
            self.db.buildrequests.fakeClaimBuildRequest(11)
        d.addCallback(insert2_and_claim)
        d.addCallback(lambda _ : self.master.pollDatabaseBuildRequests())
        def unclaim(_):
            self.gotten_buildrequest_additions.append('MARK')
            self.db.buildrequests.fakeUnclaimBuildRequest(11)
            # note that at this point brid 20 is still unclaimed, but we do
            # not get a new notification about it
        d.addCallback(unclaim)
        d.addCallback(lambda _ : self.master.pollDatabaseBuildRequests())
        def check(_):
            self.assertEqual(self.gotten_buildrequest_additions, [
                dict(bsid=9, brid=11, buildername='eleventy'),
                'MARK',
                dict(bsid=9, brid=20, buildername='twenty'),
                'MARK',
                dict(bsid=9, brid=11, buildername='eleventy'),
            ])
        d.addCallback(check)
        return d

