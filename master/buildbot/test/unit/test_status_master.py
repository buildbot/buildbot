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
from buildbot.status import master, base
from buildbot.test.fake import fakedb

class FakeStatusReceiver(base.StatusReceiver):
    pass

class TestStatus(unittest.TestCase):

    def makeStatus(self):
        m = mock.Mock(name='master')
        self.db = m.db = fakedb.FakeDBConnector(self)
        m.basedir = r'C:\BASEDIR'
        s = master.Status(m)
        return s

    def test_getBuildSets(self):
        s = self.makeStatus()
        self.db.insertTestData([
            fakedb.Buildset(id=91, sourcestampsetid=234, complete=0,
                    complete_at=298297875, results=-1, submitted_at=266761875,
                    external_idstring='extid', reason='rsn1'),
            fakedb.Buildset(id=92, sourcestampsetid=234, complete=1,
                    complete_at=298297876, results=7, submitted_at=266761876,
                    external_idstring='extid', reason='rsn2'),
        ])

        d = s.getBuildSets()
        def check(bslist):
            self.assertEqual([ bs.id for bs in bslist ], [ 91 ])
        d.addCallback(check)
        return d

    @defer.inlineCallbacks
    def test_reconfigService(self):
        m = mock.Mock(name='master')
        status = master.Status(m)
        status.startService()

        config = mock.Mock()

        # add a status reciever
        sr0 = FakeStatusReceiver()
        config.status = [ sr0 ]

        yield status.reconfigService(config)

        self.assertTrue(sr0.running)
        self.assertIdentical(sr0.master, m)

        # add a status reciever
        sr1 = FakeStatusReceiver()
        sr2 = FakeStatusReceiver()
        config.status = [ sr1, sr2 ]

        yield status.reconfigService(config)

        self.assertFalse(sr0.running)
        self.assertIdentical(sr0.master, None)
        self.assertTrue(sr1.running)
        self.assertIdentical(sr1.master, m)
        self.assertTrue(sr2.running)
        self.assertIdentical(sr2.master, m)

        # reconfig with those two (a regression check)
        sr1 = FakeStatusReceiver()
        sr2 = FakeStatusReceiver()
        config.status = [ sr1, sr2 ]

        yield status.reconfigService(config)

        # and back to nothing
        config.status = [ ]
        yield status.reconfigService(config)

        self.assertIdentical(sr0.master, None)
        self.assertIdentical(sr1.master, None)
        self.assertIdentical(sr2.master, None)

    @defer.inlineCallbacks
    def test_getURLForBuildRequest(self):
        s = self.makeStatus()
        sourcestamps = [{'b_codebase': 'c1', 'b_revision': 'r1', 'b_branch': 'b1','b_sourcestampsetid': 1},
                        {'b_codebase': 'c2', 'b_revision': 'r2', 'b_branch': 'b2','b_sourcestampsetid': 1}]

        s.master.db.mastersconfig.setupMaster()
        s.botmaster.builders = []

        url = yield s.getURLForBuildRequest(1, "buildername", 1, "buildername",
                                                             sourcestamps)

        self.assertEqual(url['text'], 'buildername #1')
        self.assertEqual(url['path'], 'baseurl/builders/buildername/builds/1?c1_branch=b1&c2_branch=b2')
