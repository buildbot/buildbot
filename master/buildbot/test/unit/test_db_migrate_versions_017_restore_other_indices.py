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

        self.changes = sautils.Table(
            'changes', metadata,
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
            sa.Column('project', sa.String(length=512), nullable=False,
                      server_default=''),
        )
        self.changes.create(bind=conn)

        self.schedulers = sautils.Table(
            "schedulers", metadata,
            sa.Column('schedulerid', sa.Integer, primary_key=True),
            sa.Column('name', sa.String(128), nullable=False),
            sa.Column('class_name', sa.String(128), nullable=False),
        )
        self.schedulers.create(bind=conn)

        self.users = sautils.Table(
            "users", metadata,
            sa.Column("uid", sa.Integer, primary_key=True),
            sa.Column("identifier", sa.String(256), nullable=False),
            sa.Column("bb_username", sa.String(128)),
            sa.Column("bb_password", sa.String(128)),
        )
        self.users.create(bind=conn)

        self.objects = sautils.Table(
            "objects", metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column('name', sa.String(128), nullable=False),
            sa.Column('class_name', sa.String(128), nullable=False),
        )
        self.objects.create()

        self.object_state = sautils.Table(
            "object_state", metadata,
            sa.Column("objectid", sa.Integer, sa.ForeignKey('objects.id'),
                      nullable=False),
            sa.Column("name", sa.String(length=256), nullable=False),
            sa.Column("value_json", sa.Text, nullable=False),
        )
        self.object_state.create()

        # these indices should already exist everywhere but on sqlite
        if conn.dialect.name != 'sqlite':
            sa.Index('name_and_class', self.schedulers.c.name,
                     self.schedulers.c.class_name).create()
            sa.Index('changes_branch', self.changes.c.branch).create()
            sa.Index('changes_revision', self.changes.c.revision).create()
            sa.Index('changes_author', self.changes.c.author).create()
            sa.Index('changes_category', self.changes.c.category).create()
            sa.Index('changes_when_timestamp',
                     self.changes.c.when_timestamp).create()

        # create this index without the unique attribute
        sa.Index('users_identifier', self.users.c.identifier).create()

    # tests

    def test_migrate(self):
        def setup_thd(conn):
            self.create_tables_thd(conn)

        def verify_thd(conn):
            insp = reflection.Inspector.from_engine(conn)
            indexes = (
                insp.get_indexes('changes') + insp.get_indexes('schedulers'))
            self.assertEqual(
                sorted([i['name'] for i in indexes]),
                sorted([
                    'changes_author',
                    'changes_branch',
                    'changes_category',
                    'changes_revision',
                    'changes_when_timestamp',
                    'name_and_class',
                ]))
            indexes = insp.get_indexes('users')
            for idx in indexes:
                if idx['name'] == 'users_identifier':
                    self.assertTrue(idx['unique'])
                    break
            else:
                self.fail("no users_identifier index")

        return self.do_test_migration(16, 17, setup_thd, verify_thd)
