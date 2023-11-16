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

from buildbot.test.fakedb.base import FakeDBComponent
from buildbot.test.fakedb.row import Row


class Project(Row):
    table = "projects"

    id_column = 'id'
    hashedColumns = [('name_hash', ('name',))]

    def __init__(
        self,
        id=None,
        name='fake_project',
        name_hash=None,
        slug=None,
        description=None,
        description_format=None,
        description_html=None,
    ):
        if slug is None:
            slug = name
        super().__init__(
            id=id,
            name=name,
            name_hash=name_hash,
            slug=slug,
            description=description,
            description_format=description_format,
            description_html=description_html
        )


class FakeProjectsComponent(FakeDBComponent):

    def setUp(self):
        self.projects = {}

    def insert_test_data(self, rows):
        for row in rows:
            if isinstance(row, Project):
                self.projects[row.id] = {
                    "id": row.id,
                    "name": row.name,
                    "slug": row.slug,
                    "description": row.description,
                    "description_format": row.description_format,
                    "description_html": row.description_html,
                }

    # Returns Deferred that yields a number
    def find_project_id(self, name, auto_create=True):
        for m in self.projects.values():
            if m['name'] == name:
                return defer.succeed(m['id'])
        if not auto_create:
            return defer.succeed(None)
        id = len(self.projects) + 1
        self.projects[id] = {
            "id": id,
            "name": name,
            "slug": name,
            "description": None,
            "description_format": None,
            "description_html": None,
        }
        return defer.succeed(id)

    def get_project(self, projectid):
        if projectid in self.projects:
            return defer.succeed(self._row2dict(self.projects[projectid]))
        return defer.succeed(None)

    def get_projects(self):
        rv = []
        for project in self.projects.values():
            rv.append(self._row2dict(project))
        return rv

    def get_active_projects(self):
        rv = []

        active_builderids = {
            builderid for builderid, _ in self.db.builders.builder_masters.values()
        }

        active_projectids = {
            builder["projectid"] for id, builder in self.db.builders.builders.items()
            if id in active_builderids
        }

        for id, project in self.projects.items():
            if id not in active_projectids:
                continue
            rv.append(self._row2dict(project))
        return rv

    def update_project_info(
        self,
        projectid,
        slug,
        description,
        description_format,
        description_html
    ):
        if projectid not in self.projects:
            return defer.succeed(None)
        project = self.projects[projectid]
        project['slug'] = slug
        project['description'] = description
        project["description_format"] = description_format
        project["description_html"] = description_html
        return defer.succeed(None)

    def _row2dict(self, row):
        return row.copy()
