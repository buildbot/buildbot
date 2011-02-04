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
from buildbot.db import model, pool, enginestrategy

class ConnectorComponentMixin(object):
    """
    Implements a mock DBConnector object, replete with a thread
    pool and a DB model.  This can work with, but does not require,
    the RealDatabaseMixin.  The connector appears at C{self.db}, and
    the component should be attached to it as an attribute.

    This has the unfortunate side-effect of making the various connectors
    depend on a functioning threadpool and model, but the alternative is to
    re-implement these modules or mock them out, both of which options would be
    more complex than simply using the existing modules!
    """
    def setUpConnectorComponent(self, db_url, basedir='basedir'):
        """Set up C{self.db}, using the given db_url and basedir."""
        self.db = mock.Mock()
        self.db._engine = enginestrategy.create_engine(db_url, basedir=basedir)
        self.db.pool = pool.DBThreadPool(self.db._engine)
        self.db.model = model.Model(self.db)

    def tearDownConnectorComponent(self):
        # break some reference loops, just for fun
        del self.db.pool
        del self.db.model
        del self.db
