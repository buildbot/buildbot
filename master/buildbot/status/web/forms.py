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
from twisted.web._responses import INTERNAL_SERVER_ERROR
from twisted.web.resource import ErrorPage

from buildbot.status.web.builder import buildForceContext
from buildbot.status.web.base import HtmlResource, getCodebasesArg, getRequestCharset


class FormsKatanaResource(HtmlResource):
    pageTitle = "Katana - Forms"

    def content(self, request, cxt):
        cxt.update(content = "<h1>Page not found.</h1>")
        template = request.site.buildbot_service.templates.get_template("empty.html")
        return template.render(**cxt)

    def getChild(self, path, req):
        if path == "forceBuild":
            return ForceBuildDialogPage()


class ForceBuildDialogPage(HtmlResource):
    pageTitle = "Force Build"

    def content(self, request, cxt):
        status = self.getStatus(request)

        #Get builder info
        builder_status = None
        if request.args.has_key("builder_name") and len(request.args["builder_name"]) == 1:
            builder_status = status.getBuilder(request.args["builder_name"][0])
            bm = self.getBuildmaster(request)
            builder = None
            for b in bm.botmaster.getBuilders():
                if b.name == builder_status.getName():
                    builder = b

            if builder:
                slaves = []
                for b in builder.getAvailableSlaveBuilders(checkCanStartBuild=False):
                    slaves.append(b.slave.slave_status)
                cxt['slaves'] = slaves
            else:
                cxt['slaves'] = builder_status.getSlaves()


            #Get branches
            encoding = getRequestCharset(request)
            branches = [ b.decode(encoding) for b in request.args.get("branch", []) if b ]
            cxt['branches'] = branches

            # Add codebase info
            codebases = {}
            codebases_arg = getCodebasesArg(request=request, codebases=codebases)
            cxt['codebases_arg'] = codebases_arg

            #Add scheduler info
            buildForceContext(cxt, request, self.getBuildmaster(request), builder_status.getName())
            cxt['fbuildsch'] = request.args
            cxt['rt_update'] = request.args

            template = request.site.buildbot_service.templates.get_template("force_build_dialog.html")
            return template.render(**cxt)

        else:
            page = ErrorPage(INTERNAL_SERVER_ERROR, "Missing parameters", "Not all parameters were given")
            return page.render(request)
