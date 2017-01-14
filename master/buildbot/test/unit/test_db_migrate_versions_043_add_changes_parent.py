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

from __future__ import absolute_import
from __future__ import print_function

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

        patches = sautils.Table(
            'patches', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('patchlevel', sa.Integer, nullable=False),
            sa.Column('patch_base64', sa.Text, nullable=False),
            sa.Column('patch_author', sa.Text, nullable=False),
            sa.Column('patch_comment', sa.Text, nullable=False),
            sa.Column('subdir', sa.Text),
        )

        sourcestamps = sautils.Table(
            'sourcestamps', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('ss_hash', sa.String(40), nullable=False),
            sa.Column('branch', sa.String(256)),
            sa.Column('revision', sa.String(256)),
            sa.Column('patchid', sa.Integer, sa.ForeignKey('patches.id')),
            sa.Column('repository', sa.String(length=512), nullable=False,
                      server_default=''),
            sa.Column('codebase', sa.String(256), nullable=False,
                      server_default=sa.DefaultClause("")),
            sa.Column('project', sa.String(length=512), nullable=False,
                      server_default=''),
            sa.Column('created_at', sa.Integer, nullable=False),
        )

        changes = sautils.Table(
            'changes', metadata,
            sa.Column('changeid', sa.Integer, primary_key=True),
            sa.Column('author', sa.String(256), nullable=False),
            sa.Column('comments', sa.Text, nullable=False),
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
            sa.Column('sourcestampid', sa.Integer,
                      sa.ForeignKey('sourcestamps.id')),
        )
        patches.create()
        sourcestamps.create()
        changes.create()

    def test_update(self):
        def setup_thd(conn):
            self.create_tables_thd(conn)

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            changes = sautils.Table('changes', metadata, autoload=True)
            self.assertIsInstance(changes.c.parent_changeids.type, sa.Integer)

        return self.do_test_migration(42, 43, setup_thd, verify_thd)
