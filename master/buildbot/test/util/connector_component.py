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

from __future__ import absolute_import
from __future__ import print_function

from buildbot.db import model
from buildbot.test.fake import fakemaster
from buildbot.test.util import db


class FakeDBConnector(object):
    pass


class ConnectorComponentMixin(db.RealDatabaseMixin):

    """
    Implements a mock DBConnector object, replete with a thread pool and a DB
    model.  This includes a RealDatabaseMixin, so subclasses should not
    instantiate that class directly.  The connector appears at C{self.db}, and
    the component should be attached to it as an attribute.

    @ivar db: fake database connector
    @ivar db.pool: DB thread pool
    @ivar db.model: DB model
    """

    def setUpConnectorComponent(self, table_names=None, basedir='basedir'):
        """Set up C{self.db}, using the given db_url and basedir."""
        if table_names is None:
            table_names = []

        d = self.setUpRealDatabase(table_names=table_names, basedir=basedir)

        @d.addCallback
        def finish_setup(_):
            self.db = FakeDBConnector()
            self.db.pool = self.db_pool
            self.db.master = fakemaster.make_master()
            self.db.model = model.Model(self.db)
        return d

    def tearDownConnectorComponent(self):
        d = self.tearDownRealDatabase()

        @d.addCallback
        def finish_cleanup(_):
            self.db_pool.shutdown()
            # break some reference loops, just for fun
            del self.db.pool
            del self.db.model
            del self.db
        return d
