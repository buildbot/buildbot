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

class ProjectsResource(HtmlResource):
    pageTitle = "Katana - Projects"

    def content(self, req, cxt):
        template = req.site.buildbot_service.templates.get_template("projects.html")
        template.autoescape = True
        return template.render(**cxt)

    def getChild(self, path, req):
        if path == "codebases":
            return CodeBasesResource()
    

class CodeBasesResource(HtmlResource):
    pageTitle = "Katana - Codebases"

    def content(self, request, cxt):
        template = request.site.buildbot_service.templates.get_template("codebases.html")
        template.autoescape = True
        return template.render(**cxt)

    def getChild(self, path, req):
        if path == "builders":
            return BuildersResource()


