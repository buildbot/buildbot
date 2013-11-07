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
            buildslaves = sa.Table("buildslaves", metadata,
                                   sa.Column("id", sa.Integer, primary_key=True),
                                   sa.Column("name", sa.String(256), nullable=False),
                                   sa.Column("info", JsonObject, nullable=False),
                                   )
            buildslaves.create()
            conn.execute(buildslaves.insert(), {
                'id': 29,
                'name': u'windows',
                'info': {}})

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            buildslaves = sa.Table('buildslaves',
                                   metadata, autoload=True)
            configured_buildslaves = sa.Table('configured_buildslaves',
                                              metadata, autoload=True)
            connected_buildslaves = sa.Table('connected_buildslaves',
                                             metadata, autoload=True)

            q = sa.select([buildslaves])
            self.assertEqual(map(dict, conn.execute(q).fetchall()), [
                # (the info does not get de-JSON'd due to use of autoload)
                {'id': 29, 'name': u'windows', 'info': '{}'}])

            # check that the name column was resized
            self.assertEqual(buildslaves.c.name.type.length, 50)

            q = sa.select([configured_buildslaves.c.buildermasterid,
                           configured_buildslaves.c.buildslaveid])
            self.assertEqual(conn.execute(q).fetchall(), [])

            q = sa.select([connected_buildslaves.c.masterid,
                           connected_buildslaves.c.buildslaveid])
            self.assertEqual(conn.execute(q).fetchall(), [])

        return self.do_test_migration(31, 32, setup_thd, verify_thd)
