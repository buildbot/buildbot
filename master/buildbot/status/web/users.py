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
from twisted.internet import defer
from twisted.web.util import redirectTo
from buildbot.status.web.base import HtmlResource, path_to_authfail, \
    path_to_root, ActionResource

class UsersActionResource(ActionResource):

    def __init__(self):
        self.action = "showUsersPage"

    @defer.deferredGenerator
    def performAction(self, req):
        d = self.getAuthz(req).actionAllowed('showUsersPage', req)
        wfd = defer.waitForDeferred(d)
        yield wfd
        res = wfd.getResult()
        if not res:
            yield path_to_authfail(req)
            return
        # show the table
        yield path_to_root(req) + "users/table"

# /users/$uid
class OneUserResource(HtmlResource):
    addSlash = False
    def __init__(self, uid):
        HtmlResource.__init__(self)
        self.uid = int(uid)

    def getPageTitle (self, req):
        return "Buildbot User: %s" % self.uid

    def content(self, request, ctx):
        status = self.getStatus(request)

        d = status.master.db.users.getUser(self.uid)
        def cb(usdict):
            ctx['user_identifier'] = usdict['identifier']
            user = ctx['user'] = {}
            for attr in usdict:
                if attr not in ['uid', 'identifier', 'bb_password']:
                    user[attr] = usdict[attr]

            template = request.site.buildbot_service.templates.get_template("user.html")
            data = template.render(**ctx)
            return data
        d.addCallback(cb)
        return d

# /users/table
class UsersTableResource(HtmlResource):
    pageTitle = "Users Table"
    addSlash = True

    def __init__(self):
        HtmlResource.__init__(self)

    def getChild(self, path, req):
        return OneUserResource(path)

    @defer.deferredGenerator
    def content(self, req, ctx):
        d = self.getAuthz(req).actionAllowed('showUsersPage', req)
        wfd = defer.waitForDeferred(d)
        yield wfd
        res = wfd.getResult()
        if not res:
            yield redirectTo(path_to_authfail(req), req)
            return

        s = self.getStatus(req)

        d = s.master.db.users.getUsers()
        wfd = defer.waitForDeferred(d)
        yield wfd
        usdicts = wfd.getResult()

        users = ctx['users'] = usdicts
        for user in users:
            user['user_link'] = req.childLink(urllib.quote(str(user['uid']), ''))
        template = req.site.buildbot_service.templates.get_template(
                                                              "users_table.html")
        yield template.render(**ctx)

# /users
class UsersResource(HtmlResource):
    pageTitle = "Users"
    addSlash = True

    def __init__(self):
        HtmlResource.__init__(self)
        self.action = "showUsersPage"

    def getChild(self, path, req):
        if path == "table":
            return UsersTableResource()

    @defer.deferredGenerator
    def content(self, req, ctx):
        # check for False or True on showUsersPage, redirect immediately
        authz = self.getAuthz(req)
        if not authz.needAuthForm(self.action):
            if authz.advertiseAction(self.action):
                yield redirectTo("users/table", req)
                return
            else:
                yield redirectTo(path_to_authfail(req), req)
                return

        ctx['authz'] = self.getAuthz(req)
        ctx['table_link'] = req.childLink("table")
        template = req.site.buildbot_service.templates.get_template("users.html")
        yield template.render(**ctx)
