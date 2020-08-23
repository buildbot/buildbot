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

from twisted.trial import unittest

from buildbot.db.types.json import JsonObject
from buildbot.test.util import migration
from buildbot.util import sautils


class Migration(migration.MigrateTestMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpMigrateTest()

    def tearDown(self):
        return self.tearDownMigrateTest()

    def create_tables_thd(self, conn):
        metadata = sa.MetaData()
        metadata.bind = conn

        # workers
        workers = sautils.Table(
            "workers", metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String(50), nullable=False),
            sa.Column("info", JsonObject, nullable=False),
        )
        workers.create()

        conn.execute(workers.insert(), [
            dict(id=3, name='foo', info='{}')])

    def test_update(self):
        def setup_thd(conn):
            self.create_tables_thd(conn)

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            workers = sautils.Table('workers', metadata, autoload=True)
            self.assertIsInstance(workers.c.paused.type, sa.SmallInteger)
            self.assertIsInstance(workers.c.graceful.type, sa.SmallInteger)

            q = sa.select(
                [workers.c.name, workers.c.paused, workers.c.graceful])
            num_rows = 0
            for row in conn.execute(q):
                # verify that the default value was set correctly
                self.assertEqual(row.paused, False)
                self.assertEqual(row.graceful, False)
                num_rows += 1
            self.assertEqual(num_rows, 1)

        return self.do_test_migration(50, 51, setup_thd, verify_thd)
