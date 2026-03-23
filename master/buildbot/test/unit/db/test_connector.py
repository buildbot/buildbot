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

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.config.master import MasterConfig
from buildbot.db import connector
from buildbot.db import exceptions
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin

if TYPE_CHECKING:
    from twisted.internet.defer import Deferred

    from buildbot.util.twisted import InlineCallbacksType


class TestDBConnector(TestReactorMixin, unittest.TestCase):
    """
    Basic tests of the DBConnector class - all start with an empty DB
    """

    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
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
        def cleanup() -> InlineCallbacksType[None]:
            if self.db.pool is not None:
                yield self.db.pool.stop()

        self.addCleanup(cleanup)

    @defer.inlineCallbacks
    def startService(self, check_version: bool = False) -> InlineCallbacksType[None]:
        self.master.config.db.db_url = self.db_url
        yield self.db.setup(check_version=check_version)
        yield self.db.startService()
        yield self.db.reconfigServiceWithBuildbotConfig(self.master.config)

    # tests
    @defer.inlineCallbacks
    def test_doCleanup_service(self) -> InlineCallbacksType[None]:
        yield self.startService()

        self.assertTrue(self.db.cleanup_timer.running)

    def test_doCleanup_unconfigured(self) -> None:
        self.db.changes.pruneChanges = mock.Mock(return_value=defer.succeed(None))  # type: ignore[method-assign]
        self.db._doCleanup()
        self.assertFalse(self.db.changes.pruneChanges.called)

    @defer.inlineCallbacks
    def test_doCleanup_configured(self) -> InlineCallbacksType[None]:
        self.db.changes.pruneChanges = mock.Mock(return_value=defer.succeed(None))  # type: ignore[method-assign]
        yield self.startService()

        self.db._doCleanup()
        self.assertTrue(self.db.changes.pruneChanges.called)

    @defer.inlineCallbacks
    def test_setup_check_version_bad(self) -> InlineCallbacksType[None]:
        if self.db_url == 'sqlite://':
            raise unittest.SkipTest('sqlite in-memory model is always upgraded at connection')
        with self.assertRaises(exceptions.DatabaseNotReadyError):
            yield self.startService(check_version=True)

    def test_setup_check_version_good(self) -> Deferred[None]:
        self.db.model.is_current = lambda: defer.succeed(True)  # type: ignore[method-assign]
        return self.startService(check_version=True)
