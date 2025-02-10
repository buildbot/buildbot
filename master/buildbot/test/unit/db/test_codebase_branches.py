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


from twisted.trial import unittest

from buildbot.db import codebase_branches
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
            fakedb.CodebaseCommit(id=107, codebaseid=13),
            fakedb.CodebaseBranch(
                id=200, codebaseid=13, name='branch1', commitid=106, last_timestamp=123456700
            ),
            fakedb.CodebaseBranch(
                id=201, codebaseid=13, name='branch2', commitid=106, last_timestamp=123456701
            ),
            fakedb.CodebaseBranch(
                id=202, codebaseid=13, name='branch3', commitid=106, last_timestamp=123456702
            ),
        ])

    @async_to_deferred
    async def test_get_branch_exists_id(self) -> None:
        dbdict = await self.master.db.codebase_branches.get_branch(id=200)
        self.assertEqual(
            dbdict,
            codebase_branches.CodebaseBranchModel(
                id=200,
                codebaseid=13,
                name='branch1',
                commitid=106,
                last_timestamp=123456700,
            ),
        )

    @async_to_deferred
    async def test_get_branch_exists_name(self) -> None:
        dbdict = await self.master.db.codebase_branches.get_branch_by_name(
            codebaseid=13, name='branch1'
        )
        self.assertEqual(
            dbdict,
            codebase_branches.CodebaseBranchModel(
                id=200,
                codebaseid=13,
                name='branch1',
                commitid=106,
                last_timestamp=123456700,
            ),
        )

    @async_to_deferred
    async def test_get_branch_does_not_exist_name(self) -> None:
        dbdict = await self.master.db.codebase_branches.get_branch_by_name(
            codebaseid=13, name='branch_not_exists'
        )
        self.assertIsNone(dbdict)

    @async_to_deferred
    async def test_get_branch_does_not_exist_id(self) -> None:
        dbdict = await self.master.db.codebase_branches.get_branch(id=234)
        self.assertIsNone(dbdict)

    @async_to_deferred
    async def test_get_branches(self) -> None:
        branches = await self.master.db.codebase_branches.get_branches(codebaseid=13)
        branches = sorted(branches, key=lambda x: x.id)
        self.assertEqual(
            branches,
            [
                codebase_branches.CodebaseBranchModel(
                    id=200,
                    codebaseid=13,
                    name='branch1',
                    commitid=106,
                    last_timestamp=123456700,
                ),
                codebase_branches.CodebaseBranchModel(
                    id=201,
                    codebaseid=13,
                    name='branch2',
                    commitid=106,
                    last_timestamp=123456701,
                ),
                codebase_branches.CodebaseBranchModel(
                    id=202,
                    codebaseid=13,
                    name='branch3',
                    commitid=106,
                    last_timestamp=123456702,
                ),
            ],
        )

    @async_to_deferred
    async def test_update_branch(self) -> None:
        await self.master.db.codebase_branches.update_branch(
            codebaseid=13,
            name='branch1',
            commitid=107,
            last_timestamp=123456789,
        )
        dbdict = await self.master.db.codebase_branches.get_branch(id=200)
        self.assertEqual(
            dbdict,
            codebase_branches.CodebaseBranchModel(
                id=200,
                codebaseid=13,
                name='branch1',
                commitid=107,
                last_timestamp=123456789,
            ),
        )
