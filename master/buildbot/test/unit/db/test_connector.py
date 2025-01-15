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
from unittest import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.config.master import MasterConfig
from buildbot.db import connector
from buildbot.db import exceptions
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin


class TestDBConnector(TestReactorMixin, unittest.TestCase):
    """
    Basic tests of the DBConnector class - all start with an empty DB
    """

    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()

        self.master = yield fakemaster.make_master(
            self, wantDb=True, auto_upgrade=False, check_version=False
        )
        self.master.config = MasterConfig()
        self.db_url = self.master.db.configured_db_config.db_url
        yield self.master.db._shutdown()
        self.db = connector.DBConnector(os.path.abspath('basedir'))
        yield self.db.set_master(self.master)

        @defer.inlineCallbacks
        def cleanup():
            if self.db.pool is not None:
                yield self.db.pool.stop()

        self.addCleanup(cleanup)

    @defer.inlineCallbacks
    def startService(self, check_version=False):
        self.master.config.db.db_url = self.db_url
        yield self.db.setup(check_version=check_version)
        yield self.db.startService()
        yield self.db.reconfigServiceWithBuildbotConfig(self.master.config)

    # tests
    @defer.inlineCallbacks
    def test_doCleanup_service(self):
        yield self.startService()

        self.assertTrue(self.db.cleanup_timer.running)

    def test_doCleanup_unconfigured(self):
        self.db.changes.pruneChanges = mock.Mock(return_value=defer.succeed(None))
        self.db._doCleanup()
        self.assertFalse(self.db.changes.pruneChanges.called)

    @defer.inlineCallbacks
    def test_doCleanup_configured(self):
        self.db.changes.pruneChanges = mock.Mock(return_value=defer.succeed(None))
        yield self.startService()

        self.db._doCleanup()
        self.assertTrue(self.db.changes.pruneChanges.called)

    @defer.inlineCallbacks
    def test_setup_check_version_bad(self):
        if self.db_url == 'sqlite://':
            raise unittest.SkipTest('sqlite in-memory model is always upgraded at connection')
        with self.assertRaises(exceptions.DatabaseNotReadyError):
            yield self.startService(check_version=True)

    def test_setup_check_version_good(self):
        self.db.model.is_current = lambda: defer.succeed(True)
        return self.startService(check_version=True)
