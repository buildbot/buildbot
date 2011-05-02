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

from twisted.web.util import redirectTo

from buildbot.status.web.base import HtmlResource, path_to_authfail
from buildbot.util.eventual import eventually

class RootPage(HtmlResource):
    pageTitle = "Buildbot"

    def content(self, request, cxt):
        status = self.getStatus(request)

        if request.path == '/shutdown':
            if self.getAuthz(request).actionAllowed("cleanShutdown", request):
                eventually(status.cleanShutdown)
                return redirectTo("/", request)
            else:
                return redirectTo(path_to_authfail(request), request)
        elif request.path == '/cancel_shutdown':
            if self.getAuthz(request).actionAllowed("cleanShutdown", request):
                eventually(status.cancelCleanShutdown)
                return redirectTo("/", request)
            else:
                return redirectTo(path_to_authfail(request), request)

        cxt.update(
                shutting_down = status.shuttingDown,
                shutdown_url = request.childLink("shutdown"),
                cancel_shutdown_url = request.childLink("cancel_shutdown"),
                )
        template = request.site.buildbot_service.templates.get_template("root.html")
        return template.render(**cxt)
