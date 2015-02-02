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

from buildbot.test.util import www
from buildbot.www import auth
from buildbot.www import config
from twisted.internet import defer
from twisted.trial import unittest


class IndexResource(www.WwwTestMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def test_render(self):
        _auth = auth.NoAuth()
        _auth.maybeAutoLogin = mock.Mock()
        master = self.make_master(url='h:/a/b/', auth=_auth)
        rsrc = config.IndexResource(master, "foo")
        rsrc.reconfigResource(master.config)
        rsrc.jinja = mock.Mock()
        template = mock.Mock()
        rsrc.jinja.get_template = lambda x: template
        template.render = lambda configjson, config: configjson

        res = yield self.render_resource(rsrc, '/')
        _auth.maybeAutoLogin.assert_called_with(mock.ANY)
        exp = '{"titleURL": "http://buildbot.net", "title": "Buildbot", "auth": {"name": "NoAuth"}, "user": {"anonymous": true}, "buildbotURL": "h:/a/b/", "multiMaster": false, "port": null}'
        self.assertIn(res, exp)

        master.session.user_info = dict(name="me", email="me@me.org")
        res = yield self.render_resource(rsrc, '/')
        exp = '{"titleURL": "http://buildbot.net", "title": "Buildbot", "auth": {"name": "NoAuth"}, "user": {"email": "me@me.org", "name": "me"}, "buildbotURL": "h:/a/b/", "multiMaster": false, "port": null}'
        self.assertIn(res, exp)

        master = self.make_master(url='h:/a/c/', auth=_auth)
        rsrc.reconfigResource(master.config)
        res = yield self.render_resource(rsrc, '/')
        exp = '{"titleURL": "http://buildbot.net", "title": "Buildbot", "auth": {"name": "NoAuth"}, "user": {"anonymous": true}, "buildbotURL": "h:/a/b/", "multiMaster": false, "port": null}'
        self.assertIn(res, exp)
