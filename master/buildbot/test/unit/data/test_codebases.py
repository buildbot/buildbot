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

from buildbot.data import codebases
from buildbot.data import resultspec
from buildbot.master import BuildMaster
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import endpoint
from buildbot.test.util import interfaces
from buildbot.util.twisted import async_to_deferred


class CodebaseEndpoint(endpoint.EndpointMixin, unittest.TestCase):
    endpointClass = codebases.CodebaseEndpoint
    resourceTypeClass = codebases.Codebase

    @async_to_deferred
    async def setUp(self) -> None:  # type: ignore[override]
        await self.setUpEndpoint()
        await self.master.db.insert_test_data([
            fakedb.Project(id=7, name='fake_project7'),
            fakedb.Codebase(id=13, projectid=7, name='codebase1', slug='slug_codebase1'),
        ])

    @async_to_deferred
    async def test_get_existing_id(self) -> None:
        codebase = await self.callGet(('codebases', 13))

        self.validateData(codebase)
        self.assertEqual(
            codebase,
            {'codebaseid': 13, 'name': 'codebase1', 'projectid': 7, 'slug': 'slug_codebase1'},
        )

    @async_to_deferred
    async def test_get_missing(self) -> None:
        codebase = await self.callGet(('codebases', 100))
        self.assertIsNone(codebase)


class CodebasesEndpoint(endpoint.EndpointMixin, unittest.TestCase):
    endpointClass = codebases.CodebasesEndpoint
    resourceTypeClass = codebases.Codebase

    @async_to_deferred
    async def setUp(self) -> None:  # type: ignore[override]
        await self.setUpEndpoint()
        await self.master.db.insert_test_data([
            fakedb.Project(id=7, name='fake_project7'),
            fakedb.Project(id=8, name='fake_project8'),
            fakedb.Codebase(id=13, projectid=7, name='codebase1', slug='slug_codebase1'),
            fakedb.Codebase(id=14, projectid=7, name='codebase2'),
            fakedb.Codebase(id=15, projectid=8, name='codebase3'),
        ])

    @parameterized.expand([
        ('no_filter', None, [13, 14, 15]),
        ('existing', 7, [13, 14]),
        ('not_existing', 9, []),
    ])
    @async_to_deferred
    async def test_get(
        self, name: str, projectid_filter: int | None, expected_codebaseids: list[str]
    ) -> None:
        result_spec = None
        if projectid_filter is not None:
            result_spec = resultspec.OptimisedResultSpec(
                filters=[resultspec.Filter('projectid', 'eq', [projectid_filter])]
            )

        codebases = await self.callGet(('codebases',), resultSpec=result_spec)

        for b in codebases:
            self.validateData(b)

        self.assertEqual(sorted([b['codebaseid'] for b in codebases]), expected_codebaseids)


class Codebase(interfaces.InterfaceTests, TestReactorMixin, unittest.TestCase):
    @async_to_deferred
    async def setUp(self) -> None:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = await fakemaster.make_master(self, wantMq=True, wantDb=True, wantData=True)
        self.rtype = codebases.Codebase(cast(BuildMaster, self.master))
        await self.master.db.insert_test_data([
            fakedb.Project(id=7, name='fake_project7'),
            fakedb.Project(id=8, name='fake_project8'),
            fakedb.Codebase(id=13, projectid=7, name='codebase1', slug='slug_codebase1'),
        ])

    def test_signature_find_codebase_id(self) -> None:
        @self.assertArgSpecMatches(
            self.master.data.updates.find_codebase_id,
            self.rtype.find_codebase_id,
        )
        def find_codebase_id(
            self: Any,
            *,
            projectid: int,
            name: int,
            auto_create: bool = True,
        ) -> None:
            pass

    def test_signature_update_codebase_info(self) -> None:
        @self.assertArgSpecMatches(
            self.master.data.updates.update_codebase_info,
            self.rtype.update_codebase_info,
        )
        def update_codebase_info(
            self: Any,
            *,
            codebaseid: int,
            projectid: int,
            slug: str,
        ) -> None:
            pass

    @async_to_deferred
    async def test_update_find_codebase_id_exists(self) -> None:
        codebase_id = await self.master.data.updates.find_codebase_id(
            projectid=7,
            name='codebase1',
        )
        self.assertEqual(codebase_id, 13)

    @async_to_deferred
    async def test_update_find_codebase_id_new(self) -> None:
        codebase_id = await self.master.data.updates.find_codebase_id(
            projectid=8,
            name='codebase2',
        )
        codebase = await self.master.data.get(('codebases', codebase_id))
        self.assertEqual(
            codebase,
            {'codebaseid': codebase_id, 'name': 'codebase2', 'slug': 'codebase2', 'projectid': 8},
        )

    @async_to_deferred
    async def test_update_codebase_info(self) -> None:
        await self.master.data.updates.update_codebase_info(
            codebaseid=13,
            projectid=8,
            slug='new_slug',
        )
        codebases = await self.master.data.get(('codebases', 13))
        self.assertEqual(
            codebases,
            {'codebaseid': 13, 'name': 'codebase1', 'slug': 'new_slug', 'projectid': 8},
        )
