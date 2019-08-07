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

from twisted.cred.checkers import FilePasswordDB
from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse
from twisted.cred.portal import Portal
from twisted.web.guard import BasicCredentialFactory
from twisted.web.guard import DigestCredentialFactory
from twisted.web.guard import HTTPAuthSessionWrapper

from buildbot.util import unicode2bytes
from buildbot.www.auth.base import AuthBase
from buildbot.www.auth.base import AuthRealm
from buildbot.www.auth.base import UserInfoProviderBase


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
        super().__init__([DigestCredentialFactory(b"md5", b"buildbot"),
             BasicCredentialFactory(b"buildbot")],
            [FilePasswordDB(passwdFile)],
            **kwargs)


class UserPasswordAuth(TwistedICredAuthBase):

    def __init__(self, users, **kwargs):
        if isinstance(users, dict):
            users = {user: unicode2bytes(pw) for user, pw in users.items()}
        elif isinstance(users, list):
            users = [(user, unicode2bytes(pw)) for user, pw in users]
        super().__init__([DigestCredentialFactory(b"md5", b"buildbot"),
             BasicCredentialFactory(b"buildbot")],
            [InMemoryUsernamePasswordDatabaseDontUse(**dict(users))],
            **kwargs)
