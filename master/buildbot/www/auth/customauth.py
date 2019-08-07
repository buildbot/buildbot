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

from abc import ABCMeta
from abc import abstractmethod

from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import IUsernamePassword
from twisted.cred.error import UnauthorizedLogin
from twisted.internet import defer
from twisted.web.guard import BasicCredentialFactory
from zope.interface import implementer

from buildbot.www.auth.userpasswd import TwistedICredAuthBase


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
