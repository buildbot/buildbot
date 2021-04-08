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
from abc import ABCMeta
from abc import abstractmethod

from twisted.cred.checkers import FilePasswordDB
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse
from twisted.cred.credentials import IUsernamePassword
from twisted.cred.error import UnauthorizedLogin
from twisted.cred.portal import IRealm
from twisted.cred.portal import Portal
from twisted.internet import defer
from twisted.web.error import Error
from twisted.web.guard import BasicCredentialFactory
from twisted.web.guard import DigestCredentialFactory
from twisted.web.guard import HTTPAuthSessionWrapper
from twisted.web.resource import IResource
from zope.interface import implementer

from buildbot.util import bytes2unicode
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


class NoAuth(AuthBase):
    pass


class RemoteUserAuth(AuthBase):
    header = b"REMOTE_USER"
    headerRegex = re.compile(br"(?P<username>[^ @]+)@(?P<realm>[^ @]+)")

    def __init__(self, header=None, headerRegex=None, **kwargs):
        super().__init__(**kwargs)
        if self.userInfoProvider is None:
            self.userInfoProvider = UserInfoProviderBase()
        if header is not None:
            self.header = unicode2bytes(header)
        if headerRegex is not None:
            self.headerRegex = re.compile(unicode2bytes(headerRegex))

    @defer.inlineCallbacks
    def maybeAutoLogin(self, request):
        header = request.getHeader(self.header)
        if header is None:
            msg = b"missing http header " + self.header + b". Check your reverse proxy config!"
            raise Error(403, msg)
        res = self.headerRegex.match(header)
        if res is None:
            msg = b'http header does not match regex! "' + header + b'" not matching ' + \
                    self.headerRegex.pattern
            raise Error(403, msg)
        session = request.getSession()
        user_info = {k: bytes2unicode(v) for k, v in res.groupdict().items()}
        if session.user_info != user_info:
            session.user_info = user_info
            yield self.updateUserInfo(request)


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


class TwistedICredAuthBase(AuthBase):

    def __init__(self, credentialFactories, checkers, **kwargs):
        super().__init__(**kwargs)
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
        super().__init__([DigestCredentialFactory(b"MD5", b"buildbot"),
             BasicCredentialFactory(b"buildbot")],
            [FilePasswordDB(passwdFile)],
            **kwargs)


class UserPasswordAuth(TwistedICredAuthBase):

    def __init__(self, users, **kwargs):
        if isinstance(users, dict):
            users = {user: unicode2bytes(pw) for user, pw in users.items()}
        elif isinstance(users, list):
            users = [(user, unicode2bytes(pw)) for user, pw in users]
        super().__init__([DigestCredentialFactory(b"MD5", b"buildbot"),
             BasicCredentialFactory(b"buildbot")],
            [InMemoryUsernamePasswordDatabaseDontUse(**dict(users))],
            **kwargs)


@implementer(ICredentialsChecker)
class CustomAuth(TwistedICredAuthBase):
    __metaclass__ = ABCMeta
    credentialInterfaces = [IUsernamePassword]

    def __init__(self, **kwargs):
        super().__init__([BasicCredentialFactory(b"buildbot")],
            [self],
            **kwargs)

    def requestAvatarId(self, cred):
        if self.check_credentials(cred.username, cred.password):
            return defer.succeed(cred.username)
        return defer.fail(UnauthorizedLogin())

    @abstractmethod
    def check_credentials(username, password):
        return False


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
