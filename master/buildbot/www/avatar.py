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

import hashlib
import urllib

from buildbot.util import config
from buildbot.www import resource
from twisted.internet import defer
from urlparse import urljoin


class AvatarBase(config.ConfiguredMixin):
    name = "noavatar"

    def getUserAvatar(self, email, size, defaultAvatarUrl):
        raise NotImplementedError()


class AvatarGravatar(AvatarBase):
    name = "gravatar"

    def getUserAvatar(self, email, size, defaultAvatarUrl):
        # construct the url
        gravatar_url = "//www.gravatar.com/avatar/"
        gravatar_url += hashlib.md5(email.lower()).hexdigest() + "?"
        gravatar_url += urllib.urlencode({'s': str(size), 'd': defaultAvatarUrl})
        raise resource.Redirect(gravatar_url)


class AvatarResource(resource.Resource):
    # enable reconfigResource calls
    needsReconfig = True
    defaultAvatarUrl = "img/nobody.png"

    def reconfigResource(self, new_config):
        self.avatarMethods = new_config.www.get('avatar_methods', [])
        self.defaultAvatarFullUrl = urljoin(new_config.www['url'], self.defaultAvatarUrl)
        self.cache = {}
        # ensure the avatarMethods is a iterable
        if isinstance(self.avatarMethods, AvatarBase):
            self.avatarMethods = (self.avatarMethods, )

    def render_GET(self, request):
        return self.asyncRenderHelper(request, self.renderAvatar)

    @defer.inlineCallbacks
    def renderAvatar(self, request):
        email = request.args.get("email", [""])[0]
        size = request.args.get("size", 32)
        if self.cache.get(email):
            r = self.cache[email]
        for method in self.avatarMethods:
            try:
                res = yield method.getUserAvatar(email, size, self.defaultAvatarFullUrl)
            except resource.Redirect, r:
                self.cache[email] = r
                raise
            if res is not None:
                request.setHeader('content-type', res[0])
                request.setHeader('content-length', len(res[1]))
                request.write(res[1])
                return
        raise resource.Redirect(self.defaultAvatarUrl)
