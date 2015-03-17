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
import copy
import json
from operator import attrgetter

from buildbot.status.web.base import HtmlResource, path_to_codebases, path_to_json_builders, path_to_comparison
from buildbot.status.web.builder import BuildersResource
from buildbot import util
from twisted.internet import defer
import types
import urllib
from buildbot.status.web.status_json import SingleProjectJsonResource


class ProjectsResource(HtmlResource):
    pageTitle = "Katana - Projects"

    def __init__(self, numbuilds=20):
        HtmlResource.__init__(self)
        self.numbuilds = numbuilds

    def content(self, req, cxt):
        status = self.getStatus(req)

        projects = req.args.get("projects", status.getProjects())
        project_objs = [status.master.getProject(p) for p in projects]
        cxt['projects'] = []
        if len(projects) > 0:
            project_objs = sorted(project_objs, key=attrgetter('priority', 'name'))
            cxt['projects'] = [p.name for p in project_objs]

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
            return CodeBasesResource(projects[path], self.numbuilds)
        return HtmlResource.getChild(self, path, req)
    

class CodeBasesResource(HtmlResource):
    pageTitle = "Katana - Codebases"

    def __init__(self, project, numbuilds=15):
        HtmlResource.__init__(self)
        self.project = project
        self.numbuilds = numbuilds

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
            return BuildersResource(self.project, self.numbuilds)
        elif path == "comparison":
            return BranchComparisonResource(self.project, self.numbuilds)

        return HtmlResource.getChild(self, path, req)


# /builders/$project/comparison?branch_1=$branch1&branch_2=$branch2
class BranchComparisonResource(HtmlResource):
    pageTitle = "Katana - Branch Comparison"

    def __init__(self, project, numbuilds=15):
        HtmlResource.__init__(self)
        self.project = project
        self.numbuilds = numbuilds

    @defer.inlineCallbacks
    def content(self, request, cxt):
        master = request.site.buildbot_service.master
        status = self.getStatus(request)
        comparison_info = {
            "builders0": {
                "codebases": {},
                "output": []
            },
            "builders1": {
                "codebases": {},
                "output": []
            }
        }

        # Get codebases/branch info
        repositories = []
        for cb in self.project.codebases:
            for key, value in cb.iteritems():
                repositories.append(value['repository'])
                if not isinstance(value['branch'], types.ListType):
                    value['branch'] = [value['branch']]
                if 'defaultbranch' not in value.keys():
                    value['defaultbranch'] = value['branch']

        branches = yield master.db.state.getObjectState(repositories)

        if len(branches) > 0:
            for cb in self.project.codebases:
                for key, value in cb.iteritems():

                    # Set the default branches on each of the codebases
                    comparison_info["builders0"]["codebases"][key] = \
                        comparison_info["builders1"]["codebases"][key] = value['defaultbranch']

                    if value['repository'] in branches.keys():
                        value['branch'] = util.naturalSort(branches[value['repository']])

        def set_instant_json(json_name, cmp_info):
            # Create our instant json for the given builders
            for bName, branch in cmp_info["codebases"].iteritems():
                request.args[bName + "_branch"] = branch

            url = status.getBuildbotURL() + path_to_json_builders(request, self.project.name)

            # Remove the extra array we don't need for autobahn
            sources = {}
            for n, src in cmp_info["codebases"].iteritems():
                sources[n] = src[0]

            filters = {
                "project": self.project.name,
                "sources": sources
            }

            cxt['instant_json'][json_name] = \
                {
                    "url": url,
                    "data": json.dumps(cmp_info["output"], separators=(',', ':')),
                    "waitForPush": status.master.config.autobahn_push,
                    "pushFilters": {
                        "buildFinished": filters,
                    }
                }

            # Remove from the object as we no longer need these values
            del cmp_info["output"]

        # Get build data for each branch
        for name, obj in comparison_info.iteritems():

            # Set branches based on url args
            args = request.args.get(name, None)
            if args is not None:
                split = urllib.unquote(args[0]).split("&")
                for s in split:
                    branch_info = s.split("=")
                    if len(branch_info) == 2:
                        branch_name = branch_info[0].replace("_branch", "")
                        obj["codebases"][branch_name] = [branch_info[1]]

            # Create a copy of the request to pass around with the updated codebases info
            for bName, branch in obj["codebases"].iteritems():
                request.args[bName + "_branch"] = branch

            # Create our json
            j = SingleProjectJsonResource(status, self.project)
            builds = yield j.asDict(request)
            obj["output"] = builds["builders"]

        # Set the instant json for each of the comparison branches
        for name, obj in comparison_info.iteritems():
            set_instant_json(name, obj)

        # Remove the extra array in our codebases
        tmp_codebases = {}
        for c in self.project.codebases:
            for name, cb in c.iteritems():
                tmp_codebases[name] = cb

        codebases_json = {
            "codebases": tmp_codebases,
            "defaults": comparison_info,
            "url": path_to_comparison(request, self.project.name)
        }

        cxt['instant_json']['codebases'] = {"data": json.dumps(codebases_json, separators=(',', ':'))}
        cxt['path_to_codebases'] = path_to_codebases(request, self.project.name)
        cxt['selectedproject'] = self.project.name
        template = request.site.buildbot_service.templates.get_template("branch_comparison.html")
        template.autoescape = True
        defer.returnValue(template.render(**cxt))

    def getChild(self, path, req):
        if path == "builders":
            return BuildersResource(self.project, self.numbuilds)
        return HtmlResource.getChild(self, path, req)
