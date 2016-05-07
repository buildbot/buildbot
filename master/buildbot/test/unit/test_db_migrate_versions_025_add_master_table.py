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

    def _createTables_thd(self, conn, metadata):
        objects = sautils.Table(
            "objects", metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column('name', sa.String(128), nullable=False),
            sa.Column('class_name', sa.String(128), nullable=False),
        )
        objects.create()

        buildrequest_claims = sautils.Table(
            'buildrequest_claims', metadata,
            sa.Column('brid', sa.Integer, index=True, unique=True),
            sa.Column('objectid', sa.Integer, index=True, nullable=True),
            sa.Column('claimed_at', sa.Integer, nullable=False),
        )
        buildrequest_claims.create()

        sa.Index('buildrequest_claims_brids', buildrequest_claims.c.brid,
                 unique=True).create()

        buildrequests = sautils.Table(
            'buildrequests', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            # ..
        )
        buildrequests.create()

    def test_empty_migration(self):
        def setup_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn
            self._createTables_thd(conn, metadata)

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            masters = sautils.Table('masters', metadata, autoload=True)
            buildrequest_claims = sautils.Table('buildrequest_claims', metadata,
                                                autoload=True)

            # both tables are empty
            res = conn.execute(masters.select())
            self.assertEqual(res.fetchall(), [])
            res = conn.execute(buildrequest_claims.select())
            self.assertEqual(res.fetchall(), [])

            # and master name is unique, so we'll get an error here
            q = masters.insert()
            self.assertRaises((sa.exc.IntegrityError,
                               sa.exc.ProgrammingError), lambda:
                              conn.execute(q,
                                           dict(
                                               name='master', active=1, last_active=0),
                                           dict(
                                               name='master', active=1, last_active=1),
                                           ))

        return self.do_test_migration(24, 25, setup_thd, verify_thd)

    def test_migration_with_data(self):
        def setup_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn
            self._createTables_thd(conn, metadata)

            q = metadata.tables['objects'].insert()
            conn.execute(q,
                         dict(id=7, name='master:/one',
                              class_name='buildbot.master.BuildMaster'),
                         dict(id=8, name='alternate_tuesdays',
                              class_name='some.scheduler.thingy'),
                         dict(id=9, name='master:/two',
                              class_name='buildbot.master.BuildMaster'),
                         )

            q = metadata.tables['buildrequests'].insert()
            conn.execute(q, *[dict(id=n) for n in xrange(20, 24)])

            q = metadata.tables['buildrequest_claims'].insert()
            conn.execute(q,
                         dict(brid=20, objectid=7, claimed_at=1349011179),
                         dict(brid=21, objectid=9, claimed_at=1349022279),
                         dict(brid=22, objectid=9, claimed_at=1349033379),
                         # tricky
                         dict(brid=23, objectid=10, claimed_at=1349444479),
                         )

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            masters = sautils.Table('masters', metadata, autoload=True)
            buildrequest_claims = sautils.Table('buildrequest_claims', metadata,
                                                autoload=True)

            # two masters (although we don't know which ids they will get)
            res = conn.execute(sa.select([masters.c.id,
                                          masters.c.name]))
            rows = res.fetchall()
            masterids = dict((row.name, row.id) for row in rows)
            self.assertEqual(sorted(masterids.keys()),
                             ['master:/one', 'master:/two'])
            mOne = masterids['master:/one']
            mTwo = masterids['master:/two']

            res = conn.execute(buildrequest_claims.select())
            self.assertEqual(
                sorted([(row.brid, row.masterid, row.claimed_at)
                        for row in res.fetchall()]), [
                    (20, mOne, 1349011179),
                    (21, mTwo, 1349022279),
                    (22, mTwo, 1349033379),
                    (23, None, 1349444479),
                ])

        return self.do_test_migration(24, 25, setup_thd, verify_thd)
