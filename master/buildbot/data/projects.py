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

from buildbot.data import base
from buildbot.data import types


def project_db_to_data(dbdict):
    return {
        "projectid": dbdict["id"],
        "name": dbdict["name"],
        "slug": dbdict["slug"],
        "description": dbdict["description"],
        "description_format": dbdict["description_format"],
        "description_html": dbdict["description_html"],
    }


class ProjectEndpoint(base.BuildNestingMixin, base.Endpoint):

    isCollection = False
    pathPatterns = """
        /projects/n:projectid
        /projects/i:projectname
    """

    @defer.inlineCallbacks
    def get(self, result_spec, kwargs):
        projectid = yield self.get_project_id(kwargs)
        if projectid is None:
            return None

        dbdict = yield self.master.db.projects.get_project(projectid)
        if not dbdict:
            return None
        return project_db_to_data(dbdict)


class ProjectsEndpoint(base.Endpoint):

    isCollection = True
    rootLinkName = 'projects'
    pathPatterns = """
        /projects
    """

    @defer.inlineCallbacks
    def get(self, result_spec, kwargs):
        dbdicts = yield self.master.db.projects.get_projects()
        return [project_db_to_data(dbdict) for dbdict in dbdicts]

    def get_kwargs_from_graphql(self, parent, resolve_info, args):
        return {}


class Project(base.ResourceType):

    name = "project"
    plural = "projects"
    endpoints = [ProjectEndpoint, ProjectsEndpoint]
    keyField = 'projectid'
    eventPathPatterns = """
        /projects/:projectid
    """
    subresources = ["Builder"]

    class EntityType(types.Entity):
        projectid = types.Integer()
        name = types.Identifier(70)
        slug = types.Identifier(70)
        description = types.NoneOk(types.String())
        description_format = types.NoneOk(types.String())
        description_html = types.NoneOk(types.String())
    entityType = EntityType(name, 'Project')

    @defer.inlineCallbacks
    def generate_event(self, _id, event):
        project = yield self.master.data.get(('projects', str(_id)))
        self.produceEvent(project, event)

    @base.updateMethod
    def find_project_id(self, name):
        return self.master.db.projects.find_project_id(name)

    @base.updateMethod
    @defer.inlineCallbacks
    def update_project_info(
        self,
        projectid,
        slug,
        description,
        description_format,
        description_html
    ):
        yield self.master.db.projects.update_project_info(
            projectid,
            slug,
            description,
            description_format,
            description_html
        )
        yield self.generate_event(projectid, "update")
