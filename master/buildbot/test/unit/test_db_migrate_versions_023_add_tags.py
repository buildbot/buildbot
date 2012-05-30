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
import datetime
from buildbot.util import UTC, datetime2epoch

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

        idx = sa.Index('changes_category', self.changes.c.category)
        idx.create(bind=conn)

    def reload_tables_after_migration(self, conn):
        metadata = sa.MetaData()
        metadata.bind = conn
        self.changes = sa.Table('changes', metadata, autoload=True)
        self.tags = sa.Table('tags', metadata, autoload=True)
        self.change_tags = sa.Table('change_tags', metadata, autoload=True)

    # Populate test data to the changes table as before migration to 023.
    def populate_changes(self, conn, changes):
        dt_when = datetime.datetime(2012, 2, 19, 12, 31, 15, tzinfo=UTC)

        for changeid, category in changes:
            conn.execute(self.changes.insert(),
                    changeid = changeid,
                    author = 'develop',
                    comments = 'no comment',
                    is_dir = 0,
                    branch = 'default',
                    revision = 'FD56A89',
                    when_timestamp = datetime2epoch(dt_when),
                    category = category,
                    repository = 'https://svn.com/repo_a',
                    codebase = 'repo_a',
                    project = '')

    # Data model migration tests.

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

    # Validate data migration.
    def do_test_migrated_data(self, conn, tags, change_tags):
        # Check tags records.
        res = conn.execute(sa.select([self.tags.c.id, self.tags.c.tag]))
        got_tags = res.fetchall()
        self.assertEqual(got_tags, tags)

        # Check change_tags records.
        res = conn.execute(sa.select([
                                  self.change_tags.c.changeid,
                                  self.change_tags.c.tagid]))
        got_change_tags = res.fetchall()
        self.assertEqual(got_change_tags, change_tags)

    # Data migration tests.

    def test_migrated_data_unique_tags(self):
        changes = [
            (1, 'category1'),
            (2, 'category2'),
            (3, 'category3'), ]
        tags = [
            (1, 'category1'),
            (2, 'category2'),
            (3, 'category3'), ]
        change_tags = [
            (1, 1),
            (2, 2),
            (3, 3), ]

        def setup_thd(conn):
            self.create_tables_thd(conn)
            self.populate_changes(conn, changes)

        def verify_thd(conn):
            self.reload_tables_after_migration(conn)
            self.do_test_migrated_data(conn, tags, change_tags)

        return self.do_test_migration(22, 23, setup_thd, verify_thd)

    def test_migrated_data_no_categories(self):
        changes = [
            (1, None),
            (2, None),
            (3, None), ]
        tags = []
        change_tags = []

        def setup_thd(conn):
            self.create_tables_thd(conn)
            self.populate_changes(conn, changes)

        def verify_thd(conn):
            self.reload_tables_after_migration(conn)
            self.do_test_migrated_data(conn, tags, change_tags)
            
        return self.do_test_migration(22, 23, setup_thd, verify_thd)

    def test_migrated_data_not_unique_tags(self):
        changes = [
            (1, 'category1'),
            (2, 'category2'),
            (3, 'category3'),
            (4,  None      ),
            (11, 'category1'),
            (12, 'category2'),
            (22, 'category2'),
            (13, 'category3'),
            (23, 'category3'),
            (33, 'category3'), ]
        tags = [
            (1, 'category1'),
            (2, 'category2'),
            (3, 'category3'), ]
        change_tags = [
            ( 1, 1),
            ( 2, 2),
            ( 3, 3),
            (11, 1),
            (12, 2),
            (13, 3),
            (22, 2),
            (23, 3),
            (33, 3), ]

        def setup_thd(conn):
            self.create_tables_thd(conn)
            self.populate_changes(conn, changes)

        def verify_thd(conn):
            self.reload_tables_after_migration(conn)
            self.do_test_migrated_data(conn, tags, change_tags)

        return self.do_test_migration(22, 23, setup_thd, verify_thd)
