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

from twisted.cred.portal import IRealm
from twisted.internet import defer
from twisted.web.error import Error
from twisted.web.resource import IResource
from zope.interface import implementer

from buildbot.util import bytes2unicode
from buildbot.util import config
from buildbot.www import resource


class AuthRootResource(resource.Resource):

    def getChild(self, path, request):
        # return dynamically generated resources
        if path == b'login':
            return self.master.www.auth.getLoginResource()
        elif path == b'logout':
            return self.master.www.auth.getLogoutResource()
        return super().getChild(path, request)


class AuthBase(config.ConfiguredMixin):

    def __init__(self, userInfoProvider=None):
        self.userInfoProvider = userInfoProvider

    def reconfigAuth(self, master, new_config):
        self.master = master

    def maybeAutoLogin(self, request):
        return defer.succeed(None)

    def getLoginResource(self):
        raise Error(501, b"not implemented")

    def getLogoutResource(self):
        return LogoutResource(self.master)

    @defer.inlineCallbacks
    def updateUserInfo(self, request):
        session = request.getSession()
        if self.userInfoProvider is not None:
            infos = yield self.userInfoProvider.getUserInfo(session.user_info['username'])
            session.user_info.update(infos)
            session.updateSession(request)

    def getConfigDict(self):
        return {'name': type(self).__name__}


class UserInfoProviderBase(config.ConfiguredMixin):
    name = "noinfo"

    def getUserInfo(self, username):
        return defer.succeed({'email': username})


class LoginResource(resource.Resource):

    def render_GET(self, request):
        return self.asyncRenderHelper(request, self.renderLogin)

    @defer.inlineCallbacks
    def renderLogin(self, request):
        raise NotImplementedError


@implementer(IRealm)
class AuthRealm:

    def __init__(self, master, auth):
        self.auth = auth
        self.master = master

    def requestAvatar(self, avatarId, mind, *interfaces):
        if IResource in interfaces:
            return (IResource,
                    PreAuthenticatedLoginResource(self.master, avatarId),
                    lambda: None)
        raise NotImplementedError()


def _redirect(master, request):
    url = request.args.get(b"redirect", [b"/"])[0]
    url = bytes2unicode(url)
    return resource.Redirect(master.config.buildbotURL + "#" + url)


class PreAuthenticatedLoginResource(LoginResource):
    # a LoginResource which is already authenticated via a
    # HTTPAuthSessionWrapper

    def __init__(self, master, username):
        super().__init__(master)
        self.username = username

    @defer.inlineCallbacks
    def renderLogin(self, request):
        session = request.getSession()
        session.user_info = dict(username=bytes2unicode(self.username))
        yield self.master.www.auth.updateUserInfo(request)
        raise _redirect(self.master, request)


class LogoutResource(resource.Resource):

    def render_GET(self, request):
        session = request.getSession()
        session.expire()
        session.updateSession(request)
        request.redirect(_redirect(self.master, request).url)
        return b''
