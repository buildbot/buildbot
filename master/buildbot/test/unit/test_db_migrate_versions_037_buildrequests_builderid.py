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

            builders = sautils.Table(
                'builders', metadata,
                sa.Column('id', sa.Integer, primary_key=True),
                sa.Column('name', sa.Text, nullable=False),
                sa.Column('name_hash', sa.String(40), nullable=False),
            )
            builders.create()

            buildsets = sautils.Table(
                'buildsets', metadata,
                sa.Column('id', sa.Integer, primary_key=True),
                sa.Column('external_idstring', sa.String(256)),
                sa.Column('reason', sa.String(256)),
                sa.Column('submitted_at', sa.Integer, nullable=False),
                sa.Column('complete', sa.SmallInteger, nullable=False,
                          server_default=sa.DefaultClause("0")),
                sa.Column('complete_at', sa.Integer),
                sa.Column('results', sa.SmallInteger),
                sa.Column('parent_buildid', sa.Integer),
                sa.Column('parent_relationship', sa.Text),
            )
            buildsets.create()

            buildrequests = sautils.Table(
                'buildrequests', metadata,
                sa.Column('id', sa.Integer, primary_key=True),
                sa.Column('buildsetid', sa.Integer,
                          sa.ForeignKey("buildsets.id"), nullable=False),
                sa.Column('buildername', sa.String(length=256),
                          nullable=False),
                sa.Column('priority', sa.Integer, nullable=False,
                          server_default=sa.DefaultClause("0")),
                sa.Column('complete', sa.Integer,
                          server_default=sa.DefaultClause("0")),
                sa.Column('results', sa.SmallInteger),
                sa.Column('submitted_at', sa.Integer, nullable=False),
                sa.Column('complete_at', sa.Integer),
                sa.Column('waited_for', sa.SmallInteger,
                          server_default=sa.DefaultClause("0")),
            )
            buildrequests.create()

            idx = sa.Index('buildrequests_buildsetid',
                           buildrequests.c.buildsetid)
            idx.create()
            idx = sa.Index('buildrequests_buildername',
                           buildrequests.c.buildername)
            idx.create()
            idx = sa.Index('buildrequests_complete', buildrequests.c.complete)
            idx.create()
            idx = sa.Index('buildsets_complete', buildsets.c.complete)
            idx.create()
            idx = sa.Index('buildsets_submitted_at', buildsets.c.submitted_at)
            idx.create()

            brargs = dict(buildsetid=10, priority=1, submitted_at=1234)
            conn.execute(buildsets.insert(), id=10, submitted_at=1233)
            conn.execute(builders.insert(), id=20, name='bldr1',
                         name_hash='88103b2fbeb05bdd81c066b58a11bcf9b0d29300')
            conn.execute(buildrequests.insert(),
                         id=30, buildername='bldr1', **brargs)
            conn.execute(buildrequests.insert(),
                         id=31, buildername='bldr1', **brargs)
            conn.execute(buildrequests.insert(),
                         id=32, buildername='bldr2', **brargs)
            self.assertTrue(hasattr(buildrequests.c, 'buildername'))
            self.assertFalse(hasattr(buildrequests.c, 'builderid'))

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            buildrequests = sautils.Table(
                'buildrequests', metadata, autoload=True)
            builders = sautils.Table('builders', metadata, autoload=True)

            self.assertFalse(hasattr(buildrequests.c, 'buildername'))
            self.assertTrue(hasattr(buildrequests.c, 'builderid'))

            self.assertEqual(
                sorted([i.name for i in buildrequests.indexes]), [
                    'buildrequests_builderid',
                    'buildrequests_buildsetid',
                    'buildrequests_complete',
                ])

            # get the new builderid
            bldr2_id = conn.execute(
                sa.select(
                    [builders.c.id],
                    whereclause=(builders.c.name == 'bldr2'))).first()[0]
            res = conn.execute(
                sa.select([buildrequests.c.id, buildrequests.c.builderid]))
            self.assertEqual(sorted(map(tuple, res)),
                             [(30, 20), (31, 20), (32, bldr2_id)])

        return self.do_test_migration(36, 37, setup_thd, verify_thd)
