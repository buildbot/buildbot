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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.db import projects
from buildbot.test import fakedb
from buildbot.test.util import connector_component
from buildbot.test.util import interfaces
from buildbot.test.util import validation


def project_key(builder):
    return builder['id']


class Tests(interfaces.InterfaceTests):

    def test_signature_find_project_id(self):
        @self.assertArgSpecMatches(self.db.projects.find_project_id)
        def find_project_id(self, name, auto_create=True):
            pass

    def test_signature_get_project(self):
        @self.assertArgSpecMatches(self.db.projects.get_project)
        def get_project(self, projectid):
            pass

    def test_signature_get_projects(self):
        @self.assertArgSpecMatches(self.db.projects.get_projects)
        def get_projects(self):
            pass

    def test_signature_update_project_info(self):
        @self.assertArgSpecMatches(self.db.projects.update_project_info)
        def update_project_info(self, projectid, slug, description):
            pass

    @defer.inlineCallbacks
    def test_update_project_info(self):
        yield self.insert_test_data([
            fakedb.Project(id=7, name='fake_project7'),
        ])

        yield self.db.projects.update_project_info(7, 'slug7', 'project7 desc')
        dbdict = yield self.db.projects.get_project(7)
        validation.verifyDbDict(self, 'projectdict', dbdict)
        self.assertEqual(dbdict, {
            "id": 7,
            "name": "fake_project7",
            "slug": "slug7",
            "description": "project7 desc",
        })

    @defer.inlineCallbacks
    def test_find_project_id_new(self):
        id = yield self.db.projects.find_project_id('fake_project')
        dbdict = yield self.db.projects.get_project(id)
        self.assertEqual(dbdict, {
            "id": id,
            "name": "fake_project",
            "slug": "fake_project",
            "description": None,
        })

    @defer.inlineCallbacks
    def test_find_project_id_new_no_auto_create(self):
        id = yield self.db.projects.find_project_id('fake_project', auto_create=False)
        self.assertIsNone(id)

    @defer.inlineCallbacks
    def test_find_project_id_exists(self):
        yield self.insert_test_data([
            fakedb.Project(id=7, name='fake_project'),
        ])
        id = yield self.db.projects.find_project_id('fake_project')
        self.assertEqual(id, 7)

    @defer.inlineCallbacks
    def test_get_project(self):
        yield self.insert_test_data([
            fakedb.Project(id=7, name='fake_project'),
        ])
        dbdict = yield self.db.projects.get_project(7)
        validation.verifyDbDict(self, 'projectdict', dbdict)
        self.assertEqual(dbdict, {
            "id": 7,
            "name": "fake_project",
            "slug": "fake_project",
            "description": None,
        })

    @defer.inlineCallbacks
    def test_get_project_missing(self):
        dbdict = yield self.db.projects.get_project(7)
        self.assertIsNone(dbdict)

    @defer.inlineCallbacks
    def test_get_projects(self):
        yield self.insert_test_data([
            fakedb.Project(id=7, name="fake_project7"),
            fakedb.Project(id=8, name="fake_project8"),
            fakedb.Project(id=9, name="fake_project9"),
        ])
        dblist = yield self.db.projects.get_projects()
        for dbdict in dblist:
            validation.verifyDbDict(self, 'projectdict', dbdict)
        self.assertEqual(sorted(dblist, key=project_key), sorted([
            {
                "id": 7,
                "name": "fake_project7",
                "slug": "fake_project7",
                "description": None,
            },
            {
                "id": 8,
                "name": "fake_project8",
                "slug": "fake_project8",
                "description": None,
            },
            {
                "id": 9,
                "name": "fake_project9",
                "slug": "fake_project9",
                "description": None,
            },
        ], key=project_key))

    @defer.inlineCallbacks
    def test_get_projects_empty(self):
        dblist = yield self.db.projects.get_projects()
        self.assertEqual(dblist, [])


class RealTests(Tests):

    # tests that only "real" implementations will pass

    pass


class TestFakeDB(unittest.TestCase, connector_component.FakeConnectorComponentMixin, Tests):

    @defer.inlineCallbacks
    def setUp(self):
        yield self.setUpConnectorComponent()


class TestRealDB(unittest.TestCase,
                 connector_component.ConnectorComponentMixin,
                 RealTests):

    @defer.inlineCallbacks
    def setUp(self):
        yield self.setUpConnectorComponent(table_names=['projects'])

        self.db.projects = projects.ProjectsConnectorComponent(self.db)
        self.master = self.db.master
        self.master.db = self.db

    def tearDown(self):
        return self.tearDownConnectorComponent()
