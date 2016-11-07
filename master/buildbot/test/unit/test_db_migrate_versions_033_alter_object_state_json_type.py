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
from buildbot.db import types as bsa

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

        objects = sa.Table("objects", metadata,
                           # unique ID for this object
                           sa.Column("id", sa.Integer, primary_key=True),
                           # object's user-given name
                           sa.Column('name', sa.String(128), nullable=False),
                           # object's class name, basically representing a "type" for the state
                           sa.Column('class_name', sa.String(128), nullable=False),
                           )
        objects.create()

        object_state = sa.Table("object_state", metadata,
                                # object for which this value is set
                                sa.Column("objectid", sa.Integer, sa.ForeignKey('objects.id'), nullable=False),
                                # name for this value (local to the object)
                                sa.Column("name", sa.String(length=255), nullable=False),
                                # value, as a JSON string
                                sa.Column("value_json", sa.Text, nullable=False))
        object_state.create()

    # tests

    def test_update(self):
        def setup_thd(conn):
            self.create_tables_thd(conn)

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            tbl = sa.Table('object_state', metadata, autoload=True)
            col = getattr(tbl.c, 'value_json')

            expected_type = bsa.LongText().dialect_impl(conn.dialect).load_dialect_impl(conn.dialect)

            self.assertIsInstance(col.type, type(expected_type))

        return self.do_test_migration(32, 33, setup_thd, verify_thd)
