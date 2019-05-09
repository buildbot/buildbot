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

from buildbot.www import resource
from twisted.web.error import Error
import datetime

import jwt

APITOKEN_SECRET_ALGORITHM = "HS256"


class APITokenResource(resource.Resource):

    def render_GET(self, request):
        userinfos = self.master.www.getUserInfos(request)
        if userinfos.get('anonymous'):  # user is not logged
            raise Error(403, "Forbidden")

        request.setHeader(b"content-type", b'text/plain')
        request.setHeader(b"Cache-Control", b"no-cache, no-store, must-revalidate")
        request.setHeader(b"Content-Disposition", b"attachment; filename=\"x-api-token.txt\"")
        request.setHeader(b"X-Frame-Options", b"SAMEORIGIN")

        claims = {
            'user_info': userinfos,
        }

        return jwt.encode(claims, self.master.www.site.api_token_secret, algorithm=APITOKEN_SECRET_ALGORITHM)
