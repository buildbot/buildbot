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

from buildbot.db.types.json import JsonObject
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

            sa.Table('builder_masters', metadata,
                     sa.Column('id', sa.Integer, primary_key=True),
                     # ..
                     ).create()
            sa.Table('masters', metadata,
                     sa.Column('id', sa.Integer, primary_key=True),
                     # ..
                     ).create()
            buildworkers = sa.Table("buildworkers", metadata,
                                   sa.Column("id", sa.Integer, primary_key=True),
                                   sa.Column("name", sa.String(256), nullable=False),
                                   sa.Column("info", JsonObject, nullable=False),
                                    )
            buildworkers.create()
            conn.execute(buildworkers.insert(), {
                'id': 29,
                'name': u'windows',
                'info': {}})

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            buildworkers = sa.Table('buildworkers',
                                   metadata, autoload=True)
            configured_buildworkers = sa.Table('configured_buildworkers',
                                              metadata, autoload=True)
            connected_buildworkers = sa.Table('connected_buildworkers',
                                             metadata, autoload=True)

            q = sa.select([buildworkers])
            self.assertEqual(map(dict, conn.execute(q).fetchall()), [
                # (the info does not get de-JSON'd due to use of autoload)
                {'id': 29, 'name': u'windows', 'info': '{}'}])

            # check that the name column was resized
            self.assertEqual(buildworkers.c.name.type.length, 50)

            q = sa.select([configured_buildworkers.c.buildermasterid,
                           configured_buildworkers.c.buildworkerid])
            self.assertEqual(conn.execute(q).fetchall(), [])

            q = sa.select([connected_buildworkers.c.masterid,
                           connected_buildworkers.c.buildworkerid])
            self.assertEqual(conn.execute(q).fetchall(), [])

        return self.do_test_migration(31, 32, setup_thd, verify_thd)
