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

    def test_migration(self):
        def setup_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            buildrequests = sautils.Table(
                'buildrequests', metadata,
                sa.Column('id', sa.Integer, primary_key=True),
                sa.Column('buildsetid', sa.Integer, nullable=False),
                sa.Column('buildername', sa.String(length=256),
                          nullable=False),
                sa.Column('priority', sa.Integer, nullable=False,
                          server_default=sa.DefaultClause("0")),
                sa.Column('complete', sa.Integer,
                          server_default=sa.DefaultClause("0")),
                sa.Column('results', sa.SmallInteger),
                sa.Column('submitted_at', sa.Integer, nullable=False),
                sa.Column('complete_at', sa.Integer),
            )
            buildrequests.create()

            conn.execute(buildrequests.insert(), [
                {'id': 101, 'buildsetid': 13, 'buildername': 'bld',
                 'priority': 10, 'complete': 0, 'submitted_at': 1234},
            ])

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            buildrequests = sautils.Table(
                'buildrequests', metadata, autoload=True)
            q = sa.select([buildrequests.c.waited_for])
            for row in conn.execute(q):
                # verify that the default value was set correctly
                self.assertEqual(row.waited_for, 0)

        return self.do_test_migration(32, 33, setup_thd, verify_thd)
