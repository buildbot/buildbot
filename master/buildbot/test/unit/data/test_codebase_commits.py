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

from typing import Any
from typing import cast

from parameterized import parameterized
from twisted.trial import unittest

from buildbot.data import codebase_commits
from buildbot.data import resultspec
from buildbot.master import BuildMaster
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import endpoint
from buildbot.test.util import interfaces
from buildbot.util.twisted import async_to_deferred


class CodebaseCommitEndpoint(endpoint.EndpointMixin, unittest.TestCase):
    endpointClass = codebase_commits.CodebaseCommitEndpoint
    resourceTypeClass = codebase_commits.CodebaseCommit

    @async_to_deferred
    async def setUp(self) -> None:  # type: ignore[override]
        await self.setUpEndpoint()
        await self.master.db.insert_test_data([
            fakedb.Project(id=7, name='fake_project7'),
            fakedb.Codebase(id=13, projectid=7, name='codebase1'),
            fakedb.CodebaseCommit(id=110, codebaseid=13),
        ])

    @async_to_deferred
    async def test_get_existing_id(self) -> None:
        commit = await self.callGet(('commits', 110))

        self.validateData(commit)
        self.assertEqual(
            commit,
            {
                'author': 'author1',
                'codebaseid': 13,
                'comments': 'comments1',
                'commitid': 110,
                'committer': 'committer1',
                'parent_commitid': None,
                'revision': 'rev110',
                'when_timestamp': 1234567,
            },
        )

    @async_to_deferred
    async def test_get_missing(self) -> None:
        commit = await self.callGet(('commits', 220))
        self.assertIsNone(commit)


class CodebaseCommitsEndpoint(endpoint.EndpointMixin, unittest.TestCase):
    endpointClass = codebase_commits.CodebaseCommitsEndpoint
    resourceTypeClass = codebase_commits.CodebaseCommit

    @async_to_deferred
    async def setUp(self) -> None:  # type: ignore[override]
        await self.setUpEndpoint()
        await self.master.db.insert_test_data([
            fakedb.Project(id=7, name='fake_project7'),
            fakedb.Codebase(id=13, projectid=7, name='codebase1'),
            fakedb.CodebaseCommit(id=106, codebaseid=13),
            fakedb.CodebaseCommit(id=107, codebaseid=13, parent_commitid=106),
            fakedb.CodebaseCommit(id=108, codebaseid=13, parent_commitid=107),
            fakedb.CodebaseCommit(id=109, codebaseid=13, parent_commitid=108),
            fakedb.CodebaseCommit(id=110, codebaseid=13, parent_commitid=109),
        ])

    @parameterized.expand([
        ('no_filter', None, [106, 107, 108, 109, 110]),
        ('existing', 108, [109]),
        ('not_existing', 120, []),
    ])
    @async_to_deferred
    async def test_get(
        self, name: str, parent_commitid_filter: int | None, expected_commitids: list[int]
    ) -> None:
        result_spec = None
        if parent_commitid_filter is not None:
            result_spec = resultspec.OptimisedResultSpec(
                filters=[resultspec.Filter('parent_commitid', 'eq', [parent_commitid_filter])]
            )

        commits = await self.callGet(('codebases', '13', 'commits'), resultSpec=result_spec)

        for b in commits:
            self.validateData(b)

        self.assertEqual(sorted([c['commitid'] for c in commits]), expected_commitids)


class CodebaseCommitsGraphEndpoint(endpoint.EndpointMixin, unittest.TestCase):
    endpointClass = codebase_commits.CodebaseCommitsGraphEndpoint
    resourceTypeClass = codebase_commits.CodebaseCommit

    @async_to_deferred
    async def setUp(self) -> None:  # type: ignore[override]
        await self.setUpEndpoint()
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
    async def test_simple(self) -> None:
        r = await self.callGet(('codebases', '13', 'commits_common_parent', '120', '110'))

        self.assertEqual(r, {'common': 108, 'from1': [108, 119, 120], 'from2': [108, 109, 110]})


class CodebaseCommitTests(interfaces.InterfaceTests, TestReactorMixin, unittest.TestCase):
    @async_to_deferred
    async def setUp(self) -> None:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = await fakemaster.make_master(self, wantMq=True, wantDb=True, wantData=True)
        self.rtype = codebase_commits.CodebaseCommit(cast(BuildMaster, self.master))
        await self.master.db.insert_test_data([
            fakedb.Project(id=7, name='fake_project7'),
            fakedb.Codebase(id=13, projectid=7, name='codebase1', slug='slug_codebase1'),
        ])

    def test_signature_add_commit(self) -> None:
        @self.assertArgSpecMatches(
            self.master.data.updates.add_commit,
            self.rtype.add_commit,
        )
        def add_commit(
            self: Any,
            *,
            codebaseid: int,
            author: str,
            committer: str | None = None,
            files: list[str] | None = None,
            comments: str,
            when_timestamp: int,
            revision: str,
            parent_commitid: int | None = None,
        ) -> None:
            pass

    @async_to_deferred
    async def test_add_commit(self) -> None:
        await self.master.data.updates.add_commit(
            codebaseid=13,
            author='author1',
            committer='committer1',
            comments='comments1',
            when_timestamp=12345678,
            revision='rev120',
        )
        commits = await self.master.data.get(('codebases', 13, 'commits'))
        self.assertEqual(
            commits,
            [
                {
                    'commitid': 1,
                    'codebaseid': 13,
                    'author': 'author1',
                    'committer': 'committer1',
                    'comments': 'comments1',
                    'when_timestamp': 12345678,
                    'revision': 'rev120',
                    'parent_commitid': None,
                }
            ],
        )
