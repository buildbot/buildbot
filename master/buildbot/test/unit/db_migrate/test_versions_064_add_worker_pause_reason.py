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

        workers = sautils.Table(
            "workers",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String(50), nullable=False),
            sa.Column("info", JsonObject, nullable=False),
            sa.Column("paused", sa.SmallInteger, nullable=False, server_default="0"),
            sa.Column("graceful", sa.SmallInteger, nullable=False, server_default="0"),
        )
        workers.create()

        conn.execute(
            workers.insert(),
            [
                {
                    "id": 4,
                    "name": "worker1",
                    "info": "{\"key\": \"value\"}",
                    "paused": 0,
                    "graceful": 0,
                }
            ],
        )

    def test_update(self):
        def setup_thd(conn):
            self.create_tables_thd(conn)

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            workers = sautils.Table('workers', metadata, autoload=True)
            self.assertIsInstance(workers.c.pause_reason.type, sa.Text)

            q = sa.select([
                workers.c.name,
                workers.c.pause_reason,
            ])

            num_rows = 0
            for row in conn.execute(q):
                self.assertEqual(row.name, "worker1")
                self.assertIsNone(row.pause_reason)
                num_rows += 1
            self.assertEqual(num_rows, 1)

        return self.do_test_migration('063', '064', setup_thd, verify_thd)
