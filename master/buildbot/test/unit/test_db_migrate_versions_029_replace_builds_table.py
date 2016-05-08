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
            )
            buildrequests.create()

            builders = sautils.Table(
                'builders', metadata,
                sa.Column('id', sa.Integer, primary_key=True),
            )
            builders.create()

            masters = sautils.Table(
                "masters", metadata,
                sa.Column('id', sa.Integer, primary_key=True),
            )
            masters.create()

            builds = sautils.Table(
                'builds', metadata,
                sa.Column('id', sa.Integer, primary_key=True),
                sa.Column('number', sa.Integer, nullable=False),
                sa.Column('brid', sa.Integer, sa.ForeignKey('buildrequests.id'),
                          nullable=False),
                sa.Column('start_time', sa.Integer, nullable=False),
                sa.Column('finish_time', sa.Integer),
            )
            builds.create()

        def verify_thd(conn):
            r = conn.execute("select * from builds")
            self.assertEqual(r.fetchall(), [])

        return self.do_test_migration(28, 29, setup_thd, verify_thd)
