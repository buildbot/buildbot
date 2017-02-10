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
from future.moves.urllib.parse import urlencode
from future.moves.urllib.parse import urljoin

import hashlib

from twisted.internet import defer

from buildbot.util import config
from buildbot.util import unicode2bytes
from buildbot.www import resource


class AvatarBase(config.ConfiguredMixin):
    name = "noavatar"

    def getUserAvatar(self, email, size, defaultAvatarUrl):
        raise NotImplementedError()


class AvatarGravatar(AvatarBase):
    name = "gravatar"
    # gravatar does not want intranet URL, which is most of where the bots are
    # just use same default as github (retro)
    default = "retro"

    def getUserAvatar(self, email, size, defaultAvatarUrl):
        # construct the url
        emailBytes = unicode2bytes(email.lower())
        emailHash = hashlib.md5(emailBytes)
        gravatar_url = "//www.gravatar.com/avatar/"
        gravatar_url += emailHash.hexdigest() + "?"
        if self.default != "url":
            defaultAvatarUrl = self.default
        url = {'d': defaultAvatarUrl, 's': str(size)}
        sorted_url = sorted(url.items(), key=lambda x: x[0])
        gravatar_url += urlencode(sorted_url)
        raise resource.Redirect(gravatar_url)


class AvatarResource(resource.Resource):
    # enable reconfigResource calls
    needsReconfig = True
    defaultAvatarUrl = b"img/nobody.png"

    def reconfigResource(self, new_config):
        self.avatarMethods = new_config.www.get('avatar_methods', [])
        self.defaultAvatarFullUrl = urljoin(
            unicode2bytes(new_config.buildbotURL), unicode2bytes(self.defaultAvatarUrl))
        self.cache = {}
        # ensure the avatarMethods is a iterable
        if isinstance(self.avatarMethods, AvatarBase):
            self.avatarMethods = (self.avatarMethods, )

    def render_GET(self, request):
        return self.asyncRenderHelper(request, self.renderAvatar)

    @defer.inlineCallbacks
    def renderAvatar(self, request):
        email = request.args.get(b"email", [b""])[0]
        size = request.args.get(b"size", 32)
        if self.cache.get(email):
            r = self.cache[email]
        for method in self.avatarMethods:
            try:
                res = yield method.getUserAvatar(email, size, self.defaultAvatarFullUrl)
            except resource.Redirect as r:
                self.cache[email] = r
                raise
            if res is not None:
                request.setHeader(b'content-type', res[0])
                request.setHeader(b'content-length', len(res[1]))
                request.write(res[1])
                return
        raise resource.Redirect(self.defaultAvatarUrl)
