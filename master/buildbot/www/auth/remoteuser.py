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

from twisted.internet import defer
from twisted.web.error import Error

from buildbot.util import bytes2unicode
from buildbot.util import unicode2bytes
from buildbot.www.auth.base import AuthBase
from buildbot.www.auth.base import UserInfoProviderBase


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
            raise Error(403, b"missing http header " + self.header + b". Check your reverse proxy config!")
        res = self.headerRegex.match(header)
        if res is None:
            raise Error(
                403, b'http header does not match regex! "' + header + b'" not matching ' + self.headerRegex.pattern)
        session = request.getSession()
        user_info = {k: bytes2unicode(v) for k, v in res.groupdict().items()}
        if session.user_info != user_info:
            session.user_info = user_info
            yield self.updateUserInfo(request)
