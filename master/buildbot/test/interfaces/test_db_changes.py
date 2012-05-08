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
from buildbot.test.fake import fakedb, fakemaster
from buildbot.test.util import interfaces, connector_component, dbtype
from buildbot.db import changes

change13 = [
    fakedb.Change(changeid=13, author="dustin",
        comments="fix spelling", is_dir=0, branch="master",
        revision="deadbeef", when_timestamp=266738400,
        revlink=None, category=None, repository='', codebase='',
        project=''),

    fakedb.ChangeFile(changeid=13, filename='master/README.txt'),
    fakedb.ChangeFile(changeid=13, filename='slave/README.txt'),

    fakedb.ChangeProperty(changeid=13, property_name='notest',
        property_value='["no","Change"]'),
]

class Tests(interfaces.InterfaceTests):

    def setUp(self):
        raise NotImplementedError

    def test_signature_addChange(self):
        @self.assertArgSpecMatches(self.db.changes.addChange)
        def addChange(self, author=None, files=None, comments=None, is_dir=0,
            revision=None, when_timestamp=None, branch=None, category=None,
            revlink='', properties={}, repository='', codebase='',
            project='', uid=None):
            pass

    def test_signature_getChange(self):
        @self.assertArgSpecMatches(self.db.changes.getChange)
        def getChange(self, key, no_cache=False):
            pass

    def test_getChange_none(self):
        d = self.db.changes.getChange(99)
        @d.addCallback
        def check(chdict):
            self.assertEqual(chdict, None)
        return d

    def test_getChange_chdict(self):
        d = self.db.changes.getChange(13)
        @d.addCallback
        def check(chdict):
            dbtype.verifyChdict(self, chdict)
        return d

    def test_signature_getChangeUids(self):
        @self.assertArgSpecMatches(self.db.changes.getChangeUids)
        def getChangeUids(self, changeid):
            pass

    def test_signature_getRecentChanges(self):
        @self.assertArgSpecMatches(self.db.changes.getRecentChanges)
        def getRecentChanges(self, count):
            pass

    def test_signature_getLatestChangeid(self):
        @self.assertArgSpecMatches(self.db.changes.getLatestChangeid)
        def getLatestChangeid(self):
            pass


class RealTests(Tests):

    # tests that only "real" implementations will pass
    pass

class TestFakeDB(unittest.TestCase, Tests):

    def setUp(self):
        self.master = fakemaster.make_master()
        self.db = fakedb.FakeDBConnector(self)
        return self.db.insertTestData(change13)

class TestRealDB(unittest.TestCase,
        connector_component.ConnectorComponentMixin,
        RealTests):

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['changes', 'change_files',
                'change_properties', 'scheduler_changes', 'objects',
                'sourcestampsets', 'sourcestamps', 'sourcestamp_changes',
                'patches', 'change_users', 'users'])

        @d.addCallback
        def finish_setup(_):
            self.db.changes = changes.ChangesConnectorComponent(self.db)
            return self.insertTestData(change13)
        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()

