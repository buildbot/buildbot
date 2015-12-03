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

from buildbot.changes import changes
from buildbot.status import base
from buildbot.status import master
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from twisted.internet import defer
from twisted.trial import unittest


class FakeStatusReceiver(base.StatusReceiver):
    pass


class TestStatus(unittest.TestCase):

    def makeStatus(self):
        m = fakemaster.make_master(wantData=True, testcase=self)
        self.db = m.db
        m.basedir = r'C:\BASEDIR'
        m.botmaster.builderNames = []
        s = master.Status()
        s.setServiceParent(m)
        m.startService()
        return s

    def test_getBuildSets(self):
        s = self.makeStatus()
        self.db.insertTestData([
            fakedb.Buildset(id=91, complete=0,
                            complete_at=298297875, results=-1, submitted_at=266761875,
                            external_idstring='extid', reason='rsn1'),
            fakedb.Buildset(id=92, complete=1,
                            complete_at=298297876, results=7, submitted_at=266761876,
                            external_idstring='extid', reason='rsn2'),
        ])

        d = s.getBuildSets()

        def check(bslist):
            self.assertEqual([bs.id for bs in bslist], [91])
        d.addCallback(check)
        return d

    @defer.inlineCallbacks
    def test_reconfigServiceWithBuildbotConfig(self):
        status = self.makeStatus()
        config = mock.Mock()

        # add a status reciever
        sr0 = FakeStatusReceiver()
        config.status = [sr0]

        yield status.reconfigServiceWithBuildbotConfig(config)
        m = status.master
        self.assertTrue(sr0.running)
        self.assertIdentical(sr0.master, m)

        # add a status reciever
        sr1 = FakeStatusReceiver()
        sr2 = FakeStatusReceiver()
        config.status = [sr1, sr2]

        yield status.reconfigServiceWithBuildbotConfig(config)

        self.assertFalse(sr0.running)
        self.assertIdentical(sr0.master, None)
        self.assertTrue(sr1.running)
        self.assertIdentical(sr1.master, m)
        self.assertTrue(sr2.running)
        self.assertIdentical(sr2.master, m)

        # reconfig with those two (a regression check)
        sr1 = FakeStatusReceiver()
        sr2 = FakeStatusReceiver()
        config.status = [sr1, sr2]

        yield status.reconfigServiceWithBuildbotConfig(config)

        # and back to nothing
        config.status = []
        yield status.reconfigServiceWithBuildbotConfig(config)

        self.assertIdentical(sr0.master, None)
        self.assertIdentical(sr1.master, None)
        self.assertIdentical(sr2.master, None)

    @defer.inlineCallbacks
    def test_change_consumer_cb_nobody_interested(self):
        m = mock.Mock(name='master')
        status = master.Status()

        yield status.change_consumer_cb('change.13.new',
                                        dict(changeid=13))

        self.assertFalse(m.db.changes.getChange.called)

    @defer.inlineCallbacks
    def test_change_consumer_cb(self):
        status = self.makeStatus()

        # insert the change that will be announced in the database
        self.db.insertTestData([
            fakedb.Change(changeid=13),
        ])

        # patch out fromChdict
        self.patch(changes.Change, 'fromChdict',
                   classmethod(lambda cls, mstr, chd:
                               defer.succeed(dict(m=mstr, c=chd))))

        # set up a watcher
        class W(object):
            pass
        watcher = W()
        watcher.changeAdded = mock.Mock(name='changeAdded')
        status.subscribe(watcher)

        yield status.change_consumer_cb('change.13.new',
                                        dict(changeid=13))

        self.assertTrue(watcher.changeAdded.called)
        args, kwargs = watcher.changeAdded.call_args
        self.assertEqual(args[0]['m'], status.master)
        self.assertEqual(args[0]['c']['changeid'], 13)
