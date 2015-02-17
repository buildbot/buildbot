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

from buildbot.db import dbconfig
from buildbot.test.util import db
from twisted.internet import defer
from twisted.internet import threads
from twisted.trial import unittest


class TestDbConfig(db.RealDatabaseMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        # as we will open the db twice, we can't use in memory sqlite
        yield self.setUpRealDatabase(table_names=['objects', 'object_state'], sqlite_memory=False)
        yield threads.deferToThread(self.createDbConfig)

    def createDbConfig(self):
        self.dbConfig = dbconfig.DbConfig(self.db_url, self.basedir)

    def tearDown(self):
        return self.tearDownRealDatabase()

    def test_basic(self):
        def thd():
            slavesInDB = ['foo', 'bar']
            self.dbConfig.set(u"slaves", slavesInDB)
            slaves = self.dbConfig.get(u"slaves")
            self.assertEqual(slaves, slavesInDB)

        return threads.deferToThread(thd)
