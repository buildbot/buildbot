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
from twisted.python import log
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
            # NOTE: foreign key omitted:
            sa.Column('sourcestampid', sa.Integer, nullable=False),
            sa.Column('submitted_at', sa.Integer, nullable=False),
            sa.Column('complete', sa.SmallInteger, nullable=False,
                      server_default=sa.DefaultClause("0")),
            sa.Column('complete_at', sa.Integer),
            sa.Column('results', sa.SmallInteger),
        )
        self.buildsets.create(bind=conn)
        sa.Index('buildsets_complete', self.buildsets.c.complete).create()
        sa.Index(
            'buildsets_submitted_at', self.buildsets.c.submitted_at).create()

        self.patches = sautils.Table(
            'patches', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('patchlevel', sa.Integer, nullable=False),
            sa.Column('patch_base64', sa.Text, nullable=False),
            sa.Column('patch_author', sa.Text, nullable=False),
            sa.Column('patch_comment', sa.Text, nullable=False),
            sa.Column('subdir', sa.Text),
        )
        self.patches.create(bind=conn)

        self.sourcestamps = sautils.Table(
            'sourcestamps', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('branch', sa.String(256)),
            sa.Column('revision', sa.String(256)),
            sa.Column('patchid', sa.Integer, sa.ForeignKey('patches.id')),
            sa.Column('repository', sa.String(
                length=512), nullable=False, server_default=''),
            sa.Column(
                'project', sa.String(length=512), nullable=False, server_default=''),
            sa.Column(
                'sourcestampid', sa.Integer, sa.ForeignKey('sourcestamps.id')),
        )
        self.sourcestamps.create(bind=conn)

    def fill_tables_with_testdata(self, conn, testdata):
        for bsid, ssid in testdata:
            self.insert_buildset_sourcestamp(conn, bsid, ssid)

    def insert_buildset_sourcestamp(self, conn, bsid, sourcestampid):
        conn.execute(self.buildsets.insert(),
                     id=bsid,
                     externalid_string='',
                     reason='just',
                     sourcestampid=sourcestampid,
                     submitted_at=22417200,
                     complete=0,
                     complete_at=22417200,
                     results=0)
        conn.execute(self.sourcestamps.insert(),
                     id=sourcestampid,
                     branch='this_branch',
                     revision='this_revision',
                     patchid=None,
                     repository='repo_a',
                     project='')

    def assertBuildsetSourceStamp_thd(self, conn, exp_buildsets=[],
                                      exp_sourcestamps=[]):
        metadata = sa.MetaData()
        metadata.bind = conn
        tbl = sautils.Table('buildsets', metadata, autoload=True)
        res = conn.execute(
            sa.select([tbl.c.id, tbl.c.sourcestampsetid], order_by=tbl.c.id))
        got_buildsets = res.fetchall()

        tbl = sautils.Table('sourcestamps', metadata, autoload=True)
        res = conn.execute(sa.select([tbl.c.id, tbl.c.sourcestampsetid],
                                     order_by=[tbl.c.sourcestampsetid, tbl.c.id]))
        got_sourcestamps = res.fetchall()

        self.assertEqual(
            dict(buildsets=exp_buildsets, sourcestamps=exp_sourcestamps),
            dict(buildsets=got_buildsets, sourcestamps=got_sourcestamps))

    # tests

    def thd_assertForeignKeys(self, conn, exp, with_constrained_columns=[]):
        # MySQL does not reflect or use foreign keys, so we can't check..
        if conn.dialect.name == 'mysql':
            return

        insp = reflection.Inspector.from_engine(conn)
        fks = orig_fks = insp.get_foreign_keys('buildsets')

        # filter out constraints including all of the given columns
        with_constrained_columns = set(with_constrained_columns)
        fks = sorted([fk
                      for fk in fks
                      if not with_constrained_columns - set(fk['constrained_columns'])
                      ])

        # clean up
        for fk in fks:
            del fk['name']  # schema dependent
            del fk['referred_schema']  # idem
            if 'options' in fk:
                del fk['options']  # newer versions of sqlalchemy

        # finally, assert
        if fks != exp:
            log.msg("got: %r" % (orig_fks,))
        self.assertEqual(fks, exp)

    def test_1_buildsets(self):
        buildsetdata = [(10, 100), (20, 200), (30, 300)]

        def setup_thd(conn):
            self.create_tables_thd(conn)
            self.fill_tables_with_testdata(conn, buildsetdata)

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn
            tbl = sautils.Table('buildsets', metadata, autoload=True)
            self.assertTrue(hasattr(tbl.c, 'sourcestampsetid'))

            self.thd_assertForeignKeys(conn, [{
                'constrained_columns': ['sourcestampsetid'],
                'referred_table':'sourcestampsets',
                'referred_columns':['id']},
            ], with_constrained_columns=['sourcestampsetid'])

            res = conn.execute(
                sa.select([tbl.c.id, tbl.c.sourcestampsetid], order_by=tbl.c.id))
            got_buildsets = res.fetchall()
            self.assertEqual(got_buildsets, buildsetdata)

        return self.do_test_migration(17, 18, setup_thd, verify_thd)

    def test_2_sourcestamp(self):
        buildsetdata = [(10, 100), (20, 200), (30, 300)]
        sourcestampdata = [(ssid, ssid) for bsid, ssid in buildsetdata]

        def setup_thd(conn):
            self.create_tables_thd(conn)
            self.fill_tables_with_testdata(conn, buildsetdata)

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn
            tbl = sautils.Table('sourcestamps', metadata, autoload=True)
            self.assertTrue(hasattr(tbl.c, 'sourcestampsetid'))

            self.thd_assertForeignKeys(conn, [{
                'constrained_columns': ['sourcestampsetid'],
                'referred_table':'sourcestampsets',
                'referred_columns':['id']},
            ], with_constrained_columns=['sourcestampsetid'])

            res = conn.execute(sa.select([tbl.c.id, tbl.c.sourcestampsetid],
                                         order_by=[tbl.c.sourcestampsetid, tbl.c.id]))
            got_sourcestamps = res.fetchall()
            self.assertEqual(got_sourcestamps, sourcestampdata)

        return self.do_test_migration(17, 18, setup_thd, verify_thd)

    def test_3_sourcestampset(self):
        buildsetdata = [(10, 100), (20, 200), (30, 300)]
        sourcestampsetdata = [(ssid,) for bsid, ssid in buildsetdata]

        def setup_thd(conn):
            self.create_tables_thd(conn)
            self.fill_tables_with_testdata(conn, buildsetdata)

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn
            tbl = sautils.Table('sourcestampsets', metadata, autoload=True)
            self.assertTrue(hasattr(tbl.c, 'id'))
            res = conn.execute(sa.select([tbl.c.id], order_by=[tbl.c.id]))
            got_sourcestampsets = res.fetchall()
            self.assertEqual(got_sourcestampsets, sourcestampsetdata)

        return self.do_test_migration(17, 18, setup_thd, verify_thd)

    def test_4_integrated_migration(self):
        buildsetdata = [(10, 100), (20, 200), (30, 300)]
        sourcestampdata = [(ssid, ssid) for bsid, ssid in buildsetdata]
        sourcestampsetdata = [(ssid,) for bsid, ssid in buildsetdata]

        def setup_thd(conn):
            self.create_tables_thd(conn)
            self.fill_tables_with_testdata(conn, buildsetdata)

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn
            # Test for the buildsets
            tbl = sautils.Table('buildsets', metadata, autoload=True)
            res = conn.execute(
                sa.select([tbl.c.id, tbl.c.sourcestampsetid], order_by=tbl.c.id))
            got_buildsets = res.fetchall()
            self.assertEqual(got_buildsets, buildsetdata)

            # Test for the sourcestamps
            tbl = sautils.Table('sourcestamps', metadata, autoload=True)
            res = conn.execute(sa.select([tbl.c.id, tbl.c.sourcestampsetid],
                                         order_by=[tbl.c.sourcestampsetid, tbl.c.id]))
            got_sourcestamps = res.fetchall()
            self.assertEqual(got_sourcestamps, sourcestampdata)

            tbl = sautils.Table('sourcestampsets', metadata, autoload=True)
            res = conn.execute(sa.select([tbl.c.id], order_by=[tbl.c.id]))
            got_sourcestampsets = res.fetchall()
            self.assertEqual(got_sourcestampsets, sourcestampsetdata)

        return self.do_test_migration(17, 18, setup_thd, verify_thd)
