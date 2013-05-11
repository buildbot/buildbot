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

class Migration(migration.MigrateTestMixin, unittest.TestCase):

    table_columns = [
        ('changes', 'comments'),
        ('buildset_properties', 'property_value'),
    ]

    def setUp(self):
        return self.setUpMigrateTest()

    def tearDown(self):
        return self.tearDownMigrateTest()

    def create_tables_thd(self, conn):
        metadata = sa.MetaData()
        metadata.bind = conn

        # Create the tables/columns we're testing
        for table, column in self.table_columns:
            tbl = sa.Table(table, metadata,
                sa.Column(column, sa.String(1024), nullable=False),
                # the rest is unimportant
            )
            tbl.create()

    # tests

    def test_update(self):
        def setup_thd(conn):
            self.create_tables_thd(conn)

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            # Verify that the columns have been upate to the Text type.
            for table, column in self.table_columns:
                tbl = sa.Table(table, metadata, autoload=True)
                self.assertIsInstance(getattr(tbl.c, column).type, sa.Text)

        return self.do_test_migration(22, 23, setup_thd, verify_thd)
