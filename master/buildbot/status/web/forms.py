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
import urllib
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

    def decodeFromURL(self, value, encoding):
        return urllib.unquote(value).decode(encoding)

    def content(self, request, cxt):
        status = self.getStatus(request)

        args = request.args.copy()

        # decode all of the args
        encoding = getRequestCharset(request)
        for name, argl in args.iteritems():
            if '_branch' in name:
                args[name] = [ self.decodeFromURL(arg, encoding) for arg in argl ]

        #Get builder info
        builder_status = None
        if args.has_key("builder_name") and len(args["builder_name"]) == 1:
            builder_status = status.getBuilder(self.decodeFromURL(args["builder_name"][0], encoding))
            bm = self.getBuildmaster(request)

            cxt['slaves'] = [s for s in builder_status.getSlaves() if s.isConnected()]

            #Get branches
            encoding = getRequestCharset(request)
            branches = [ b.decode(encoding) for b in args.get("branch", []) if b ]
            cxt['branches'] = branches

            # Add codebase info
            codebases = {}
            cxt['codebases_arg'] = codebases_arg = getCodebasesArg(request=request, codebases=codebases)

            return_page = ""
            if args.has_key("returnpage"):
                return_page = args['returnpage']
                if not isinstance(return_page, basestring):
                    return_page = args['returnpage'][0]

                if len(codebases_arg) > 0:
                    return_page = "&returnpage={0}".format(return_page)
                else:
                    return_page = "?returnpage={0}".format(return_page)

            cxt['return_page'] = return_page


            #Add scheduler info
            buildForceContext(cxt, request, self.getBuildmaster(request), builder_status.getName())

            cxt['force_url'] = args['datab'][0] + "/force" + codebases_arg + return_page
            cxt['rt_update'] = args
            request.args = args

            template = request.site.buildbot_service.templates.get_template("force_build_dialog.html")
            return template.render(**cxt)

        else:
            page = ErrorPage(INTERNAL_SERVER_ERROR, "Missing parameters", "Not all parameters were given")
            return page.render(request)
