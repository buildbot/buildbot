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

import mock
import re

from buildbot.test.fake import endpoint
from buildbot.test.util import compat
from buildbot.test.util import www
from buildbot.util import json
from buildbot.www import auth
from twisted.internet import defer
from twisted.trial import unittest


class SessionConfigResource(www.WwwTestMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def test_render(self):
        master = self.make_master(url='h:/a/b/', auth=auth.Auth())
        rsrc = auth.SessionConfigResource(master)
        rsrc.reconfigResource(master.config)
        res = yield self.render_resource(rsrc, '/')
        exp = 'this.config = {"url": "h:/a/b/", "user": {"anonymous": true}, "auth": "auth", "port": null}'
        self.assertEqual(res, exp)
        master.session.user_infos = dict(name="me", email="me@me.org")
        res = yield self.render_resource(rsrc, '/')
        exp = 'this.config = {"url": "h:/a/b/", "user": {"email": "me@me.org", "name": "me"}, "auth": "auth", "port": null}'
        self.assertEqual(res, exp)
