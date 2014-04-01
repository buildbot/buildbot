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
from twisted.internet import defer
import types
import urllib

class ProjectsResource(HtmlResource):
    pageTitle = "Katana - Projects"

    def content(self, req, cxt):
        status = self.getStatus(req)

        projects = req.args.get("projects", status.getProjects())
        cxt['projects'] = []
        if len(projects) > 0:
            cxt['projects'] = util.naturalSort(projects.keys())
            
            cxt['projects_codebases'] = status.getProjects() 

        project_shortcut = {}
        for key, value in projects.iteritems():
            project_path= urllib.quote(key, safe='') + "/builders"

            for cb in value.codebases:
                if '?' not in project_path:
                    project_path += '?'
                for cbkey,cbvalue in cb.iteritems():
                    if '=' in project_path:
                        project_path += "&"

                    project_path += urllib.quote(cbkey, safe='') + "_branch"

                    if 'defaultbranch' in cbvalue.keys():
                        branch =  cbvalue['defaultbranch']
                    else:
                        branch = cbvalue['branch']

                    if not isinstance(cbvalue['branch'], types.ListType):
                        project_path += "=" + urllib.quote(branch, safe='')
                    else:
                        if len(branch) > 0:
                            project_path += "=" + urllib.quote(branch[0], safe='')

            project_shortcut[key] = project_path

        cxt['project_shortcut'] = project_shortcut
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

    @defer.inlineCallbacks
    def content(self, request, cxt):
        master = request.site.buildbot_service.master
        repositories = []
        for cb in self.project.codebases:
            for key,value in cb.iteritems():
                repositories.append(value['repository'])
                if not isinstance(value['branch'], types.ListType):
                    value['branch'] = [value['branch']]
                if 'defaultbranch' not in value.keys():
                    value['defaultbranch'] = value['branch']

        branches = yield master.db.state.getObjectState(repositories)

        if len(branches) > 0:
            for cb in self.project.codebases:
                for key, value in cb.iteritems():
                    if value['repository'] in branches.keys():
                        value['branch'] = util.naturalSort(branches[value['repository']])

        cxt['codebases'] = self.project.codebases
        cxt['selectedproject'] = self.project.name
        template = request.site.buildbot_service.templates.get_template("project.html")
        template.autoescape = True
        defer.returnValue(template.render(**cxt))

    def getChild(self, path, req):
        if path == "builders":
            return BuildersResource(self.project)
        return HtmlResource.getChild(self, path, req)


