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

import datetime

from buildbot.test.util import migration
from twisted.trial import unittest


class Migration(migration.MigrateTestMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpMigrateTest()

    def tearDown(self):
        return self.tearDownMigrateTest()

    def test_migration(self):
        def setup_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            buildsets = sa.Table('buildsets', metadata,
                                 sa.Column('id', sa.Integer, primary_key=True),
                                 sa.Column('external_idstring', sa.String(256)),
                                 sa.Column('reason', sa.String(256)),
                                 sa.Column('submitted_at', sa.Integer, nullable=False),
                                 sa.Column('complete', sa.SmallInteger, nullable=False,
                                           server_default=sa.DefaultClause("0")),
                                 sa.Column('complete_at', sa.Integer),
                                 sa.Column('results', sa.SmallInteger),
                                 )

            buildsets.create()

            conn.execute(buildsets.insert(), [
                dict(external_idstring='extid', reason='rsn1', sourcestamps=[91],
                     submitted_at=datetime.datetime(1978, 6, 15, 12, 31, 15),
                     complete_at=datetime.datetime(1979, 6, 15, 12, 31, 15),
                     complete=False, results=-1, bsid=91)
            ])

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            buildsets = sa.Table('buildsets', metadata, autoload=True)
            q = sa.select([buildsets.c.parent_buildid, buildsets.c.parent_relationship])
            num_rows = 0
            for row in conn.execute(q):
                # verify that the default value was set correctly
                self.assertEqual(row.parent_buildid, None)
                self.assertEqual(row.parent_relationship, None)
                num_rows += 1
            self.assertEqual(num_rows, 1)

        return self.do_test_migration(35, 36, setup_thd, verify_thd)
