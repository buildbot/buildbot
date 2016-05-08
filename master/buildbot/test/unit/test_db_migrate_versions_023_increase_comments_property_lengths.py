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

        changes = sautils.Table(
            'changes', metadata,
            sa.Column('changeid', sa.Integer, primary_key=True),
            sa.Column('author', sa.String(256), nullable=False),
            sa.Column('comments', sa.String(1024), nullable=False),
            # old, for CVS
            sa.Column('is_dir', sa.SmallInteger, nullable=False),
            sa.Column('branch', sa.String(256)),
            sa.Column('revision', sa.String(256)),  # CVS uses NULL
            sa.Column('revlink', sa.String(256)),
            sa.Column('when_timestamp', sa.Integer, nullable=False),
            sa.Column('category', sa.String(256)),
            sa.Column('repository', sa.String(length=512), nullable=False,
                      server_default=''),
            sa.Column('codebase', sa.String(256), nullable=False,
                      server_default=sa.DefaultClause("")),
            sa.Column('project', sa.String(length=512), nullable=False,
                      server_default=''),
        )
        changes.create()

        buildsets = sautils.Table(
            'buildsets', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('external_idstring', sa.String(256)),
            sa.Column('reason', sa.String(256)),
            sa.Column('submitted_at', sa.Integer, nullable=False),
            sa.Column('complete', sa.SmallInteger, nullable=False,
                      server_default=sa.DefaultClause("0")),
            sa.Column('complete_at', sa.Integer),
            sa.Column('results', sa.SmallInteger),
            sa.Column('sourcestampsetid', sa.Integer),  # foreign key omitted
        )
        buildsets.create()

        buildset_properties = sautils.Table(
            'buildset_properties', metadata,
            sa.Column('buildsetid', sa.Integer, nullable=False),
            sa.Column('property_name', sa.String(256), nullable=False),
            sa.Column('property_value', sa.String(1024), nullable=False),
        )
        buildset_properties.create()

    # tests

    def test_update(self):
        def setup_thd(conn):
            self.create_tables_thd(conn)

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            # Verify that the columns have been upate to the Text type.
            for table, column in self.table_columns:
                tbl = sautils.Table(table, metadata, autoload=True)
                self.assertIsInstance(getattr(tbl.c, column).type, sa.Text)

        return self.do_test_migration(22, 23, setup_thd, verify_thd)
