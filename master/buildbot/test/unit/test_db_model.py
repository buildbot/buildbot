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

from buildbot.db import enginestrategy
from buildbot.db import model
from buildbot.test.util import db


class DBConnector_Basic(db.RealDatabaseMixin, unittest.TestCase):

    """
    Basic tests of the DBConnector class - all start with an empty DB
    """

    @defer.inlineCallbacks
    def setUp(self):
        yield self.setUpRealDatabase()

        engine = enginestrategy.create_engine(self.db_url,
                                              basedir=os.path.abspath('basedir'))

        # mock out the pool, and set up the model
        self.db = mock.Mock()
        self.db.pool.do_with_engine = lambda thd: defer.maybeDeferred(
            thd, engine)
        self.db.model = model.Model(self.db)
        self.db.start()

    def tearDown(self):
        self.db.stop()
        return self.tearDownRealDatabase()

    @defer.inlineCallbacks
    def test_is_current_empty(self):
        res = yield self.db.model.is_current()
        self.assertFalse(res)

    @defer.inlineCallbacks
    def test_is_current_full(self):
        yield self.db.model.upgrade()
        res = yield self.db.model.is_current()
        self.assertTrue(res)

    # the upgrade method is very well-tested by the integration tests; the
    # remainder of the object is just tables.
