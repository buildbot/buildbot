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
        )
        builds.create()

        buildsets = sautils.Table(
            'buildsets', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('external_idstring', sa.String(256)),
            sa.Column('reason', sa.String(256)),
            sa.Column('submitted_at', sa.Integer, nullable=False),
            sa.Column('revision', sa.String(255)),
            sa.Column('complete', sa.SmallInteger, nullable=False,
                      server_default=sa.DefaultClause("0")),
            sa.Column('complete_at', sa.Integer),
            sa.Column('results', sa.SmallInteger),
            sa.Column('parent_buildid', sa.Integer,
                      sa.ForeignKey('builds.id', use_alter=True,
                      name='parent_buildid', ondelete='SET NULL'),
                      nullable=True),
            sa.Column('parent_relationship', sa.Text),
        )
        buildsets.create()

        conn.execute(builds.insert(), [
            dict(id=100),
        ])

        conn.execute(buildsets.insert(), [
            dict(
                id=1,
                submitted_at=1565182914,
                complete=1,
                complete_at=1565182925,
                results=0),
        ])

    def test_update(self):
        def setup_thd(conn):
            self.create_tables_thd(conn)

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            buildsets = sautils.Table('buildsets', metadata, autoload=True)
            self.assertIsInstance(buildsets.c.pipeline_id.type, sa.Integer)

        return self.do_test_migration(55, 56, setup_thd, verify_thd)
