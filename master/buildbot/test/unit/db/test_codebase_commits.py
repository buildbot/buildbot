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

from parameterized import parameterized
from twisted.trial import unittest

from buildbot.db import codebase_commits
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.util.twisted import async_to_deferred


class Tests(TestReactorMixin, unittest.TestCase):
    @async_to_deferred
    async def setUp(self) -> None:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = await fakemaster.make_master(self, wantDb=True)
        await self.master.db.insert_test_data([
            fakedb.Project(id=7, name='fake_project7'),
            fakedb.Codebase(id=13, projectid=7, name='codebase1'),
            fakedb.CodebaseCommit(id=106, codebaseid=13),
            fakedb.CodebaseCommit(id=107, codebaseid=13, parent_commitid=106),
            fakedb.CodebaseCommit(id=108, codebaseid=13, parent_commitid=107),
            fakedb.CodebaseCommit(id=109, codebaseid=13, parent_commitid=108),
            fakedb.CodebaseCommit(id=110, codebaseid=13, parent_commitid=109),
            fakedb.CodebaseCommit(id=119, codebaseid=13, parent_commitid=108),
            fakedb.CodebaseCommit(id=120, codebaseid=13, parent_commitid=119),
        ])

    @async_to_deferred
    async def test_get_commit_by_revision(self) -> None:
        dbdict = await self.master.db.codebase_commits.get_commit_by_revision(
            codebaseid=13, revision='rev110'
        )

        self.assertEqual(
            dbdict,
            codebase_commits.CodebaseCommitModel(
                id=110,
                codebaseid=13,
                author='author1',
                committer='committer1',
                comments='comments1',
                when_timestamp=1234567,
                revision='rev110',
                parent_commitid=109,
            ),
        )

    @async_to_deferred
    async def test_get_commit_by_revision_does_not_exist(self) -> None:
        id = await self.master.db.codebase_commits.get_commit_by_revision(
            codebaseid=13, revision='rev_not_exist'
        )
        self.assertIsNone(id)

    @parameterized.expand([(200, 200), (110, 200), (200, 110)])
    @async_to_deferred
    async def test_get_first_common_commit_with_ranges_does_not_exist(
        self, id1: int, id2: int
    ) -> None:
        r = await self.master.db.codebase_commits.get_first_common_commit_with_ranges(id1, id2)
        self.assertIsNone(r)

    @parameterized.expand([
        ('same_commit', 110, 110, (110, [110], [110])),
        ('same_branch1', 106, 110, (106, [106], [106, 107, 108, 109, 110])),
        ('same_branch2', 110, 106, (106, [106, 107, 108, 109, 110], [106])),
        ('different_branches', 110, 120, (108, [108, 109, 110], [108, 119, 120])),
    ])
    @async_to_deferred
    async def test_get_first_common_commit_with_ranges_does_same_c(
        self, name: str, id1: int, id2: int, expected: tuple[int, list[int], list[int]]
    ) -> None:
        r = await self.master.db.codebase_commits.get_first_common_commit_with_ranges(id1, id2)
        self.assertEqual(r, expected)

    @async_to_deferred
    async def test_get_commits(self) -> None:
        commits = await self.master.db.codebase_commits.get_commits(codebaseid=13)
        self.assertEqual(sorted(c.id for c in commits), [106, 107, 108, 109, 110, 119, 120])

    @async_to_deferred
    async def test_get_commits_by_id(self) -> None:
        dbdicts = await self.master.db.codebase_commits.get_commits_by_id([106, 200, 107])
        self.assertEqual(
            dbdicts,
            [
                codebase_commits.CodebaseCommitModel(
                    id=106,
                    codebaseid=13,
                    author='author1',
                    committer='committer1',
                    comments='comments1',
                    when_timestamp=1234567,
                    revision='rev106',
                    parent_commitid=None,
                ),
                None,
                codebase_commits.CodebaseCommitModel(
                    id=107,
                    codebaseid=13,
                    author='author1',
                    committer='committer1',
                    comments='comments1',
                    when_timestamp=1234567,
                    revision='rev107',
                    parent_commitid=106,
                ),
            ],
        )

    @async_to_deferred
    async def test_add_commit(self) -> None:
        await self.master.db.codebase_commits.add_commit(
            codebaseid=13,
            author='new_author',
            committer='new_committer',
            comments='new_comments',
            when_timestamp=12345678,
            revision='new_revision',
            parent_commitid=110,
        )
        dbdicts = await self.master.db.codebase_commits.get_commits_by_id([121])
        self.assertEqual(
            dbdicts,
            [
                codebase_commits.CodebaseCommitModel(
                    id=121,
                    codebaseid=13,
                    author='new_author',
                    committer='new_committer',
                    comments='new_comments',
                    when_timestamp=12345678,
                    revision='new_revision',
                    parent_commitid=110,
                )
            ],
        )
