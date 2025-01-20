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

from __future__ import annotations

import sqlalchemy as sa
from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.util import migration
from buildbot.util import sautils


class Migration(migration.MigrateTestMixin, unittest.TestCase):
    def setUp(self) -> defer.Deferred[None]:  # type: ignore[override]
        return self.setUpMigrateTest()

    def create_tables_thd(self, conn: sa.future.engine.Connection) -> None:
        metadata = sa.MetaData()
        metadata.bind = conn  # type: ignore[attr-defined]

        projects_tbl = sautils.Table(
            'projects',
            metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('name', sa.Text, nullable=False),
            sa.Column('name_hash', sa.String(40), nullable=False),
            sa.Column('slug', sa.String(50), nullable=False),
            sa.Column('description', sa.Text, nullable=True),
            sa.Column('description_format', sa.Text, nullable=True),
            sa.Column('description_html', sa.Text, nullable=True),
        )
        projects_tbl.create(bind=conn)

        conn.commit()

    def test_update(self) -> defer.Deferred[None]:
        def setup_thd(conn: sa.future.engine.Connection) -> None:
            self.create_tables_thd(conn)

        def verify_thd(conn: sa.future.engine.Connection) -> None:
            metadata = sa.MetaData()
            metadata.bind = conn  # type: ignore[attr-defined]

            # verify tables have been created
            codebases = sautils.Table('codebases', metadata, autoload_with=conn)
            q = sa.select(
                codebases.c.projectid,
                codebases.c.name,
                codebases.c.name_hash,
                codebases.c.slug,
            )
            self.assertEqual(conn.execute(q).fetchall(), [])

            codebase_commits = sautils.Table('codebase_commits', metadata, autoload_with=conn)
            q = sa.select(
                codebase_commits.c.codebaseid,
                codebase_commits.c.author,
                codebase_commits.c.committer,
                codebase_commits.c.comments,
                codebase_commits.c.when_timestamp,
                codebase_commits.c.revision,
                codebase_commits.c.parent_commitid,
            )
            self.assertEqual(conn.execute(q).fetchall(), [])

            codebase_branches = sautils.Table('codebase_branches', metadata, autoload_with=conn)
            q = sa.select(
                codebase_branches.c.codebaseid,
                codebase_branches.c.name,
                codebase_branches.c.name_hash,
                codebase_branches.c.commitid,
                codebase_branches.c.last_timestamp,
            )
            self.assertEqual(conn.execute(q).fetchall(), [])

            # verify indexes have been created
            insp = sa.inspect(conn)

            def verify_indexes(table: str, expected_indexes: list[str]) -> None:
                indexes = insp.get_indexes(table)
                index_names = [item['name'] for item in indexes]
                for expected_index in expected_indexes:
                    self.assertTrue(expected_index in index_names)

            verify_indexes('codebases', ['codebases_projects_name_hash'])
            verify_indexes('codebase_branches', ['codebase_branches_unique'])
            verify_indexes('codebase_commits', ['codebase_commits_unique'])

        return self.do_test_migration('066', '067', setup_thd, verify_thd)
