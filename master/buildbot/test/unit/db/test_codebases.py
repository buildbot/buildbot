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

from buildbot.db import codebases
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
            fakedb.Project(id=8, name='fake_project8'),
            fakedb.Codebase(id=13, projectid=7, name='codebase1', slug='slug_codebase1'),
            fakedb.Codebase(id=14, projectid=7, name='codebase2'),
            fakedb.Codebase(id=15, projectid=7, name='codebase3'),
        ])

    @async_to_deferred
    async def test_find_codebase_id_exists(self) -> None:
        id = await self.master.db.codebases.find_codebase_id(projectid=7, name='codebase1')
        self.assertEqual(id, 13)

    @async_to_deferred
    async def test_find_codebase_id_new_no_auto_create(self) -> None:
        id = await self.master.db.codebases.find_codebase_id(
            projectid=7, name='codebase_not_exist', auto_create=False
        )
        self.assertIsNone(id)

    @async_to_deferred
    async def test_find_codebase_id_new(self) -> None:
        id = await self.master.db.codebases.find_codebase_id(projectid=7, name='codebase_not_exist')
        codebase = await self.master.db.codebases.get_codebase(id)
        self.assertEqual(
            codebase,
            codebases.CodebaseModel(
                id=id, projectid=7, name='codebase_not_exist', slug='codebase_not_exist'
            ),
        )

    @async_to_deferred
    async def test_get_codebase_exists(self) -> None:
        dbdict = await self.master.db.codebases.get_codebase(13)
        self.assertEqual(
            dbdict,
            codebases.CodebaseModel(id=13, projectid=7, name='codebase1', slug='slug_codebase1'),
        )

    @async_to_deferred
    async def test_get_codebase_does_not_exist(self) -> None:
        dbdict = await self.master.db.codebases.get_codebase(100)
        self.assertIsNone(dbdict)

    @async_to_deferred
    async def test_get_codebases(self) -> None:
        values = await self.master.db.codebases.get_codebases(projectid=7)
        values = sorted(values, key=lambda c: c.id)
        self.assertEqual(
            values,
            [
                codebases.CodebaseModel(
                    id=13, projectid=7, name='codebase1', slug='slug_codebase1'
                ),
                codebases.CodebaseModel(id=14, projectid=7, name='codebase2', slug='codebase2'),
                codebases.CodebaseModel(id=15, projectid=7, name='codebase3', slug='codebase3'),
            ],
        )

    @async_to_deferred
    async def test_update_codebase_info(self) -> None:
        await self.master.db.codebases.update_codebase_info(
            codebaseid=13, projectid=8, slug='new_slug'
        )
        dbdict = await self.master.db.codebases.get_codebase(13)
        self.assertEqual(
            dbdict,
            codebases.CodebaseModel(
                id=13,
                projectid=8,
                name="codebase1",
                slug="new_slug",
            ),
        )
