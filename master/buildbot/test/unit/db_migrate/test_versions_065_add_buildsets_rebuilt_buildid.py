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
from sqlalchemy.inspection import inspect
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

        # parent_buildid foreign key is removed for the purposes of the test
        buildsets = sautils.Table(
            "buildsets",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("external_idstring", sa.String(256)),
            sa.Column("reason", sa.String(256)),
            sa.Column("submitted_at", sa.Integer, nullable=False),
            sa.Column(
                "complete", sa.SmallInteger, nullable=False, server_default=sa.DefaultClause("0")
            ),
            sa.Column("complete_at", sa.Integer),
            sa.Column("results", sa.SmallInteger),
            sa.Column("parent_relationship", sa.Text),
        )
        buildsets.create()

        conn.execute(
            buildsets.insert(),
            [
                {
                    "id": 4,
                    "external_idstring": 5,
                    "reason": "rebuild",
                    "submitted_at": 1695730972,
                    "complete": 1,
                    "complete_at": 1695730977,
                    "results": 0,
                    "parent_relationship": "Triggered from",
                }
            ],
        )

        builds = sautils.Table("builds", metadata, sa.Column("id", sa.Integer, primary_key=True))
        builds.create()

        conn.execute(
            builds.insert(),
            [
                {
                    "id": 123,
                }
            ],
        )

    def test_update(self):
        def setup_thd(conn):
            self.create_tables_thd(conn)

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            # check that builsets.rebuilt_buildid has been added
            buildsets = sautils.Table('buildsets', metadata, autoload=True)
            self.assertIsInstance(buildsets.c.rebuilt_buildid.type, sa.Integer)

            q = sa.select([
                buildsets.c.rebuilt_buildid,
            ])

            all_fk_info = inspect(conn).get_foreign_keys("buildsets")
            fk_in_search = []
            for fk in all_fk_info:
                if fk["name"] == "rebuilt_buildid":
                    fk_in_search.append(fk)
                # verify that a foreign with name "fk_buildsets_rebuilt_buildid" was found
                self.assertEqual(len(fk_in_search), 1)

            conn.execute(
                buildsets.insert(),
                [
                    {
                        "id": 5,
                        "external_idstring": 6,
                        "reason": "rebuild",
                        "submitted_at": 1695730973,
                        "complete": 1,
                        "complete_at": 1695730978,
                        "results": 0,
                        "rebuilt_buildid": 123,
                        "parent_relationship": "Triggered from",
                    }
                ],
            )

            rebuilt_buildid_list = []
            for row in conn.execute(q):
                rebuilt_buildid_list.append(row.rebuilt_buildid)

            # verify that the 1st default value was set correctly to None
            self.assertEqual(rebuilt_buildid_list, [None, 123])

        return self.do_test_migration('064', '065', setup_thd, verify_thd)
