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

from unittest import mock

from parameterized import parameterized
from twisted.internet import defer
from twisted.trial import unittest

from buildbot.data import projects
from buildbot.data import resultspec
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import endpoint
from buildbot.test.util import interfaces


class ProjectEndpoint(endpoint.EndpointMixin, unittest.TestCase):
    endpointClass = projects.ProjectEndpoint
    resourceTypeClass = projects.Project

    @defer.inlineCallbacks
    def setUp(self):
        self.setUpEndpoint()
        yield self.db.insert_test_data([
            fakedb.Project(id=1, name='project1'),
            fakedb.Project(id=2, name='project2'),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    @defer.inlineCallbacks
    def test_get_existing_id(self):
        project = yield self.callGet(('projects', 2))

        self.validateData(project)
        self.assertEqual(project['name'], 'project2')

    @defer.inlineCallbacks
    def test_get_existing_name(self):
        project = yield self.callGet(('projects', 'project2'))

        self.validateData(project)
        self.assertEqual(project['name'], 'project2')

    @defer.inlineCallbacks
    def test_get_missing(self):
        project = yield self.callGet(('projects', 99))

        self.assertIsNone(project)

    @defer.inlineCallbacks
    def test_get_missing_with_name(self):
        project = yield self.callGet(('projects', 'project99'))

        self.assertIsNone(project)


class ProjectsEndpoint(endpoint.EndpointMixin, unittest.TestCase):
    endpointClass = projects.ProjectsEndpoint
    resourceTypeClass = projects.Project

    @defer.inlineCallbacks
    def setUp(self):
        self.setUpEndpoint()
        yield self.db.insert_test_data([
            fakedb.Project(id=1, name='project1'),
            fakedb.Project(id=2, name='project2'),
            fakedb.Project(id=3, name='project3'),
            fakedb.Master(id=100),
            fakedb.Builder(id=200, projectid=2),
            fakedb.Builder(id=201, projectid=3),
            fakedb.BuilderMaster(id=300, builderid=200, masterid=100),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    @parameterized.expand([
        ('no_filter', None, [1, 2, 3]),
        ('active', True, [2]),
        ('inactive', False, [1, 3]),
    ])
    @defer.inlineCallbacks
    def test_get(self, name, active_filter, expected_projectids):
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
    def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self, wantMq=True, wantDb=True, wantData=True)
        self.rtype = projects.Project(self.master)
        yield self.master.db.insert_test_data([
            fakedb.Project(id=13, name="fake_project"),
        ])

    def test_signature_find_project_id(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.find_project_id,  # fake
            self.rtype.find_project_id,
        )  # real
        def find_project_id(self, name):
            pass

    def test_find_project_id(self):
        # this just passes through to the db method, so test that
        rv = defer.succeed(None)
        self.master.db.projects.find_project_id = mock.Mock(return_value=rv)
        self.assertIdentical(self.rtype.find_project_id('foo'), rv)

    def test_signature_update_project_info(self):
        @self.assertArgSpecMatches(self.master.data.updates.update_project_info)
        def update_project_info(
            self, projectid, slug, description, description_format, description_html
        ):
            pass

    @defer.inlineCallbacks
    def test_update_project_info(self):
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
                {
                    "id": 13,
                    "name": "fake_project",
                    "slug": "slug13",
                    "description": "project13 desc",
                    "description_format": "format",
                    "description_html": "html desc",
                }
            ],
        )
