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

        # builderid, buildrequestid, workerid, masterid foreign keys are removed for the
        # purposes of the test
        builds = sautils.Table(
            'builds',
            metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('number', sa.Integer, nullable=False),
            sa.Column('started_at', sa.Integer, nullable=False),
            sa.Column('complete_at', sa.Integer),
            sa.Column('state_string', sa.Text, nullable=False),
            sa.Column('results', sa.Integer),
        )
        builds.create()

        conn.execute(
            builds.insert(),
            [
                {
                    "id": 4,
                    "number": 5,
                    "started_at": 1695730972,
                    "complete_at": 1695730975,
                    "state_string": "test build",
                    "results": 0,
                }
            ],
        )

    def test_update(self):
        def setup_thd(conn):
            self.create_tables_thd(conn)

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            builds = sautils.Table('builds', metadata, autoload=True)
            self.assertIsInstance(builds.c.locks_duration_s.type, sa.Integer)

            conn.execute(
                builds.insert(),
                [
                    {
                        "id": 5,
                        "number": 6,
                        "started_at": 1695730982,
                        "complete_at": 1695730985,
                        "locks_duration_s": 12,
                        "state_string": "test build",
                        "results": 0,
                    }
                ],
            )

            durations = []
            for row in conn.execute(sa.select([builds.c.locks_duration_s])):
                durations.append(row.locks_duration_s)
            self.assertEqual(durations, [0, 12])

        return self.do_test_migration('065', '066', setup_thd, verify_thd)
