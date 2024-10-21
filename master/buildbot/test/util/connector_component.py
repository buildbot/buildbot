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

import types
from typing import TYPE_CHECKING

from twisted.internet import defer

from buildbot.db import model
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import db
from buildbot.util.sautils import get_upsert_method

if TYPE_CHECKING:
    from buildbot.db import logs
    from buildbot.db import pool
    from buildbot.db import sourcestamps


class FakeDBConnector:
    logs: logs.LogsConnectorComponent
    pool: pool.DBThreadPool
    sourcestamps: sourcestamps.SourceStampsConnectorComponent


class ConnectorComponentMixin(TestReactorMixin, db.RealDatabaseMixin):
    """
    Implements a mock DBConnector object, replete with a thread pool and a DB
    model.  This includes a RealDatabaseMixin, so subclasses should not
    instantiate that class directly.  The connector appears at C{self.db}, and
    the component should be attached to it as an attribute.

    @ivar db: fake database connector
    @ivar db.pool: DB thread pool
    @ivar db.model: DB model
    """

    @defer.inlineCallbacks
    def setUpConnectorComponent(self, table_names=None, basedir='basedir', dialect_name='sqlite'):
        """Set up C{self.db}, using the given db_url and basedir."""
        self.setup_test_reactor(auto_tear_down=False)

        if table_names is None:
            table_names = []

        yield self.setUpRealDatabase(table_names=table_names, basedir=basedir)

        self.db = FakeDBConnector()
        self.db.pool = self.db_pool
        self.db.upsert = get_upsert_method(self.db_engine)
        self.db.has_native_upsert = self.db.upsert != get_upsert_method(None)
        self.db.master = yield fakemaster.make_master(self)
        self.db.model = model.Model(self.db)
        self.db._engine = types.SimpleNamespace(dialect=types.SimpleNamespace(name=dialect_name))

    @defer.inlineCallbacks
    def tearDownConnectorComponent(self):
        yield self.tearDownRealDatabase()
        # break some reference loops, just for fun
        del self.db.pool
        del self.db.model
        del self.db
        yield self.tear_down_test_reactor()


class FakeConnectorComponentMixin(TestReactorMixin):
    # Just like ConnectorComponentMixin, but for working with fake database

    @defer.inlineCallbacks
    def setUpConnectorComponent(self):
        self.setup_test_reactor(auto_tear_down=False)
        self.master = yield fakemaster.make_master(self, wantDb=True)
        self.db = self.master.db
        self.db.checkForeignKeys = True
        self.insert_test_data = self.db.insert_test_data

    @defer.inlineCallbacks
    def tearDownConnectorComponent(self):
        yield self.tear_down_test_reactor()
