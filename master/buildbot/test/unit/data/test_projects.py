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

from typing import TYPE_CHECKING
from unittest import mock

from parameterized import parameterized
from twisted.internet import defer
from twisted.trial import unittest

from buildbot.data import projects
from buildbot.data import resultspec
from buildbot.db.projects import ProjectModel
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import endpoint
from buildbot.test.util import interfaces

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class ProjectEndpoint(endpoint.EndpointMixin, unittest.TestCase):
    endpointClass = projects.ProjectEndpoint
    resourceTypeClass = projects.Project

    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        yield self.setUpEndpoint()
        yield self.master.db.insert_test_data([
            fakedb.Project(id=1, name='project1'),
            fakedb.Project(id=2, name='project2'),
        ])

    @defer.inlineCallbacks
    def test_get_existing_id(self) -> InlineCallbacksType[None]:
        project = yield self.callGet(('projects', 2))

        self.validateData(project)
        self.assertEqual(project['name'], 'project2')

    @defer.inlineCallbacks
    def test_get_existing_name(self) -> InlineCallbacksType[None]:
        project = yield self.callGet(('projects', 'project2'))

        self.validateData(project)
        self.assertEqual(project['name'], 'project2')

    @defer.inlineCallbacks
    def test_get_missing(self) -> InlineCallbacksType[None]:
        project = yield self.callGet(('projects', 99))

        self.assertIsNone(project)

    @defer.inlineCallbacks
    def test_get_missing_with_name(self) -> InlineCallbacksType[None]:
        project = yield self.callGet(('projects', 'project99'))

        self.assertIsNone(project)


class ProjectsEndpoint(endpoint.EndpointMixin, unittest.TestCase):
    endpointClass = projects.ProjectsEndpoint
    resourceTypeClass = projects.Project

    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        yield self.setUpEndpoint()
        yield self.master.db.insert_test_data([
            fakedb.Project(id=1, name='project1'),
            fakedb.Project(id=2, name='project2'),
            fakedb.Project(id=3, name='project3'),
            fakedb.Master(id=100),
            fakedb.Builder(id=200, projectid=2),
            fakedb.Builder(id=201, projectid=3),
            fakedb.BuilderMaster(id=300, builderid=200, masterid=100),
        ])

    @parameterized.expand([
        ('no_filter', None, [1, 2, 3]),
        ('active', True, [2]),
        ('inactive', False, [1, 3]),
    ])
    @defer.inlineCallbacks
    def test_get(
        self, name: str, active_filter: bool | None, expected_projectids: list[int]
    ) -> InlineCallbacksType[None]:
        result_spec = None
        if active_filter is not None:
            result_spec = resultspec.OptimisedResultSpec(
                filters=[resultspec.Filter('active', 'eq', [active_filter])]
            )

        projects = yield self.callGet(('projects',), resultSpec=result_spec)

        for b in projects:
            self.validateData(b)

        self.assertEqual(sorted([b['projectid'] for b in projects]), expected_projectids)


class Project(interfaces.InterfaceTests, TestReactorMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantMq=True, wantDb=True, wantData=True)
        self.rtype = projects.Project(self.master)
        yield self.master.db.insert_test_data([
            fakedb.Project(id=13, name="fake_project"),
        ])

    def test_signature_find_project_id(self) -> None:
        @self.assertArgSpecMatches(
            self.master.data.updates.find_project_id,  # fake
            self.rtype.find_project_id,
        )  # real
        def find_project_id(self: object, name: str, auto_create: bool = True) -> None:
            pass

    def test_find_project_id(self) -> None:
        # this just passes through to the db method, so test that
        rv = defer.succeed(None)
        self.master.db.projects.find_project_id = mock.Mock(return_value=rv)
        self.assertIdentical(self.rtype.find_project_id('foo'), rv)

    def test_signature_update_project_info(self) -> None:
        @self.assertArgSpecMatches(self.master.data.updates.update_project_info)
        def update_project_info(
            self: object,
            projectid: int,
            slug: str,
            description: str | None,
            description_format: str | None,
            description_html: str | None,
        ) -> None:
            pass

    @defer.inlineCallbacks
    def test_update_project_info(self) -> InlineCallbacksType[None]:
        yield self.master.data.updates.update_project_info(
            13,
            "slug13",
            "project13 desc",
            "format",
            "html desc",
        )
        projects = yield self.master.db.projects.get_projects()
        self.assertEqual(
            projects,
            [
                ProjectModel(
                    id=13,
                    name="fake_project",
                    slug="slug13",
                    description="project13 desc",
                    description_format="format",
                    description_html="html desc",
                )
            ],
        )
