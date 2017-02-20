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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.util import www
from buildbot.www import auth
from buildbot.www import avatar


class AvatarResource(www.WwwTestMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def test_default(self):
        master = self.make_master(
            url='http://a/b/', auth=auth.NoAuth(), avatar_methods=[])
        rsrc = avatar.AvatarResource(master)
        rsrc.reconfigResource(master.config)

        res = yield self.render_resource(rsrc, b'/')
        self.assertEqual(
            res, dict(redirected=avatar.AvatarResource.defaultAvatarUrl))

    @defer.inlineCallbacks
    def test_gravatar(self):
        master = self.make_master(
            url='http://a/b/', auth=auth.NoAuth(), avatar_methods=[avatar.AvatarGravatar()])
        rsrc = avatar.AvatarResource(master)
        rsrc.reconfigResource(master.config)

        res = yield self.render_resource(rsrc, b'/?email=foo')
        self.assertEqual(res, dict(redirected='//www.gravatar.com/avatar/acbd18db4cc2f85ce'
                                   'def654fccc4a4d8?d=retro&s=32'))

    @defer.inlineCallbacks
    def test_custom(self):
        class CustomAvatar(avatar.AvatarBase):

            def getUserAvatar(self, email, size, defaultAvatarUrl):
                return defer.succeed((b"image/png", email +
                                      str(size).encode('utf-8') +
                                      defaultAvatarUrl))

        master = self.make_master(
            url='http://a/b/', auth=auth.NoAuth(), avatar_methods=[CustomAvatar()])
        rsrc = avatar.AvatarResource(master)
        rsrc.reconfigResource(master.config)

        res = yield self.render_resource(rsrc, b'/?email=foo')
        self.assertEqual(res, b"foo32http://a/b/img/nobody.png")

    @defer.inlineCallbacks
    def test_custom_not_found(self):
        # use gravatar if the custom avatar fail to return a response
        class CustomAvatar(avatar.AvatarBase):

            def getUserAvatar(self, email, size, defaultAvatarUrl):
                return defer.succeed(None)

        master = self.make_master(url=b'http://a/b/', auth=auth.NoAuth(),
                                  avatar_methods=[CustomAvatar(), avatar.AvatarGravatar()])
        rsrc = avatar.AvatarResource(master)
        rsrc.reconfigResource(master.config)

        res = yield self.render_resource(rsrc, b'/?email=foo')
        self.assertEqual(res, dict(redirected='//www.gravatar.com/avatar/acbd18db4cc2f85ce'
                         'def654fccc4a4d8?d=retro&s=32'))
