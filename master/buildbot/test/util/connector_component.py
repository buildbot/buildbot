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


from twisted.internet import defer

from buildbot.db import model
from buildbot.test.fake import fakemaster
from buildbot.test.util import db
from buildbot.test.util.misc import TestReactorMixin


class FakeDBConnector:
    pass


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
    def setUpConnectorComponent(self, table_names=None, basedir='basedir'):
        self.setUpTestReactor()

        """Set up C{self.db}, using the given db_url and basedir."""
        if table_names is None:
            table_names = []

        yield self.setUpRealDatabase(table_names=table_names, basedir=basedir)

        self.db = FakeDBConnector()
        self.db.pool = self.db_pool
        self.db.master = fakemaster.make_master(self)
        self.db.model = model.Model(self.db)

    @defer.inlineCallbacks
    def tearDownConnectorComponent(self):
        yield self.tearDownRealDatabase()

        self.db_pool.shutdown()
        # break some reference loops, just for fun
        del self.db.pool
        del self.db.model
        del self.db
