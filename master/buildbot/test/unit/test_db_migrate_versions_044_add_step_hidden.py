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

        steps = sautils.Table(
            'steps', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('number', sa.Integer, nullable=False),
            sa.Column('name', sa.String(50), nullable=False),
            sa.Column('buildid', sa.Integer),
            sa.Column('started_at', sa.Integer),
            sa.Column('complete_at', sa.Integer),
            sa.Column(
                'state_string', sa.Text, nullable=False),
            sa.Column('results', sa.Integer),
            sa.Column('urls_json', sa.Text, nullable=False),
        )
        steps.create()

        conn.execute(steps.insert(), [
            dict(number=3, name='echo', urls_json='[]', state_string='')])

    def test_update(self):
        def setup_thd(conn):
            self.create_tables_thd(conn)

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            steps = sautils.Table('steps', metadata, autoload=True)
            self.assertIsInstance(steps.c.hidden.type, sa.SmallInteger)

            q = sa.select([steps.c.name, steps.c.hidden])
            num_rows = 0
            for row in conn.execute(q):
                # verify that the default value was set correctly
                self.assertEqual(row.hidden, 0)
                num_rows += 1
            self.assertEqual(num_rows, 1)

        return self.do_test_migration(43, 44, setup_thd, verify_thd)
