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
from buildbot.db import connector
from buildbot import config
from buildbot.test.util import db
from buildbot.test.fake import fakemaster

class DBConnector(db.RealDatabaseMixin, unittest.TestCase):
    """
    Basic tests of the DBConnector class - all start with an empty DB
    """

    @defer.inlineCallbacks
    def setUp(self):
        yield self.setUpRealDatabase(table_names=[
                    'changes', 'change_properties', 'change_files', 'patches',
                    'sourcestamps', 'buildset_properties', 'buildsets',
                    'sourcestampsets' ])

        self.master = fakemaster.make_master()
        self.master.config = config.MasterConfig()
        self.db = connector.DBConnector(self.master,
                                os.path.abspath('basedir'))

    @defer.inlineCallbacks
    def tearDown(self):
        if self.db.running:
            yield self.db.stopService()

        yield self.tearDownRealDatabase()

    @defer.inlineCallbacks
    def startService(self, check_version=False):
        self.master.config.db['db_url'] = self.db_url
        yield self.db.setup(check_version=check_version)
        self.db.startService()
        yield self.db.reconfigService(self.master.config)


    # tests

    def test_doCleanup_service(self):
        d = self.startService()
        @d.addCallback
        def check(_):
            self.assertTrue(self.db.cleanup_timer.running)

    def test_doCleanup_unconfigured(self):
        self.db.changes.pruneChanges = mock.Mock(
                        return_value=defer.succeed(None))
        self.db._doCleanup()
        self.assertFalse(self.db.changes.pruneChanges.called)

    def test_doCleanup_configured(self):
        self.db.changes.pruneChanges = mock.Mock(
                        return_value=defer.succeed(None))
        d = self.startService()
        @d.addCallback
        def check(_):
            self.db._doCleanup()
            self.assertTrue(self.db.changes.pruneChanges.called)
        return d

    def test_setup_check_version_bad(self):
        d = self.startService(check_version=True)
        def eb(f):
            f.trap(connector.DatabaseNotReadyError)
        def cb(_):
            self.fail("startService unexpectedly succeeded")
        d.addCallbacks(cb, eb)
        return d

    def test_setup_check_version_good(self):
        self.db.model.is_current = lambda : defer.succeed(True)
        return self.startService(check_version=True)
