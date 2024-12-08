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
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin


def project_key(builder):
    return builder.id


class Tests(TestReactorMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantDb=True)
        self.db = self.master.db

    @defer.inlineCallbacks
    def test_update_project_info(self):
        yield self.db.insert_test_data([
            fakedb.Project(id=7, name='fake_project7'),
        ])

        yield self.db.projects.update_project_info(
            7, "slug7", "project7 desc", "format", "html desc"
        )
        dbdict = yield self.db.projects.get_project(7)
        self.assertIsInstance(dbdict, projects.ProjectModel)
        self.assertEqual(
            dbdict,
            projects.ProjectModel(
                id=7,
                name="fake_project7",
                slug="slug7",
                description="project7 desc",
                description_format="format",
                description_html="html desc",
            ),
        )

    @defer.inlineCallbacks
    def test_find_project_id_new(self):
        id = yield self.db.projects.find_project_id('fake_project')
        dbdict = yield self.db.projects.get_project(id)
        self.assertEqual(
            dbdict,
            projects.ProjectModel(
                id=id,
                name="fake_project",
                slug="fake_project",
                description=None,
                description_format=None,
                description_html=None,
            ),
        )

    @defer.inlineCallbacks
    def test_find_project_id_new_no_auto_create(self):
        id = yield self.db.projects.find_project_id('fake_project', auto_create=False)
        self.assertIsNone(id)

    @defer.inlineCallbacks
    def test_find_project_id_exists(self):
        yield self.db.insert_test_data([
            fakedb.Project(id=7, name='fake_project'),
        ])
        id = yield self.db.projects.find_project_id('fake_project')
        self.assertEqual(id, 7)

    @defer.inlineCallbacks
    def test_get_project(self):
        yield self.db.insert_test_data([
            fakedb.Project(id=7, name='fake_project'),
        ])
        dbdict = yield self.db.projects.get_project(7)
        self.assertIsInstance(dbdict, projects.ProjectModel)
        self.assertEqual(
            dbdict,
            projects.ProjectModel(
                id=7,
                name="fake_project",
                slug="fake_project",
                description=None,
                description_format=None,
                description_html=None,
            ),
        )

    @defer.inlineCallbacks
    def test_get_project_missing(self):
        dbdict = yield self.db.projects.get_project(7)
        self.assertIsNone(dbdict)

    @defer.inlineCallbacks
    def test_get_projects(self):
        yield self.db.insert_test_data([
            fakedb.Project(id=7, name="fake_project7"),
            fakedb.Project(id=8, name="fake_project8"),
            fakedb.Project(id=9, name="fake_project9"),
        ])
        dblist = yield self.db.projects.get_projects()
        for dbdict in dblist:
            self.assertIsInstance(dbdict, projects.ProjectModel)
        self.assertEqual(
            sorted(dblist, key=project_key),
            sorted(
                [
                    projects.ProjectModel(
                        id=7,
                        name="fake_project7",
                        slug="fake_project7",
                        description=None,
                        description_format=None,
                        description_html=None,
                    ),
                    projects.ProjectModel(
                        id=8,
                        name="fake_project8",
                        slug="fake_project8",
                        description=None,
                        description_format=None,
                        description_html=None,
                    ),
                    projects.ProjectModel(
                        id=9,
                        name="fake_project9",
                        slug="fake_project9",
                        description=None,
                        description_format=None,
                        description_html=None,
                    ),
                ],
                key=project_key,
            ),
        )

    @defer.inlineCallbacks
    def test_get_projects_empty(self):
        dblist = yield self.db.projects.get_projects()
        self.assertEqual(dblist, [])

    @defer.inlineCallbacks
    def test_get_active_projects(self):
        yield self.db.insert_test_data([
            fakedb.Project(id=1, name='fake_project1'),
            fakedb.Project(id=2, name='fake_project2'),
            fakedb.Project(id=3, name='fake_project3'),
            fakedb.Master(id=100),
            fakedb.Builder(id=200, name="builder_200", projectid=2),
            fakedb.Builder(id=201, name="builder_201", projectid=3),
            fakedb.BuilderMaster(id=300, builderid=200, masterid=100),
        ])
        dblist = yield self.db.projects.get_active_projects()
        for dbdict in dblist:
            self.assertIsInstance(dbdict, projects.ProjectModel)
        self.assertEqual(
            dblist,
            [
                projects.ProjectModel(
                    id=2,
                    name="fake_project2",
                    slug="fake_project2",
                    description=None,
                    description_format=None,
                    description_html=None,
                )
            ],
        )
