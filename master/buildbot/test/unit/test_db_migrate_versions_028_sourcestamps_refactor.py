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

            patches = sautils.Table(
                'patches', metadata,
                sa.Column('id', sa.Integer, primary_key=True),
                # ...
            )
            patches.create()

            sourcestampsets = sautils.Table(
                'sourcestampsets', metadata,
                sa.Column('id', sa.Integer, primary_key=True),
            )
            sourcestampsets.create()

            sourcestamps = sautils.Table(
                'sourcestamps', metadata,
                sa.Column('id', sa.Integer, primary_key=True),
                sa.Column('branch', sa.String(256)),
                sa.Column('revision', sa.String(256)),
                sa.Column('patchid', sa.Integer, sa.ForeignKey('patches.id')),
                sa.Column('repository', sa.String(length=512), nullable=False,
                          server_default=''),
                sa.Column('codebase', sa.String(256), nullable=False,
                          server_default=sa.DefaultClause("")),
                sa.Column('project', sa.String(length=512), nullable=False,
                          server_default=''),
                sa.Column('sourcestampsetid', sa.Integer,
                          sa.ForeignKey('sourcestampsets.id')),
            )
            sourcestamps.create()

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
                sa.Column('sourcestampsetid', sa.Integer,
                          sa.ForeignKey('sourcestampsets.id')),
            )
            buildsets.create()

            changes = sautils.Table(
                'changes', metadata,
                sa.Column('changeid', sa.Integer, primary_key=True),
                sa.Column('author', sa.String(256), nullable=False),
                sa.Column('comments', sa.String(1024), nullable=False),
                # old, for CVS
                sa.Column('is_dir', sa.SmallInteger, nullable=False),
                sa.Column('branch', sa.String(256)),
                sa.Column('revision', sa.String(256)),  # CVS uses NULL
                sa.Column('revlink', sa.String(256)),
                sa.Column('when_timestamp', sa.Integer, nullable=False),
                sa.Column('category', sa.String(256)),
                sa.Column('repository', sa.String(length=512), nullable=False,
                          server_default=''),
                sa.Column('codebase', sa.String(256), nullable=False,
                          server_default=sa.DefaultClause("")),
                sa.Column('project', sa.String(length=512), nullable=False,
                          server_default=''),
            )
            changes.create()

            sourcestamp_changes = sautils.Table(
                'sourcestamp_changes', metadata,
                sa.Column('sourcestampid', sa.Integer,
                          sa.ForeignKey('sourcestamps.id'), nullable=False),
                sa.Column('changeid', sa.Integer, sa.ForeignKey('changes.changeid'),
                          nullable=False),
            )
            sourcestamp_changes.create()

            # now insert some data..
            conn.execute(changes.insert(), [
                {'changeid': 101, 'author': 'dustin', 'comments': 'AAAA',
                 'branch': 'br', 'revision': 'aaa', 'revlink': 'ht:/',
                 'when_timestamp': 1356371433, 'category': 'cat',
                 'repository': 'git:/', 'codebase': 'cb', 'project': 'pr',
                 'is_dir': 0},
                {'changeid': 102, 'author': 'tom', 'comments': 'BBBB',
                 'branch': 'br', 'revision': 'bbb', 'revlink': 'ht:/',
                 'when_timestamp': 1356371433, 'category': 'cat',
                 'repository': 'git:/', 'codebase': 'cb', 'project': 'pr',
                 'is_dir': 0},
                {'changeid': 103, 'author': 'pierre', 'comments': 'CCCC',
                 'branch': 'dev', 'revision': 'ccc', 'revlink': 'ht:/',
                 'when_timestamp': 1356371433, 'category': 'cat',
                 'repository': 'git:/', 'codebase': 'cb', 'project': 'pr',
                 'is_dir': 0},
            ])
            conn.execute(patches.insert(), [
                {'id': 301},  # other columns don't matter
            ])
            conn.execute(sourcestampsets.insert(), [
                {'id': 2001},
                {'id': 2002},
                {'id': 2011},
                {'id': 9999},
            ])
            conn.execute(sourcestamps.insert(), [
                {'id': 201, 'branch': 'br', 'revision': 'aaa',
                 'patchid': None, 'repository': 'git:/', 'codebase': 'cb',
                 'project': 'pr', 'sourcestampsetid': 2001},
                {'id': 202, 'branch': 'br', 'revision': 'bbb',
                 'patchid': None, 'repository': 'git:/', 'codebase': 'cb',
                 'project': 'pr', 'sourcestampsetid': 2002},
                {'id': 211, 'branch': 'br', 'revision': 'aaa',
                 'patchid': 301, 'repository': 'git:/', 'codebase': 'cb',
                 'project': 'pr', 'sourcestampsetid': 2011},
                {'id': 221, 'branch': None, 'revision': 'a22',
                 'patchid': None, 'repository': 'hg:/', 'codebase': 'lib1',
                 'project': 'pr', 'sourcestampsetid': 2001},
                {'id': 231, 'branch': None, 'revision': 'a33',
                 'patchid': None, 'repository': 'svn:/', 'codebase': 'lib2',
                 'project': 'pr', 'sourcestampsetid': 2001},
                {'id': 222, 'branch': None, 'revision': 'b22',
                 'patchid': None, 'repository': 'hg:/', 'codebase': 'lib1',
                 'project': 'pr', 'sourcestampsetid': 2002},
                {'id': 232, 'branch': None, 'revision': 'b33',
                 'patchid': None, 'repository': 'svn:/', 'codebase': 'lib2',
                 'project': 'pr', 'sourcestampsetid': 2002},
                # this sourcestamp gets forgotten, because it's not used
                {'id': 999, 'branch': None, 'revision': '999',
                 'patchid': None, 'repository': 'svn:/', 'codebase': '999',
                 'project': 'pr', 'sourcestampsetid': 9999},
            ])

            conn.execute(sourcestamp_changes.insert(), [
                # change 101 has sourcestamp 201
                {'changeid': 101, 'sourcestampid': 201},
                # change 102 has sourcestamps 201 and 202
                {'changeid': 102, 'sourcestampid': 201},
                {'changeid': 102, 'sourcestampid': 202},
                # change 103 has no sourcestamps
            ])
            conn.execute(buildsets.insert(), [
                {'id': 501, 'submitted_at': 1356372121,
                 'sourcestampsetid': 2001},
                {'id': 502, 'submitted_at': 1356372131,
                 'sourcestampsetid': 2002},
                {'id': 511, 'submitted_at': 1356372141,
                 'sourcestampsetid': 2011},
            ])

        def verify_thd(conn):
            r = conn.execute("""select branch, codebase, patchid, project,
                                       repository, revision, id
                            from sourcestamps""")
            # sort by revision, then patchid - in Python, so NULL/None is
            # handled consistently
            sourcestamps = [dict(row) for row in r.fetchall()]
            sourcestamps.sort(key=lambda ss: (ss['revision'], ss['patchid']))
            new_ssids = dict(zip([221, 231, 201, 211, 222, 232, 202, 888],
                                 [ss['id'] for ss in sourcestamps]))
            self.assertEqual(sourcestamps, [
                {u'branch': None, u'codebase': u'lib1', u'patchid': None,
                 u'project': u'pr', u'repository': u'hg:/',
                 u'revision': u'a22', 'id': new_ssids[221]},
                {u'branch': None, u'codebase': u'lib2', u'patchid': None,
                 u'project': u'pr', u'repository': u'svn:/',
                 u'revision': u'a33', 'id': new_ssids[231]},
                {u'branch': u'br', u'codebase': u'cb', u'patchid': None,
                 u'project': u'pr', u'repository': u'git:/',
                 u'revision': u'aaa', 'id': new_ssids[201]},
                {u'branch': u'br', u'codebase': u'cb', u'patchid': 301,
                 u'project': u'pr', u'repository': u'git:/',
                 u'revision': u'aaa', 'id': new_ssids[211]},
                {u'branch': None, u'codebase': u'lib1', u'patchid': None,
                 u'project': u'pr', u'repository': u'hg:/',
                 u'revision': u'b22', 'id': new_ssids[222]},
                {u'branch': None, u'codebase': u'lib2', u'patchid': None,
                 u'project': u'pr', u'repository': u'svn:/',
                 u'revision': u'b33', 'id': new_ssids[232]},
                {u'branch': u'br', u'codebase': u'cb', u'patchid': None,
                 u'project': u'pr', u'repository': u'git:/',
                 u'revision': u'bbb', 'id': new_ssids[202]},
                {u'branch': u'dev', u'codebase': u'cb', u'patchid': None,
                 u'project': u'pr', u'repository': u'git:/',
                 u'revision': u'ccc', 'id': new_ssids[888]}])  # (new ss)

            r = conn.execute("""select changeid, sourcestampid from changes
                                order by changeid""")
            self.assertEqual(map(dict, r.fetchall()), [
                {u'changeid': 101, u'sourcestampid': new_ssids[201]},
                {u'changeid': 102, u'sourcestampid': new_ssids[202]},
                {u'changeid': 103, u'sourcestampid': new_ssids[888]}
            ])

            r = conn.execute("""select buildsetid, sourcestampid
                                from buildset_sourcestamps""")
            self.assertEqual(sorted(map(dict, r.fetchall())), sorted([
                {u'buildsetid': 501, u'sourcestampid': new_ssids[201]},
                {u'buildsetid': 501, u'sourcestampid': new_ssids[221]},
                {u'buildsetid': 501, u'sourcestampid': new_ssids[231]},
                {u'buildsetid': 502, u'sourcestampid': new_ssids[202]},
                {u'buildsetid': 502, u'sourcestampid': new_ssids[222]},
                {u'buildsetid': 502, u'sourcestampid': new_ssids[232]},
                {u'buildsetid': 511, u'sourcestampid': new_ssids[211]}
            ]))

        return self.do_test_migration(27, 28, setup_thd, verify_thd)
