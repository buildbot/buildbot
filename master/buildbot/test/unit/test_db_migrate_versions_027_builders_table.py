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
            sautils.Table(
                'masters', metadata,
                sa.Column('id', sa.Integer, primary_key=True),
                # ..
            ).create()

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            builders = sautils.Table('builders', metadata, autoload=True)
            builder_masters = sautils.Table('builder_masters', metadata,
                                            autoload=True)

            q = sa.select([builders.c.id, builders.c.name,
                           builders.c.name_hash])
            self.assertEqual(conn.execute(q).fetchall(), [])

            q = sa.select([builder_masters.c.builderid,
                           builder_masters.c.masterid])
            self.assertEqual(conn.execute(q).fetchall(), [])

        return self.do_test_migration(26, 27, setup_thd, verify_thd)
