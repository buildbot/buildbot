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
from sqlalchemy.engine import reflection
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

        self.buildsets = sautils.Table(
            'buildsets', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('external_idstring', sa.String(256)),
            sa.Column('reason', sa.String(256)),
            sa.Column('sourcestampid', sa.Integer,
                      nullable=False),  # NOTE: foreign key omitted
            sa.Column('submitted_at', sa.Integer, nullable=False),
            sa.Column('complete', sa.SmallInteger, nullable=False,
                      server_default=sa.DefaultClause("0")),
            sa.Column('complete_at', sa.Integer),
            sa.Column('results', sa.SmallInteger),
        )
        self.buildsets.create(bind=conn)

        self.buildrequests = sautils.Table(
            'buildrequests', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('buildsetid', sa.Integer, sa.ForeignKey("buildsets.id"),
                      nullable=False),
            sa.Column('buildername', sa.String(length=256), nullable=False),
            sa.Column('priority', sa.Integer, nullable=False,
                      server_default=sa.DefaultClause("0")),
            sa.Column('claimed_at', sa.Integer,
                      server_default=sa.DefaultClause("0")),
            sa.Column('claimed_by_name', sa.String(length=256)),
            sa.Column('claimed_by_incarnation', sa.String(length=256)),
            sa.Column('complete', sa.Integer,
                      server_default=sa.DefaultClause("0")),
            sa.Column('results', sa.SmallInteger),
            sa.Column('submitted_at', sa.Integer, nullable=False),
            sa.Column('complete_at', sa.Integer),
        )
        self.buildrequests.create(bind=conn)

        idx = sa.Index('buildrequests_buildsetid',
                       self.buildrequests.c.buildsetid)
        idx.create()

        idx = sa.Index('buildrequests_buildername',
                       self.buildrequests.c.buildername)
        idx.create()

        idx = sa.Index('buildrequests_complete',
                       self.buildrequests.c.complete)
        idx.create()

        self.objects = sautils.Table(
            "objects", metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column('name', sa.String(128), nullable=False),
            sa.Column('class_name', sa.String(128), nullable=False),
            sa.UniqueConstraint('name', 'class_name', name='object_identity'),
        )
        self.objects.create(bind=conn)

    # tests

    def test_migrate(self):
        def setup_thd(conn):
            self.create_tables_thd(conn)

        def verify_thd(conn):
            # regression test for bug #2158; this is known to be broken on
            # sqlite (and fixed in db version 016) but expected to work on
            # other engines.
            if conn.dialect.name != 'sqlite':
                insp = reflection.Inspector.from_engine(conn)
                indexes = insp.get_indexes('buildrequests')
                self.assertEqual(
                    sorted([i['name'] for i in indexes]),
                    sorted([
                        'buildrequests_buildername',
                        'buildrequests_buildsetid',
                        'buildrequests_complete',
                    ]))

        return self.do_test_migration(10, 11, setup_thd, verify_thd)
