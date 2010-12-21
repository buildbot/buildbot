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
import shutil
from twisted.trial import unittest
from twisted.internet import defer
from buildbot.changes.changes import Change
from buildbot import util
from buildbot.db.connector import DBConnector
from buildbot.test.util import db

class TestChangeProperties(db.RealDatabaseMixin, unittest.TestCase):
    def setUp(self):
        self.setUpRealDatabase()
        self.basedir = os.path.abspath("basedir")
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        os.makedirs(self.basedir)

        self.db = DBConnector(self.db_url, self.basedir)
        d = self.db.model.upgrade()
        d.addCallback(lambda _ : self.db.start())
        return d

    def tearDown(self):
        self.db.stop()
        shutil.rmtree(self.basedir)
        self.tearDownRealDatabase()

    def testDBGetChangeByNumber(self):
        db = self.db

        c = Change(who="catlee", files=["foo"], comments="", branch="b1")
        c.properties.setProperty("foo", "bar", "property_source")

        d = defer.succeed(None)

        # add the change to the db..
        d.addCallback(lambda _ : db.addChangeToDatabase(c)) # TODO not async yet

        # get it and check (probably from the cache)
        d.addCallback(lambda _ : db.getChangeByNumber(c.number))
        def check(c1):
            self.assertEquals(c1.properties, c.properties)
        d.addCallback(check)

        # flush the cache
        def flush(_):
            db._change_cache = util.LRUCache()
        d.addCallback(flush)

        # and get the change again, this time using the db, and check it
        d.addCallback(lambda _ : db.getChangeByNumber(c.number))
        d.addCallback(check)
