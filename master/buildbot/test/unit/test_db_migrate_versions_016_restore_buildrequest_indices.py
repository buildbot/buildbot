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

        self.buildrequests = sautils.Table(
            'buildrequests', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('buildsetid', sa.Integer,  # foreign key removed
                      nullable=False),
            sa.Column('buildername', sa.String(length=256), nullable=False),
            sa.Column('priority', sa.Integer, nullable=False,
                      server_default=sa.DefaultClause("0")),
            sa.Column('complete', sa.Integer,
                      server_default=sa.DefaultClause("0")),
            sa.Column('results', sa.SmallInteger),
            sa.Column('submitted_at', sa.Integer, nullable=False),
            sa.Column('complete_at', sa.Integer),
        )
        self.buildrequests.create(bind=conn)

        # these indices should already exist everywhere but on sqlite
        if conn.dialect.name != 'sqlite':
            idx = sa.Index('buildrequests_buildsetid',
                           self.buildrequests.c.buildsetid)
            idx.create()

            idx = sa.Index('buildrequests_buildername',
                           self.buildrequests.c.buildername)
            idx.create()

            idx = sa.Index('buildrequests_complete',
                           self.buildrequests.c.complete)
            idx.create()

    # tests

    def test_migrate(self):
        def setup_thd(conn):
            self.create_tables_thd(conn)

        def verify_thd(conn):
            insp = reflection.Inspector.from_engine(conn)
            indexes = insp.get_indexes('buildrequests')
            self.assertEqual(
                sorted([i['name'] for i in indexes]),
                sorted([
                    'buildrequests_buildername',
                    'buildrequests_buildsetid',
                    'buildrequests_complete',
                ]))

        return self.do_test_migration(15, 16, setup_thd, verify_thd)
