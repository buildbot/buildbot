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

import datetime
from twisted.trial import unittest
from buildbot.test.util import migration
import sqlalchemy as sa
from sqlalchemy.engine import reflection
from buildbot.util import UTC

class Migration(migration.MigrateTestMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpMigrateTest()

    def tearDown(self):
        return self.tearDownMigrateTest()

    def create_tables_thd(self, conn):
        metadata = sa.MetaData()
        metadata.bind = conn

        self.buildsets = sa.Table('buildsets', metadata,
            sa.Column('id', sa.Integer,  primary_key=True),
            sa.Column('external_idstring', sa.String(256)),
            sa.Column('reason', sa.String(256)),
            sa.Column('sourcestampid', sa.Integer,
                nullable=False), # NOTE: foreign key omitted
            sa.Column('submitted_at', sa.Integer, nullable=False),
            sa.Column('complete', sa.SmallInteger, nullable=False,
                server_default=sa.DefaultClause("0")),
            sa.Column('complete_at', sa.Integer),
            sa.Column('results', sa.SmallInteger),
        )
        self.buildsets.create(bind=conn)
        sa.Index('buildsets_complete', self.buildsets.c.complete)
        sa.Index('buildsets_submitted_at', self.buildsets.c.submitted_at)

        self.patches = sa.Table('patches', metadata,
            sa.Column('id', sa.Integer,  primary_key=True),
            sa.Column('patchlevel', sa.Integer, nullable=False),
            sa.Column('patch_base64', sa.Text, nullable=False),
            sa.Column('patch_author', sa.Text, nullable=False),
            sa.Column('patch_comment', sa.Text, nullable=False),
            sa.Column('subdir', sa.Text),
        )
        self.patches.create(bind=conn)

        self.sourcestamps = sa.Table('sourcestamps', metadata,
            sa.Column('id', sa.Integer,  primary_key=True),
            sa.Column('branch', sa.String(256)),
            sa.Column('revision', sa.String(256)),
            sa.Column('patchid', sa.Integer, sa.ForeignKey('patches.id')),
            sa.Column('repository', sa.String(length=512), nullable=False, server_default=''),
            sa.Column('project', sa.String(length=512), nullable=False, server_default=''),
            sa.Column('sourcestampid', sa.Integer, sa.ForeignKey('sourcestamps.id')),
        )
        self.sourcestamps.create(bind=conn)

    def fill_tables_with_testdata(self, conn, testdata):
        for bsid, ssid in testdata:
            self.insert_buildset_sourcestamp(conn, bsid, ssid)

    def insert_buildset_sourcestamp(self, conn, bsid, sourcestampid):
        conn.execute(self.buildsets.insert(),
                id=bsid,
                externalid_string='',
                reason = 'just',
                sourcestampid=sourcestampid,
                submitted_at = datetime.datetime(1969, 4, 16, 12, 00, 00, tzinfo=UTC),
                complete = 0,
                complete_at = datetime.datetime(1969, 4, 16, 13, 00, 00, tzinfo=UTC),
                results=0)
        conn.execute(self.sourcestamps.insert(),
                id=sourcestampid,
                branch='this_branch',
                revision='this_revision',
                patchid = None,
                repository='repo_a',
                project='')

    def assertBuildsetSourceStamp_thd(self, conn, exp_buildsets=[],
                            exp_sourcestamps=[]):
        metadata = sa.MetaData()
        metadata.bind = conn
        tbl = sa.Table('buildsets', metadata, autoload=True)
        res = conn.execute(sa.select([tbl.c.id, tbl.c.sourcestampsetid], order_by=tbl.c.id))
        got_buildsets = res.fetchall()

        tbl = sa.Table('sourcestamps', metadata, autoload=True)
        res = conn.execute(sa.select([tbl.c.id, tbl.c.sourcestampsetid],
                                      order_by=[tbl.c.sourcestampsetid, tbl.c.id]))
        got_sourcestamps = res.fetchall()

        self.assertEqual(
                dict(buildsets=exp_buildsets, sourcestamps=exp_sourcestamps),
                dict(buildsets=got_buildsets, sourcestamps=got_sourcestamps))

    # tests

    def test_1_buildsets(self):
        buildsetdata = [(10, 100),(20, 200),(30, 300)]
        def setup_thd(conn):
            self.create_tables_thd(conn)
            self.fill_tables_with_testdata(conn, buildsetdata)

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn
            tbl = sa.Table('buildsets', metadata, autoload=True)
            self.assertTrue(hasattr(tbl.c, 'sourcestampsetid'))
            insp = reflection.Inspector.from_engine(conn)
            fk = insp.get_foreign_keys('buildsets')[0]
            del fk['name'] # schema dependent
            del fk['referred_schema'] # idem
            self.assertEqual(fk,{'constrained_columns':['sourcestampsetid'],
                              'referred_table':'sourcestampsets',
                              'referred_columns':['id']})
            res = conn.execute(sa.select([tbl.c.id, tbl.c.sourcestampsetid], order_by=tbl.c.id))
            got_buildsets = res.fetchall()
            self.assertEqual(got_buildsets, buildsetdata)

        return self.do_test_migration(17, 18, setup_thd, verify_thd)

    def test_2_sourcestamp(self):
        buildsetdata = [(10, 100),(20, 200),(30, 300)]
        sourcestampdata = [ (ssid, ssid) for bsid, ssid in buildsetdata ]
        def setup_thd(conn):
            self.create_tables_thd(conn)
            self.fill_tables_with_testdata(conn, buildsetdata)

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn
            tbl = sa.Table('sourcestamps', metadata, autoload=True)
            self.assertTrue(hasattr(tbl.c, 'sourcestampsetid'))
            insp = reflection.Inspector.from_engine(conn)
            fk = insp.get_foreign_keys('sourcestamps')[0]
            del fk['name'] # schema dependent
            del fk['referred_schema'] # idem
            self.assertEqual(fk,{'constrained_columns':['sourcestampsetid'],
                              'referred_table':'sourcestampsets',
                              'referred_columns':['id']})
            res = conn.execute(sa.select([tbl.c.id, tbl.c.sourcestampsetid],
                                          order_by=[tbl.c.sourcestampsetid, tbl.c.id]))
            got_sourcestamps = res.fetchall()
            self.assertEqual(got_sourcestamps, sourcestampdata)

        return self.do_test_migration(17, 18, setup_thd, verify_thd)

    def test_3_sourcestampset(self):
        buildsetdata = [(10, 100),(20, 200),(30, 300)]
        sourcestampsetdata = [ (ssid,) for bsid, ssid in buildsetdata ]
        def setup_thd(conn):
            self.create_tables_thd(conn)
            self.fill_tables_with_testdata(conn, buildsetdata)

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn
            tbl = sa.Table('sourcestampsets', metadata, autoload=True)
            self.assertTrue(hasattr(tbl.c, 'id'))
            res = conn.execute(sa.select([tbl.c.id],order_by=[tbl.c.id]))
            got_sourcestampsets = res.fetchall()
            self.assertEqual(got_sourcestampsets, sourcestampsetdata)

        return self.do_test_migration(17, 18, setup_thd, verify_thd)

    def test_4_integrated_migration(self):
        buildsetdata = [(10, 100),(20, 200),(30, 300)]
        sourcestampdata = [ (ssid, ssid) for bsid, ssid in buildsetdata ]
        sourcestampsetdata = [ (ssid,) for bsid, ssid in buildsetdata ]
        def setup_thd(conn):
            self.create_tables_thd(conn)
            self.fill_tables_with_testdata(conn, buildsetdata)

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn
            # Test for the buildsets
            tbl = sa.Table('buildsets', metadata, autoload=True)
            res = conn.execute(sa.select([tbl.c.id, tbl.c.sourcestampsetid], order_by=tbl.c.id))
            got_buildsets = res.fetchall()
            self.assertEqual(got_buildsets, buildsetdata)

            # Test for the sourcestamps
            tbl = sa.Table('sourcestamps', metadata, autoload=True)
            res = conn.execute(sa.select([tbl.c.id, tbl.c.sourcestampsetid],
                                          order_by=[tbl.c.sourcestampsetid, tbl.c.id]))
            got_sourcestamps = res.fetchall()
            self.assertEqual(got_sourcestamps, sourcestampdata)

            tbl = sa.Table('sourcestampsets', metadata, autoload=True)
            res = conn.execute(sa.select([tbl.c.id],order_by=[tbl.c.id]))
            got_sourcestampsets = res.fetchall()
            self.assertEqual(got_sourcestampsets, sourcestampsetdata)

        return self.do_test_migration(17, 18, setup_thd, verify_thd)
