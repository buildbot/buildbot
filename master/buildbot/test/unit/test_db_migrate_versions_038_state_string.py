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

    def setUp(self):
        return self.setUpMigrateTest()

    def tearDown(self):
        return self.tearDownMigrateTest()

    def create_tables_thd(self, conn):
        metadata = sa.MetaData()
        metadata.bind = conn

        builds = sautils.Table(
            'builds', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('number', sa.Integer, nullable=False),
            sa.Column('builderid', sa.Integer),
            sa.Column('buildrequestid', sa.Integer, nullable=False),
            sa.Column('buildslaveid', sa.Integer),
            sa.Column('masterid', sa.Integer, nullable=False),
            sa.Column('started_at', sa.Integer, nullable=False),
            sa.Column('complete_at', sa.Integer),
            sa.Column('state_strings_json', sa.Text, nullable=False),
            sa.Column('results', sa.Integer),
        )
        builds.create()

        steps = sautils.Table(
            'steps', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('number', sa.Integer, nullable=False),
            sa.Column('name', sa.String(50), nullable=False),
            sa.Column('buildid', sa.Integer, sa.ForeignKey('builds.id')),
            sa.Column('started_at', sa.Integer),
            sa.Column('complete_at', sa.Integer),
            sa.Column('state_strings_json', sa.Text, nullable=False),
            sa.Column('results', sa.Integer),
            sa.Column('urls_json', sa.Text, nullable=False),
        )
        steps.create()

    # tests

    def test_update(self):
        def setup_thd(conn):
            self.create_tables_thd(conn)

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            steps = sautils.Table('steps', metadata, autoload=True)
            self.failIf(hasattr(steps.c, 'state_strings_json'))
            self.failUnless(hasattr(steps.c, 'state_string'))
            self.assertIsInstance(steps.c.state_string.type, sa.Text)

            builds = sautils.Table('builds', metadata, autoload=True)
            self.failIf(hasattr(builds.c, 'state_strings_json'))
            self.failUnless(hasattr(builds.c, 'state_string'))
            self.assertIsInstance(builds.c.state_string.type, sa.Text)

        return self.do_test_migration(37, 38, setup_thd, verify_thd)
