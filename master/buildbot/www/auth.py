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

import re

from zope.interface import implements

from buildbot.interfaces import IConfigured
from buildbot.util import config
from buildbot.util import json
from buildbot.www import resource

from twisted.cred.checkers import FilePasswordDB
from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse
from twisted.cred.portal import IRealm
from twisted.cred.portal import Portal
from twisted.internet import defer
from twisted.web.error import Error
from twisted.web.guard import BasicCredentialFactory
from twisted.web.guard import DigestCredentialFactory
from twisted.web.guard import HTTPAuthSessionWrapper
from twisted.web.resource import IResource


class AuthBase(config.ConfiguredMixin):
    name = "auth"

    def __init__(self, userInfoProvider=None):
        if userInfoProvider is None:
            userInfoProvider = UserInfoProviderBase()
        self.userInfoProvider = userInfoProvider

    def reconfigAuth(self, master, new_config):
        self.master = master

    def maybeAutoLogin(self, request):
        return defer.succeed(False)

    def authenticateViaLogin(self, request):
        raise Error(501, "not implemented")

    def getLoginResource(self, master):
        return LoginResource(master)

    @defer.inlineCallbacks
    def updateUserInfo(self, request):
        session = request.getSession()
        if self.userInfoProvider is not None:
            infos = yield self.userInfoProvider.getUserInfo(session.user_infos['username'])
            session.user_infos.update(infos)


class UserInfoProviderBase(config.ConfiguredMixin):
    name = "noinfo"

    def getUserInfo(self, username):
        return defer.succeed({'email': username})


class NoAuth(AuthBase):
    name = "noauth"


class RemoteUserAuth(AuthBase):
    name = "remoteuserauth"
    header = "REMOTE_USER"
    headerRegex = re.compile(r"(?P<username>[^ @]+)@(?P<realm>[^ @]+)")

    def __init__(self, header=None, headerRegex=None, **kwargs):
        AuthBase.__init__(self, **kwargs)
        if header is not None:
            self.header = header
        if headerRegex is not None:
            self.headerRegex = re.compile(headerRegex)

    @defer.inlineCallbacks
    def maybeAutoLogin(self, request):
        header = request.getHeader(self.header)
        if header is None:
            raise Error(403, "missing http header %s. Check your reverse proxy config!" % (
                             self.header))
        res = self.headerRegex.match(header)
        if res is None:
            raise Error(403, 'http header does not match regex! "%s" not matching %s' %
                        (header, self.headerRegex.pattern))
        session = request.getSession()
        if not hasattr(session, "user_infos"):
            session.user_infos = dict(res.groupdict())
            yield self.updateUserInfo(request)
        defer.returnValue(True)

    def authenticateViaLogin(self, request):
        raise Error(403, "Please check with your administrator"
                         ", there is an issue with the reverse proxy")


class AuthRealm(object):
    implements(IRealm)

    def __init__(self, master, auth):
        self.auth = auth
        self.master = master

    def requestAvatar(self, avatarId, mind, *interfaces):
        if IResource in interfaces:
            return (IResource,
                    PreAuthenticatedLoginResource(self.master, self.auth, avatarId),
                    lambda: None)
        raise NotImplementedError()


class TwistedICredAuthBase(AuthBase):
    name = "icredauth"

    def __init__(self, credentialFactories, checkers, **kwargs):
        AuthBase.__init__(self, **kwargs)
        self.credentialFactories = credentialFactories
        self.checkers = checkers

    def getLoginResource(self, master):
        return HTTPAuthSessionWrapper(Portal(AuthRealm(master, self), self.checkers),
                                      self.credentialFactories)


class HTPasswdAuth(TwistedICredAuthBase):

    def __init__(self, passwdFile, **kwargs):
        TwistedICredAuthBase.__init__(
            self,
            [DigestCredentialFactory("md5", "buildbot"), BasicCredentialFactory("buildbot")],
            [FilePasswordDB(passwdFile)],
            **kwargs)


class BasicAuth(TwistedICredAuthBase):

    def __init__(self, users, **kwargs):
        TwistedICredAuthBase.__init__(
            self,
            [DigestCredentialFactory("md5", "buildbot"), BasicCredentialFactory("buildbot")],
            [InMemoryUsernamePasswordDatabaseDontUse(**dict(users))],
            **kwargs)


class SessionConfigResource(resource.Resource):
    # enable reconfigResource calls
    needsReconfig = True

    def reconfigResource(self, new_config):
        self.config = new_config.www

    def render_GET(self, request):
        return self.asyncRenderHelper(request, self.renderConfig)

    @defer.inlineCallbacks
    def renderConfig(self, request):
        config = {}
        request.setHeader("content-type", 'text/javascript')
        request.setHeader("Cache-Control", "public;max-age=0")

        session = request.getSession()
        try:
            yield self.config['auth'].maybeAutoLogin(request)
        except Error, e:
            config["on_load_warning"] = e.message

        if hasattr(session, "user_infos"):
            config.update({"user": session.user_infos})
        else:
            config.update({"user": {"anonymous": True}})
        config.update(self.config)

        def toJson(obj):
            obj = IConfigured(obj).getConfigDict()
            if isinstance(obj, dict):
                return obj
            return repr(obj) + " not yet IConfigured"
        defer.returnValue("this.config = " + json.dumps(config, default=toJson))


class LoginResource(resource.Resource):
    # enable reconfigResource calls
    needsReconfig = True

    def reconfigResource(self, new_config):
        self.auth = new_config.www['auth']

    def render_GET(self, request):
        return self.asyncRenderHelper(request, self.renderLogin)

    @defer.inlineCallbacks
    def renderLogin(self, request):
        yield self.auth.authenticateViaLogin(request)


class PreAuthenticatedLoginResource(LoginResource):
    # a LoginResource, which is already authenticated via a HTTPAuthSessionWrapper
    # disable reconfigResource calls
    needsReconfig = False

    def __init__(self, master, auth, username):
        LoginResource.__init__(self, master)
        self.auth = auth
        self.username = username

    @defer.inlineCallbacks
    def renderLogin(self, request):
        session = request.getSession()
        session.user_infos = dict(username=self.username)
        yield self.auth.updateUserInfo(request)


class LogoutResource(resource.Resource):
    # enable reconfigResource calls
    needsReconfig = True

    def reconfigResource(self, new_config):
        self.auth = new_config.www['auth']

    def render_GET(self, request):
        session = request.getSession()
        session.expire()
        return ""
