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
    PREVIOUS_NULLABLE = True

    def setUp(self):
        return self.setUpMigrateTest()

    def tearDown(self):
        return self.tearDownMigrateTest()

    def create_tables_thd(self, conn):
        metadata = sa.MetaData()
        metadata.bind = conn

        sourcestamps = sautils.Table(
            'sourcestamps', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
        )
        sourcestamps.create()

        changes = sautils.Table(
            'changes', metadata,
            sa.Column('changeid', sa.Integer, primary_key=True),
            sa.Column('author', sa.String(255), nullable=False),
            sa.Column('committer', sa.String(255), nullable=self.PREVIOUS_NULLABLE),
            sa.Column('comments', sa.Text, nullable=False),
            sa.Column('branch', sa.String(255)),
            sa.Column('revision', sa.String(255)),
            sa.Column('revlink', sa.String(256)),
            sa.Column('when_timestamp', sa.Integer, nullable=False),
            sa.Column('category', sa.String(255)),
            sa.Column('repository', sa.String(length=512), nullable=False,
                      server_default=''),
            sa.Column('codebase', sa.String(256), nullable=False,
                      server_default=sa.DefaultClause("")),
            sa.Column('project', sa.String(length=512), nullable=False,
                      server_default=''),
            sa.Column('sourcestampid', sa.Integer,
                      sa.ForeignKey('sourcestamps.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('parent_changeids', sa.Integer,
                      sa.ForeignKey('changes.changeid', ondelete='SET NULL'),
                      nullable=True),
        )
        changes.create()

    def test_update(self):
        def setup_thd(conn):
            self.create_tables_thd(conn)

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            changes = sautils.Table('changes', metadata, autoload=True)
            self.assertIsInstance(changes.c.committer.type, sa.String)
            self.assertTrue(changes.c.committer.nullable)
        return self.do_test_migration(54, 55, setup_thd, verify_thd)


class MigrationNotNullable(Migration):
    # same test, but in the case the column was previously non nullable (2.4.0 fresh install case)
    PREVIOUS_NULLABLE = False
