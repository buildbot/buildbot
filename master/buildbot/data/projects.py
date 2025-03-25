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

from twisted.internet import defer

from buildbot.data import base
from buildbot.data import types

if TYPE_CHECKING:
    from buildbot.db.projects import ProjectModel


def project_db_to_data(model: ProjectModel, active=None):
    return {
        "projectid": model.id,
        "name": model.name,
        "slug": model.slug,
        "description": model.description,
        "description_format": model.description_format,
        "description_html": model.description_html,
        "active": active,
    }


class ProjectEndpoint(base.BuildNestingMixin, base.Endpoint):
    kind = base.EndpointKind.SINGLE
    pathPatterns = [
        "/projects/n:projectid",
        "/projects/i:projectname",
    ]

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
    kind = base.EndpointKind.COLLECTION
    rootLinkName = 'projects'
    pathPatterns = [
        "/projects",
    ]

    @defer.inlineCallbacks
    def get(self, result_spec, kwargs):
        active = result_spec.popBooleanFilter("active")
        if active is None:
            dbdicts = yield self.master.db.projects.get_projects()
        elif active:
            dbdicts = yield self.master.db.projects.get_active_projects()
        else:
            # This is not optimized case which is assumed to be infrequently required
            dbdicts_all = yield self.master.db.projects.get_projects()
            dbdicts_active = yield self.master.db.projects.get_active_projects()
            ids_active = set(dbdict.id for dbdict in dbdicts_active)
            dbdicts = [dbdict for dbdict in dbdicts_all if dbdict.id not in ids_active]

        return [project_db_to_data(dbdict, active=active) for dbdict in dbdicts]


class Project(base.ResourceType):
    name = "project"
    plural = "projects"
    endpoints = [ProjectEndpoint, ProjectsEndpoint]
    eventPathPatterns = [
        "/projects/:projectid",
    ]

    class EntityType(types.Entity):
        projectid = types.Integer()
        name = types.Identifier(70)
        slug = types.Identifier(70)
        active = types.NoneOk(types.Boolean())
        description = types.NoneOk(types.String())
        description_format = types.NoneOk(types.String())
        description_html = types.NoneOk(types.String())

    entityType = EntityType(name)

    @defer.inlineCallbacks
    def generate_event(self, _id, event):
        project = yield self.master.data.get(('projects', str(_id)))
        self.produceEvent(project, event)

    @base.updateMethod
    def find_project_id(self, name: str, auto_create: bool = True):
        return self.master.db.projects.find_project_id(name, auto_create)

    @base.updateMethod
    @defer.inlineCallbacks
    def update_project_info(
        self,
        projectid: int,
        slug: str,
        description: str | None,
        description_format: str | None,
        description_html: str | None,
    ):
        yield self.master.db.projects.update_project_info(
            projectid, slug, description, description_format, description_html
        )
        yield self.generate_event(projectid, "update")
