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


from __future__ import annotations

import re
from abc import ABCMeta
from abc import abstractmethod
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable
from typing import cast

import jwt
import twisted
from packaging.version import parse as parse_version
from twisted.cred.checkers import FilePasswordDB
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse
from twisted.cred.credentials import IUsernamePassword
from twisted.cred.error import UnauthorizedLogin
from twisted.cred.portal import IRealm
from twisted.cred.portal import Portal
from twisted.internet import defer
from twisted.python import log
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

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class AuthRootResource(resource.Resource):
    def getChild(self, path: bytes, request: Any) -> resource.Resource:
        # return dynamically generated resources
        if path == b'login':
            return self.master.www.auth.getLoginResource()
        elif path == b'logout':
            return self.master.www.auth.getLogoutResource()
        return super().getChild(path, request)


class AuthBase(config.ConfiguredMixin):
    def __init__(self, userInfoProvider: UserInfoProviderBase | None = None) -> None:
        self.userInfoProvider = userInfoProvider

    def reconfigAuth(self, master: Any, new_config: Any) -> None:
        self.master = master

    def maybeAutoLogin(self, request: Any) -> defer.Deferred[None]:
        return defer.succeed(None)

    def getLoginResource(self) -> resource.Resource:
        raise Error(501, b"not implemented")

    def getLogoutResource(self) -> resource.Resource:
        return LogoutResource(self.master)

    @defer.inlineCallbacks
    def updateUserInfo(self, request: Any) -> InlineCallbacksType[None]:
        session = request.getSession()
        if self.userInfoProvider is not None:
            infos = yield self.userInfoProvider.getUserInfo(session.user_info['username'])
            session.user_info.update(infos)
            session.updateSession(request)

    def getConfigDict(self) -> dict[str, str]:
        return {'name': type(self).__name__}


class UserInfoProviderBase(config.ConfiguredMixin):
    name = "noinfo"

    def getUserInfo(self, username: str) -> defer.Deferred[dict[str, str]]:
        return defer.succeed({'email': username})


class LoginResource(resource.Resource):
    def render_GET(self, request: Any) -> Any:
        return self.asyncRenderHelper(request, self.renderLogin)

    @defer.inlineCallbacks
    def renderLogin(self, request: Any) -> InlineCallbacksType[None]:
        raise NotImplementedError


class NoAuth(AuthBase):
    pass


class RemoteUserAuth(AuthBase):
    header = b"REMOTE_USER"
    headerRegex = re.compile(rb"(?P<username>[^ @]+)@(?P<realm>[^ @]+)")

    def __init__(
        self, header: str | None = None, headerRegex: str | None = None, **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        if self.userInfoProvider is None:
            self.userInfoProvider = UserInfoProviderBase()
        if header is not None:
            self.header = unicode2bytes(header)
        if headerRegex is not None:
            self.headerRegex = re.compile(unicode2bytes(headerRegex))

    def getLoginResource(self) -> resource.Resource:
        current_version = parse_version(twisted.__version__)
        if current_version < parse_version("22.10.0"):
            from twisted.web.resource import ForbiddenResource

            return cast(
                resource.Resource,
                ForbiddenResource(message="URL is not supported for authentication"),
            )

        from twisted.web.pages import forbidden

        return cast(resource.Resource, forbidden(message="URL is not supported for authentication"))

    @defer.inlineCallbacks
    def maybeAutoLogin(self, request: Any) -> InlineCallbacksType[None]:
        header = request.getHeader(self.header)
        if header is None:
            msg = b"missing http header " + self.header + b". Check your reverse proxy config!"
            raise Error(403, msg)
        res = self.headerRegex.match(header)
        if res is None:
            msg = (
                b'http header does not match regex! "'
                + header
                + b'" not matching '
                + self.headerRegex.pattern
            )
            raise Error(403, msg)
        session = request.getSession()
        user_info = {k: bytes2unicode(v) for k, v in res.groupdict().items()}
        if session.user_info != user_info:
            session.user_info = user_info
            yield self.updateUserInfo(request)


@implementer(IRealm)
class AuthRealm:
    def __init__(self, master: Any, auth: Any) -> None:
        self.auth = auth
        self.master = master

    def requestAvatar(
        self, avatarId: Any, mind: Any, *interfaces: Any
    ) -> tuple[Any, Any, Callable[[], None]]:
        if IResource in interfaces:
            return (IResource, PreAuthenticatedLoginResource(self.master, avatarId), lambda: None)
        raise NotImplementedError()


class TwistedICredAuthBase(AuthBase):
    def __init__(self, credentialFactories: list[Any], checkers: list[Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if self.userInfoProvider is None:
            self.userInfoProvider = UserInfoProviderBase()
        self.credentialFactories = credentialFactories
        self.checkers = checkers

    def getLoginResource(self) -> resource.Resource:
        return cast(
            resource.Resource,
            HTTPAuthSessionWrapper(
                Portal(AuthRealm(self.master, self), self.checkers), self.credentialFactories
            ),
        )


class HTPasswdAuth(TwistedICredAuthBase):
    def __init__(self, passwdFile: str, **kwargs: Any) -> None:
        super().__init__(
            [DigestCredentialFactory(b"MD5", b"buildbot"), BasicCredentialFactory(b"buildbot")],
            [FilePasswordDB(passwdFile)],
            **kwargs,
        )


class UserPasswordAuth(TwistedICredAuthBase):
    def __init__(
        self, users: dict[str, str | bytes] | list[tuple[str, str | bytes]], **kwargs: Any
    ) -> None:
        if isinstance(users, dict):
            users_dict = {user: unicode2bytes(pw) for user, pw in users.items()}
        elif isinstance(users, list):
            users_dict = {user: unicode2bytes(pw) for user, pw in users}
        super().__init__(
            [DigestCredentialFactory(b"MD5", b"buildbot"), BasicCredentialFactory(b"buildbot")],
            [InMemoryUsernamePasswordDatabaseDontUse(**users_dict)],
            **kwargs,
        )


@implementer(ICredentialsChecker)
class CustomAuth(TwistedICredAuthBase):
    __metaclass__ = ABCMeta
    credentialInterfaces = [IUsernamePassword]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__([BasicCredentialFactory(b"buildbot")], [self], **kwargs)

    def requestAvatarId(self, cred: Any) -> defer.Deferred[Any]:
        if self.check_credentials(cred.username, cred.password):
            return defer.succeed(cred.username)
        return defer.fail(UnauthorizedLogin())

    @abstractmethod
    def check_credentials(self, username: bytes, password: bytes) -> bool:
        return False


def _redirect(master: Any, request: Any) -> resource.Redirect:
    url = request.args.get(b"redirect", [b"/"])[0]
    url = bytes2unicode(url)
    return resource.Redirect(master.config.buildbotURL + "#" + url)


class PreAuthenticatedLoginResource(LoginResource):
    # a LoginResource which is already authenticated via a
    # HTTPAuthSessionWrapper

    def __init__(self, master: Any, username: bytes) -> None:
        super().__init__(master)
        self.username = username

    @defer.inlineCallbacks
    def renderLogin(self, request: Any) -> InlineCallbacksType[None]:
        session = request.getSession()
        session.user_info = {"username": bytes2unicode(self.username)}
        yield self.master.www.auth.updateUserInfo(request)
        raise _redirect(self.master, request)


class LogoutResource(resource.Resource):
    def render_GET(self, request: Any) -> bytes:
        session = request.getSession()
        session.expire()
        session.updateSession(request)
        request.redirect(_redirect(self.master, request).url)
        return b''


# as per:
# http://security.stackexchange.com/questions/95972/what-are-requirements-for-hmac-secret-key
# we need 128 bit key for HS256
SESSION_SECRET_LENGTH = 128
SESSION_SECRET_ALGORITHM = "HS256"


def parse_user_info_from_token(token: str, session_secret: str) -> dict[str, Any]:
    try:
        decoded = jwt.decode(token, session_secret, algorithms=[SESSION_SECRET_ALGORITHM])
    except jwt.exceptions.ExpiredSignatureError as e:
        raise KeyError(str(e)) from e
    except jwt.exceptions.InvalidSignatureError as e:
        log.msg(
            e,
            "Web request has been rejected.Signature verification failed while decoding JWT.",
        )
        raise KeyError(str(e)) from e
    except Exception as e:
        log.err(e, "while decoding JWT session")
        raise KeyError(str(e)) from e
    # might raise KeyError: will be caught by caller, which makes the token invalid
    return decoded['user_info']


def build_anonymous_user_info() -> dict[str, Any]:
    return {'anonymous': True}


def build_cookie_name(is_secure: bool, sitepath: list[bytes]) -> bytes:
    # we actually need to copy some hardcoded constants from twisted :-(
    if not is_secure:
        cookie_string = b"TWISTED_SESSION"
    else:
        cookie_string = b"TWISTED_SECURE_SESSION"

    return b"_".join([cookie_string, *sitepath])
