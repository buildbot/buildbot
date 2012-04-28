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
from sqlalchemy.engine import reflection
from twisted.python import log
from twisted.trial import unittest
from buildbot.test.util import migration

class Migration(migration.MigrateTestMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpMigrateTest()

    def tearDown(self):
        return self.tearDownMigrateTest()

    # create tables as they are before migrating to version 023
    def create_tables_thd(self, conn):
        metadata = sa.MetaData()
        metadata.bind = conn

        self.changes = sa.Table('changes', metadata,
            sa.Column('changeid', sa.Integer, primary_key=True),
            sa.Column('author', sa.String(256), nullable=False),
            sa.Column('comments', sa.String(1024), nullable=False),
            sa.Column('is_dir', sa.SmallInteger, nullable=False),
            sa.Column('branch', sa.String(256)),
            sa.Column('revision', sa.String(256)),
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
        self.changes.create(bind=conn)

    # tests

    def test_added_tags_tbl(self):
        def setup_thd(conn):
            self.create_tables_thd(conn)

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            # Verify that we have a new table 'tags'.
            tbl = sa.Table('tags', metadata, autoload=True)
            self.assertTrue(hasattr(tbl.c, 'id'))

        return self.do_test_migration(22, 23, setup_thd, verify_thd)

    def test_added_change_tags_tbl(self):
        def setup_thd(conn):
            self.create_tables_thd(conn)

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            # Verify that we have a new table 'change_tags'.
            tbl = sa.Table('change_tags', metadata, autoload=True)
            self.assertTrue(hasattr(tbl.c, 'changeid'))

        return self.do_test_migration(22, 23, setup_thd, verify_thd)

    def test_tags_indexes(self):
        def setup_thd(conn):
            self.create_tables_thd(conn)

        def verify_thd(conn):
            # Do we need to check DB engine dialect here?
            insp = reflection.Inspector.from_engine(conn)
            indexes = insp.get_indexes('tags')
            self.assertEqual(
                sorted([ i['name'] for i in indexes ]),
                sorted([
                    'tags_tag',
                ]))

        return self.do_test_migration(22, 23, setup_thd, verify_thd)

    def test_change_tags_indexes(self):
        def setup_thd(conn):
            self.create_tables_thd(conn)

        def verify_thd(conn):
            # Do we need to check DB engine dialect here?
            insp = reflection.Inspector.from_engine(conn)
            indexes = insp.get_indexes('change_tags')
            self.assertEqual(
                sorted([ i['name'] for i in indexes ]),
                sorted([
                    'change_tags_tagid',
                ]))

        return self.do_test_migration(22, 23, setup_thd, verify_thd)
