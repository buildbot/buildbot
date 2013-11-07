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

import sqlalchemy as sa

from buildbot.test.util import migration
from twisted.trial import unittest


class Migration(migration.MigrateTestMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpMigrateTest()

    def tearDown(self):
        return self.tearDownMigrateTest()

    def test_migration(self):
        def setup_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            sa.Table('builds', metadata,
                     sa.Column('id', sa.Integer, primary_key=True),
                     ).create()

        def verify_thd(conn):
            r = conn.execute("select * from steps")
            self.assertEqual(r.fetchall(), [])
            r = conn.execute("select * from logs")
            self.assertEqual(r.fetchall(), [])
            r = conn.execute("select * from logchunks")
            self.assertEqual(r.fetchall(), [])

        return self.do_test_migration(29, 30, setup_thd, verify_thd)
