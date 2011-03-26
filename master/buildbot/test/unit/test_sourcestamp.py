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
from buildbot.test.fake import fakedb
from buildbot import sourcestamp

class TestBuilderBuildCreation(unittest.TestCase):

    def test_fromSsdict_changes(self):
        master = mock.Mock()
        master.db = fakedb.FakeDBConnector(self)
        master.db.insertTestData([
            fakedb.Change(changeid=13, branch='trunk', revision='9283',
                        repository='svn://...', project='world-domination'),
            fakedb.Change(changeid=14, branch='trunk', revision='9284',
                        repository='svn://...', project='world-domination'),
            fakedb.Change(changeid=15, branch='trunk', revision='9284',
                        repository='svn://...', project='world-domination'),
            fakedb.SourceStamp(id=234, branch='trunk', revision='9284',
                        repository='svn://...', project='world-domination'),
            fakedb.SourceStampChange(sourcestampid=234, changeid=14),
            fakedb.SourceStampChange(sourcestampid=234, changeid=13),
            fakedb.SourceStampChange(sourcestampid=234, changeid=15),
        ])
        # use getSourceStamp to minimize the risk from changes to the format of
        # the ssdict
        d = master.db.sourcestamps.getSourceStamp(234)
        d.addCallback(lambda ssdict :
                    sourcestamp.SourceStamp.fromSsdict(master, ssdict))
        def check(ss):
            self.assertEqual(ss.ssid, 234)
            self.assertEqual(ss.branch, 'trunk')
            self.assertEqual(ss.revision, '9284')
            self.assertEqual(ss.patch, None)
            self.assertEqual([ ch.number for ch in ss.changes], [13, 14, 15])
            self.assertEqual(ss.project, 'world-domination')
            self.assertEqual(ss.repository, 'svn://...')
        d.addCallback(check)
        return d

    def test_fromSsdict_patch(self):
        master = mock.Mock()
        master.db = fakedb.FakeDBConnector(self)
        master.db.insertTestData([
            fakedb.Patch(id=99, subdir='/foo', patchlevel=3,
                        patch_base64='LS0gKys='),
            fakedb.SourceStamp(id=234, branch='trunk', revision='9284',
                        repository='svn://...', project='world-domination',
                        patchid=99),
        ])
        # use getSourceStamp to minimize the risk from changes to the format of
        # the ssdict
        d = master.db.sourcestamps.getSourceStamp(234)
        d.addCallback(lambda ssdict :
                    sourcestamp.SourceStamp.fromSsdict(master, ssdict))
        def check(ss):
            self.assertEqual(ss.ssid, 234)
            self.assertEqual(ss.branch, 'trunk')
            self.assertEqual(ss.revision, '9284')
            self.assertEqual(ss.patch, ('-- ++', 3))
            self.assertEqual(ss.changes, ())
            self.assertEqual(ss.project, 'world-domination')
            self.assertEqual(ss.repository, 'svn://...')
        d.addCallback(check)
        return d

    def test_fromSsdict_simple(self):
        master = mock.Mock()
        master.db = fakedb.FakeDBConnector(self)
        master.db.insertTestData([
            fakedb.SourceStamp(id=234, branch='trunk', revision='9284',
                        repository='svn://...', project='world-domination'),
        ])
        # use getSourceStamp to minimize the risk from changes to the format of
        # the ssdict
        d = master.db.sourcestamps.getSourceStamp(234)
        d.addCallback(lambda ssdict :
                    sourcestamp.SourceStamp.fromSsdict(master, ssdict))
        def check(ss):
            self.assertEqual(ss.ssid, 234)
            self.assertEqual(ss.branch, 'trunk')
            self.assertEqual(ss.revision, '9284')
            self.assertEqual(ss.patch, None)
            self.assertEqual(ss.changes, ())
            self.assertEqual(ss.project, 'world-domination')
            self.assertEqual(ss.repository, 'svn://...')
        d.addCallback(check)
        return d
