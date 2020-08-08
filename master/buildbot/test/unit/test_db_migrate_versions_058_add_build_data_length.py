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

            builds = sautils.Table(
                'builds', metadata,
                sa.Column('id', sa.Integer, primary_key=True),
                # ...
            )
            builds.create()

            build_data = sautils.Table(
                'build_data', metadata,
                sa.Column('id', sa.Integer, primary_key=True),
                sa.Column('buildid', sa.Integer,
                          sa.ForeignKey('builds.id', ondelete='CASCADE'),
                          nullable=False),
                sa.Column('name', sa.String(256), nullable=False),
                sa.Column('value', sa.LargeBinary().with_variant(sa.dialects.mysql.LONGBLOB,
                                                                 "mysql"),
                          nullable=False),
                sa.Column('source', sa.String(256), nullable=False),
            )
            build_data.create()

            conn.execute(builds.insert(), [{'id': 3}])
            conn.execute(build_data.insert(), [
                {'id': 15, 'buildid': 3, 'name': 'name1',
                 'value': b'value1', 'source': 'source1'}])

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            build_data = sautils.Table('build_data', metadata, autoload=True)

            q = sa.select([
                build_data.c.buildid,
                build_data.c.name,
                build_data.c.value,
                build_data.c.length,
                build_data.c.source,
            ])
            # build_data without the 'length' column has never been released, so we don't care about
            # correct values there.
            self.assertEqual(conn.execute(q).fetchall(), [
                (3, 'name1', b'value1', 0, 'source1')
            ])

        return self.do_test_migration(57, 58, setup_thd, verify_thd)
