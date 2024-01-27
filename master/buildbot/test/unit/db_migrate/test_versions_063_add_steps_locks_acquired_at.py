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

        # buildid foreign key is removed for the purposes of the test
        steps = sautils.Table(
            'steps',
            metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('number', sa.Integer, nullable=False),
            sa.Column('name', sa.String(50), nullable=False),
            sa.Column('buildid', sa.Integer, nullable=True),
            sa.Column('started_at', sa.Integer),
            sa.Column('complete_at', sa.Integer),
            sa.Column('state_string', sa.Text, nullable=False),
            sa.Column('results', sa.Integer),
            sa.Column('urls_json', sa.Text, nullable=False),
            sa.Column('hidden', sa.SmallInteger, nullable=False, server_default='0'),
        )
        steps.create()

        conn.execute(
            steps.insert(),
            [
                {
                    "id": 4,
                    "number": 123,
                    "name": "step",
                    "buildid": 12,
                    "started_at": 1690848000,
                    "complete_at": 1690848030,
                    "state_string": "state",
                    "results": 0,
                    "urls_json": "",
                    "hidden": 0,
                }
            ],
        )

    def test_update(self):
        def setup_thd(conn):
            self.create_tables_thd(conn)

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            steps = sautils.Table('steps', metadata, autoload=True)
            self.assertIsInstance(steps.c.locks_acquired_at.type, sa.Integer)

            q = sa.select([
                steps.c.name,
                steps.c.locks_acquired_at,
            ])

            num_rows = 0
            for row in conn.execute(q):
                self.assertEqual(row.name, "step")
                self.assertEqual(row.locks_acquired_at, 1690848000)
                num_rows += 1
            self.assertEqual(num_rows, 1)

        return self.do_test_migration('062', '063', setup_thd, verify_thd)
