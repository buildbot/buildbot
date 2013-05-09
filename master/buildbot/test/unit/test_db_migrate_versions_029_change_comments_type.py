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

from twisted.trial import unittest
from buildbot.test.util import migration
import sqlalchemy as sa
from sqlalchemy.engine import reflection

class Migration(migration.MigrateTestMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpMigrateTest()

    def tearDown(self):
        return self.tearDownMigrateTest()

    def create_tables_thd(self, conn):
        metadata = sa.MetaData()
        metadata.bind = conn

        self.changes = sa.Table('changes', metadata,
            sa.Column('changeid', sa.Integer,  primary_key=True),
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
            sa.Column('sourcestampid', sa.Integer,
              sa.ForeignKey('sourcestamps.id'))
        )
        self.changes.create(bind=conn)

        idx = sa.Index('changeid',
                self.changes.c.changeid)
        idx.create()

    # tests

    def test_migrate(self):
        def setup_thd(conn):
            self.create_tables_thd(conn)

        def verify_thd(conn):
            # regression test for bug #2158; this is known to be broken on
            # sqlite (and fixed in db version 016) but expected to work on
            # other engines.
            if conn.dialect.name != 'sqlite':
                insp = reflection.Inspector.from_engine(conn)
                indexes = insp.get_indexes('changes')
                self.assertEqual(
                    sorted([ i['name'] for i in indexes ]),
                    sorted([
                        'buildrequests_buildername',
                        'buildrequests_buildsetid',
                        'buildrequests_complete',
                    ]))

        return self.do_test_migration(28, 29, setup_thd, verify_thd)
