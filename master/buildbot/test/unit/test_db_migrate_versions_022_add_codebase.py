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

import sqlalchemy as sa
from twisted.trial import unittest

from buildbot.test.util import migration
from buildbot.util import UTC
from buildbot.util import datetime2epoch
from buildbot.util import sautils


class Migration(migration.MigrateTestMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpMigrateTest()

    def tearDown(self):
        return self.tearDownMigrateTest()

    # create tables as they are before migrating to version 019
    def create_tables_thd(self, conn):
        metadata = sa.MetaData()
        metadata.bind = conn

        self.sourcestamps = sautils.Table(
            'sourcestamps', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('branch', sa.String(256)),
            sa.Column('revision', sa.String(256)),
            sa.Column('patchid', sa.Integer),
            sa.Column('repository', sa.String(
                length=512), nullable=False, server_default=''),
            sa.Column(
                'project', sa.String(length=512), nullable=False, server_default=''),
            sa.Column('sourcestampsetid', sa.Integer),
        )
        self.sourcestamps.create(bind=conn)

        self.changes = sautils.Table(
            'changes', metadata,
            sa.Column('changeid', sa.Integer, primary_key=True),
            sa.Column('author', sa.String(256), nullable=False),
            sa.Column('comments', sa.String(1024), nullable=False),
            sa.Column('is_dir', sa.SmallInteger, nullable=False),
            sa.Column('branch', sa.String(256)),
            sa.Column('revision', sa.String(256)),
            sa.Column('revlink', sa.String(256)),
            sa.Column('when_timestamp', sa.Integer, nullable=False),
            sa.Column('category', sa.String(256)),
            sa.Column('repository', sa.String(
                length=512), nullable=False, server_default=''),
            sa.Column(
                'project', sa.String(length=512), nullable=False, server_default=''),
        )
        self.changes.create(bind=conn)

    def reload_tables_after_migration(self, conn):
        metadata = sa.MetaData()
        metadata.bind = conn
        self.sourcestamps = sautils.Table(
            'sourcestamps', metadata, autoload=True)
        self.changes = sautils.Table('changes', metadata, autoload=True)

    def fill_tables_with_testdata(self, conn, testdata):
        for ssid, repo, codebase, cid in testdata:
            self.insert_sourcestamps_changes(conn, ssid, repo, codebase, cid)

    def insert_sourcestamps_changes(self, conn, sourcestampid, repository, codebase, changeid):
        conn.execute(self.sourcestamps.insert(),
                     id=sourcestampid,
                     sourcestampsetid=sourcestampid,
                     branch='this_branch',
                     revision='this_revision',
                     patchid=None,
                     repository=repository,
                     project='',
                     codebase=codebase)

        dt_when = datetime.datetime(1978, 6, 15, 12, 31, 15, tzinfo=UTC)
        conn.execute(self.changes.insert(),
                     changeid=changeid,
                     author='develop',
                     comments='no comment',
                     is_dir=0,
                     branch='default',
                     revision='FD56A89',
                     revling=None,
                     when_timestamp=datetime2epoch(dt_when),
                     category=None,
                     repository=repository,
                     codebase=codebase,
                     project='')

    def test_changes_has_codebase(self):
        changesdata = [(1000, 'https://svn.com/repo_a', 'repo_a', 1)]

        def setup_thd(conn):
            self.create_tables_thd(conn)

        def verify_thd(conn):
            self.reload_tables_after_migration(conn)
            tbl = self.changes
            self.assertTrue(
                hasattr(tbl.c, 'codebase'), 'Column codebase not found')

            # insert data in the table and new column
            self.fill_tables_with_testdata(conn, changesdata)

            res = conn.execute(sa.select([tbl.c.changeid, tbl.c.repository,
                                          tbl.c.codebase, ]))
            got_changes = res.fetchall()
            self.assertEqual(
                got_changes, [(1, 'https://svn.com/repo_a', 'repo_a')])

        return self.do_test_migration(21, 22, setup_thd, verify_thd)

    def test_sourcestamps_has_codebase(self):
        changesdata = [(1000, 'https://svn.com/repo_a', 'repo_a', 1)]

        def setup_thd(conn):
            self.create_tables_thd(conn)

        def verify_thd(conn):
            self.reload_tables_after_migration(conn)
            tbl = self.sourcestamps
            self.assertTrue(
                hasattr(tbl.c, 'codebase'), 'Column codebase not found')

            # insert data in the table and new column
            self.fill_tables_with_testdata(conn, changesdata)

            res = conn.execute(sa.select([tbl.c.id, tbl.c.repository,
                                          tbl.c.codebase, ]))
            got_sourcestamps = res.fetchall()
            self.assertEqual(
                got_sourcestamps, [(1000, 'https://svn.com/repo_a', 'repo_a')])

        return self.do_test_migration(21, 22, setup_thd, verify_thd)
