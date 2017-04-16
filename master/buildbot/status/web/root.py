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
from twisted.web.util import redirectTo

from buildbot.status.web.base import HtmlResource
from buildbot.status.web.base import path_to_authzfail
from buildbot.util.eventual import eventually


class RootPage(HtmlResource):
    pageTitle = "Buildbot"

    @defer.inlineCallbacks
    def content(self, request, cxt):
        status = self.getStatus(request)

        repos = ['git://github.com/MariaDB/server', 'git@github.com:mariadb-corporation/MariaDBEnterprise.git']
        cmds = ['git ls-remote --heads ' + repo + ' | grep -v "\^" | sed s/".*refs\/heads\/"//g' for repo in repos]
        all_branches = os.popen(" && ".join(cmds), 'r', 1).readlines()

        cxt['waterfall_branches'] = all_branches
        cxt['grid_branches'] = all_branches
        cxt['important_branches'] = ["5.5", "10.0", "5.5e", "10.0e"]


        res = yield self.getAuthz(request).actionAllowed("cleanShutdown",
                                                         request)

        if request.path == '/shutdown':
            if res:
                eventually(status.cleanShutdown)
                defer.returnValue(redirectTo("/", request))
                return
            else:
                defer.returnValue(
                    redirectTo(path_to_authzfail(request), request))
                return
        elif request.path == '/cancel_shutdown':
            if res:
                eventually(status.cancelCleanShutdown)
                defer.returnValue(redirectTo("/", request))
                return
            else:
                defer.returnValue(
                    redirectTo(path_to_authzfail(request), request))
                return

        cxt.update(
            shutting_down=status.shuttingDown,
            shutdown_url=request.childLink("shutdown"),
            cancel_shutdown_url=request.childLink("cancel_shutdown"),
        )
        template = request.site.buildbot_service.templates.get_template("root.html")
        defer.returnValue(template.render(**cxt))
