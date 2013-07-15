# This file is part of Buildbot.  Buildbot is free software: you can
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


from buildbot.status.web.base import HtmlResource
from buildbot.status.web.builder import BuildersResource
from buildbot import util

class ProjectsResource(HtmlResource):
    pageTitle = "Katana - Projects"

    def content(self, req, cxt):
        status = self.getStatus(req)

        projects = req.args.get("projects", status.getProjects())
        cxt['projects'] = []
        if len(projects) > 0:
            cxt['projects'] = util.naturalSort(projects.keys())

        template = req.site.buildbot_service.templates.get_template("projects.html")
        template.autoescape = True
        return template.render(**cxt)

    def getChild(self, path, req):
        status = self.getStatus(req)
        projects = status.getProjects()

        if path in projects:
            return CodeBasesResource(projects[path])
        return HtmlResource.getChild(self, path, req)
    

class CodeBasesResource(HtmlResource):
    pageTitle = "Katana - Codebases"

    def __init__(self, project):
        HtmlResource.__init__(self)
        self.project = project

    def content(self, request, cxt):
        cxt['codebases'] = self.project.codebases
        cxt['selectedproject'] = self.project.name
        template = request.site.buildbot_service.templates.get_template("codebases.html")
        template.autoescape = True
        return template.render(**cxt)

    def getChild(self, path, req):
        if path == "builders":
            return BuildersResource(self.project)
        return HtmlResource.getChild(self, path, req)


