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

    def setUp(self):
        d = self.setUpRealDatabase()

        def make_fake_pool(_):
            engine = enginestrategy.create_engine(self.db_url,
                                                  basedir=os.path.abspath('basedir'))

            # mock out the pool, and set up the model
            self.db = mock.Mock()
            self.db.pool.do_with_engine = lambda thd: defer.maybeDeferred(
                thd, engine)
            self.db.model = model.Model(self.db)
            self.db.start()
        d.addCallback(make_fake_pool)
        return d

    def tearDown(self):
        self.db.stop()
        return self.tearDownRealDatabase()

    def test_is_current_empty(self):
        d = self.db.model.is_current()
        d.addCallback(lambda r: self.assertFalse(r))
        return d

    def test_is_current_full(self):
        d = self.db.model.upgrade()
        d.addCallback(lambda _: self.db.model.is_current())
        d.addCallback(lambda r: self.assertTrue(r))
        return d

    # the upgrade method is very well-tested by the integration tests; the
    # remainder of the object is just tables.
