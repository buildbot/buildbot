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

import hashlib

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

        builders = sautils.Table(
            'builders',
            metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('name', sa.Text, nullable=False),
            sa.Column('description', sa.Text, nullable=True),
            sa.Column('projectid', sa.Integer, nullable=True),
            sa.Column('name_hash', sa.String(40), nullable=False),
        )
        builders.create()

        conn.execute(
            builders.insert(),
            [
                {
                    "id": 3,
                    "name": "foo",
                    "description": "foo_description",
                    "projectid": None,
                    "name_hash": hashlib.sha1(b'foo').hexdigest(),
                }
            ],
        )

    def test_update(self):
        def setup_thd(conn):
            self.create_tables_thd(conn)

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            builders = sautils.Table('builders', metadata, autoload=True)
            self.assertIsInstance(builders.c.description_format.type, sa.Text)
            self.assertIsInstance(builders.c.description_html.type, sa.Text)

            q = sa.select([
                builders.c.name,
                builders.c.description_format,
                builders.c.description_html,
            ])

            num_rows = 0
            for row in conn.execute(q):
                self.assertIsNone(row.description_format)
                self.assertIsNone(row.description_html)
                num_rows += 1
            self.assertEqual(num_rows, 1)

        return self.do_test_migration('060', '061', setup_thd, verify_thd)
