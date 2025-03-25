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

from buildbot.data import codebase_branches
from buildbot.data import resultspec
from buildbot.master import BuildMaster
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import endpoint
from buildbot.test.util import interfaces
from buildbot.util.twisted import async_to_deferred


class CodebaseBranchEndpoint(endpoint.EndpointMixin, unittest.TestCase):
    endpointClass = codebase_branches.CodebaseBranchEndpoint
    resourceTypeClass = codebase_branches.CodebaseBranch

    @async_to_deferred
    async def setUp(self) -> None:  # type: ignore[override]
        await self.setUpEndpoint()
        await self.master.db.insert_test_data([
            fakedb.Project(id=7, name='fake_project7'),
            fakedb.Codebase(id=13, projectid=7, name='codebase1'),
            fakedb.CodebaseCommit(id=110, codebaseid=13),
            fakedb.CodebaseBranch(id=220, codebaseid=13, name='branch1', commitid=110),
        ])

    @async_to_deferred
    async def test_get_existing(self) -> None:
        branch = await self.callGet(('branches', 220))

        self.validateData(branch)
        self.assertEqual(
            branch,
            {
                'branchid': 220,
                'codebaseid': 13,
                'commitid': 110,
                'last_timestamp': 1234567,
                'name': 'branch1',
            },
        )

    @async_to_deferred
    async def test_get_missing(self) -> None:
        branch = await self.callGet(('branches', 234))
        self.assertIsNone(branch)


class CodebaseBranchesEndpoint(endpoint.EndpointMixin, unittest.TestCase):
    endpointClass = codebase_branches.CodebaseBranchesEndpoint
    resourceTypeClass = codebase_branches.CodebaseBranch

    @async_to_deferred
    async def setUp(self) -> None:  # type: ignore[override]
        await self.setUpEndpoint()
        await self.master.db.insert_test_data([
            fakedb.Project(id=7, name='fake_project7'),
            fakedb.Codebase(id=13, projectid=7, name='codebase1'),
            fakedb.CodebaseCommit(id=110, codebaseid=13),
            fakedb.CodebaseCommit(id=111, codebaseid=13),
            fakedb.CodebaseCommit(id=112, codebaseid=13),
            fakedb.CodebaseBranch(id=220, codebaseid=13, name='branch1', commitid=110),
            fakedb.CodebaseBranch(id=221, codebaseid=13, name='branch2', commitid=111),
            fakedb.CodebaseBranch(id=222, codebaseid=13, name='branch3', commitid=112),
        ])

    @parameterized.expand([
        ('no_filter', None, [220, 221, 222]),
        ('existing', 111, [221]),
        ('not_existing', 120, []),
    ])
    @async_to_deferred
    async def test_get(
        self, name: str, commitid_filter: int | None, expected_branchids: list[str]
    ) -> None:
        result_spec = None
        if commitid_filter is not None:
            result_spec = resultspec.OptimisedResultSpec(
                filters=[resultspec.Filter('commitid', 'eq', [commitid_filter])]
            )

        branches = await self.callGet(('codebases', 13, 'branches'), resultSpec=result_spec)

        for b in branches:
            self.validateData(b)

        self.assertEqual(sorted([b['branchid'] for b in branches]), expected_branchids)


class CodebaseBranchTests(interfaces.InterfaceTests, TestReactorMixin, unittest.TestCase):
    @async_to_deferred
    async def setUp(self) -> None:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = await fakemaster.make_master(self, wantMq=True, wantDb=True, wantData=True)
        self.rtype = codebase_branches.CodebaseBranch(cast(BuildMaster, self.master))
        await self.master.db.insert_test_data([
            fakedb.Project(id=7, name='fake_project7'),
            fakedb.Codebase(id=13, projectid=7, name='codebase1'),
            fakedb.CodebaseCommit(id=110, codebaseid=13),
            fakedb.CodebaseCommit(id=111, codebaseid=13),
            fakedb.CodebaseBranch(id=220, codebaseid=13, name='branch1', commitid=110),
        ])

    def test_signature_update_branch(self) -> None:
        @self.assertArgSpecMatches(
            self.master.data.updates.update_branch,
            self.rtype.update_branch,
        )
        def update_branch(
            self: Any,
            *,
            codebaseid: int,
            name: str,
            commitid: int | None = None,
            last_timestamp: int,
        ) -> None:
            pass

    @async_to_deferred
    async def test_update_branch(self) -> None:
        await self.master.data.updates.update_branch(
            codebaseid=13,
            name='branch1',
            commitid=111,
            last_timestamp=87654321,
        )
        branch = await self.master.data.get(('branches', 220))
        self.assertEqual(
            branch,
            {
                'branchid': 220,
                'codebaseid': 13,
                'commitid': 111,
                'last_timestamp': 87654321,
                'name': 'branch1',
            },
        )
