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

from __future__ import absolute_import
from __future__ import print_function

import re

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
from zope.interface import implementer

from buildbot.util import bytes2NativeString
from buildbot.util import config
from buildbot.util import unicode2bytes
from buildbot.www import resource


class AuthRootResource(resource.Resource):

    def getChild(self, path, request):
        # return dynamically generated resources
        if path == b'login':
            return self.master.www.auth.getLoginResource()
        elif path == b'logout':
            return self.master.www.auth.getLogoutResource()
        return resource.Resource.getChild(self, path, request)


class AuthBase(config.ConfiguredMixin):

    def __init__(self, userInfoProvider=None):
        self.userInfoProvider = userInfoProvider

    def reconfigAuth(self, master, new_config):
        self.master = master

    def maybeAutoLogin(self, request):
        return defer.succeed(None)

    def getLoginResource(self):
        raise Error(501, "not implemented")

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


class NoAuth(AuthBase):
    pass


class RemoteUserAuth(AuthBase):
    header = "REMOTE_USER"
    headerRegex = re.compile(r"(?P<username>[^ @]+)@(?P<realm>[^ @]+)")

    def __init__(self, header=None, headerRegex=None, **kwargs):
        AuthBase.__init__(self, **kwargs)
        if self.userInfoProvider is None:
            self.userInfoProvider = UserInfoProviderBase()
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
            raise Error(
                403, 'http header does not match regex! "%s" not matching %s' %
                (header, self.headerRegex.pattern))
        session = request.getSession()
        if session.user_info != dict(res.groupdict()):
            session.user_info = dict(res.groupdict())
            yield self.updateUserInfo(request)


@implementer(IRealm)
class AuthRealm(object):

    def __init__(self, master, auth):
        self.auth = auth
        self.master = master

    def requestAvatar(self, avatarId, mind, *interfaces):
        if IResource in interfaces:
            return (IResource,
                    PreAuthenticatedLoginResource(self.master, avatarId),
                    lambda: None)
        raise NotImplementedError()


class TwistedICredAuthBase(AuthBase):

    def __init__(self, credentialFactories, checkers, **kwargs):
        AuthBase.__init__(self, **kwargs)
        if self.userInfoProvider is None:
            self.userInfoProvider = UserInfoProviderBase()
        self.credentialFactories = credentialFactories
        self.checkers = checkers

    def getLoginResource(self):
        return HTTPAuthSessionWrapper(
            Portal(AuthRealm(self.master, self), self.checkers),
            self.credentialFactories)


class HTPasswdAuth(TwistedICredAuthBase):

    def __init__(self, passwdFile, **kwargs):
        TwistedICredAuthBase.__init__(
            self,
            [DigestCredentialFactory(b"md5", b"buildbot"),
             BasicCredentialFactory(b"buildbot")],
            [FilePasswordDB(passwdFile)],
            **kwargs)


class UserPasswordAuth(TwistedICredAuthBase):

    def __init__(self, users, **kwargs):
        for user, password in users.items():
            users[user] = unicode2bytes(password)
        TwistedICredAuthBase.__init__(
            self,
            [DigestCredentialFactory(b"md5", b"buildbot"),
             BasicCredentialFactory(b"buildbot")],
            [InMemoryUsernamePasswordDatabaseDontUse(**dict(users))],
            **kwargs)


def _redirect(master, request):
    url = request.args.get("redirect", ["/"])[0]
    return resource.Redirect(master.config.buildbotURL + "#" + url)


class PreAuthenticatedLoginResource(LoginResource):
    # a LoginResource which is already authenticated via a
    # HTTPAuthSessionWrapper

    def __init__(self, master, username):
        LoginResource.__init__(self, master)
        self.username = username

    @defer.inlineCallbacks
    def renderLogin(self, request):
        session = request.getSession()
        session.user_info = dict(username=bytes2NativeString(self.username))
        yield self.master.www.auth.updateUserInfo(request)
        raise _redirect(self.master, request)


class LogoutResource(resource.Resource):

    def render_GET(self, request):
        session = request.getSession()
        session.expire()
        session.updateSession(request)
        request.redirect(_redirect(self.master, request).url)
        return b''
