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

import json
import os
from unittest import mock

from parameterized import parameterized

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import www
from buildbot.util import bytes2unicode
from buildbot.www import auth
from buildbot.www import config


class Utils(unittest.TestCase):
    def test_serialize_www_frontend_theme_to_css(self):
        self.maxDiff = None
        self.assertEqual(
            config.serialize_www_frontend_theme_to_css({}, indent=4),
            """\
--bb-sidebar-background-color: #30426a;
    --bb-sidebar-header-background-color: #273759;
    --bb-sidebar-header-text-color: #fff;
    --bb-sidebar-title-text-color: #627cb7;
    --bb-sidebar-footer-background-color: #273759;
    --bb-sidebar-button-text-color: #b2bfdc;
    --bb-sidebar-button-hover-background-color: #1b263d;
    --bb-sidebar-button-hover-text-color: #fff;
    --bb-sidebar-button-current-background-color: #273759;
    --bb-sidebar-button-current-text-color: #b2bfdc;
    --bb-sidebar-stripe-hover-color: #e99d1a;
    --bb-sidebar-stripe-current-color: #8c5e10;""",
        )


class TestConfigResource(TestReactorMixin, www.WwwTestMixin, unittest.TestCase):
    def setUp(self):
        self.setup_test_reactor()

    @defer.inlineCallbacks
    def test_render(self):
        _auth = auth.NoAuth()
        _auth.maybeAutoLogin = mock.Mock()

        custom_versions = [['test compoent', '0.1.2'], ['test component 2', '0.2.1']]

        master = self.make_master(url='h:/a/b/', auth=_auth, versions=custom_versions)
        rsrc = config.ConfigResource(master)
        rsrc.reconfigResource(master.config)

        vjson = [list(v) for v in config.get_environment_versions()] + custom_versions

        res = yield self.render_resource(rsrc, b'/config')
        res = json.loads(bytes2unicode(res))
        exp = {
            "authz": {},
            "titleURL": "http://buildbot.net",
            "versions": vjson,
            "title": "Buildbot",
            "auth": {"name": "NoAuth"},
            "user": {"anonymous": True},
            "buildbotURL": "h:/a/b/",
            "multiMaster": False,
            "port": None,
        }
        self.assertEqual(res, exp)


class IndexResourceTest(TestReactorMixin, www.WwwTestMixin, unittest.TestCase):
    def setUp(self):
        self.setup_test_reactor()

    def get_react_base_path(self):
        path = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        for _ in range(0, 4):
            path = os.path.dirname(path)
        return os.path.join(path, 'www/base')

    def find_matching_line(self, lines, match, start_i):
        for i in range(start_i, len(lines)):
            if match in lines[i]:
                return i
        return None

    def extract_config_json(self, res):
        lines = res.split('\n')

        first_line = self.find_matching_line(lines, '<script id="bb-config">', 0)
        if first_line is None:
            raise RuntimeError("Could not find first config line")
        first_line += 1

        last_line = self.find_matching_line(lines, '</script>', first_line)
        if last_line is None:
            raise RuntimeError("Could not find last config line")

        config_json = '\n'.join(lines[first_line:last_line])
        config_json = config_json.replace('window.buildbotFrontendConfig = ', '').strip()
        config_json = config_json.strip(';').strip()
        return json.loads(config_json)

    @parameterized.expand([
        ('anonymous_user', None, {'anonymous': True}),
        (
            'logged_in_user',
            {"name": 'me', "email": 'me@me.org'},
            {"email": "me@me.org", "name": "me"},
        ),
    ])
    @defer.inlineCallbacks
    def test_render(self, name, user_info, expected_user):
        _auth = auth.NoAuth()
        _auth.maybeAutoLogin = mock.Mock()

        custom_versions = [['test compoent', '0.1.2'], ['test component 2', '0.2.1']]

        master = self.make_master(url='h:/a/b/', auth=_auth, versions=custom_versions, plugins={})
        if user_info is not None:
            master.session.user_info = user_info

        # IndexResource only uses static path to get index.html. In the source checkout
        # index.html resides not in www/base/public but in www/base. Thus
        # base path is sent to IndexResource.
        rsrc = config.IndexResource(master, self.get_react_base_path())
        rsrc.reconfigResource(master.config)

        vjson = [list(v) for v in config.get_environment_versions()] + custom_versions

        res = yield self.render_resource(rsrc, b'/')
        config_json = self.extract_config_json(bytes2unicode(res))

        _auth.maybeAutoLogin.assert_called_with(mock.ANY)
        exp = {
            "authz": {},
            "titleURL": "http://buildbot.net",
            "versions": vjson,
            "title": "Buildbot",
            "auth": {"name": "NoAuth"},
            "user": expected_user,
            "buildbotURL": "h:/a/b/",
            "multiMaster": False,
            "port": None,
            "plugins": {},
        }
        self.assertEqual(config_json, exp)


class IndexResourceReactTestOldPath(TestReactorMixin, www.WwwTestMixin, unittest.TestCase):
    def setUp(self):
        self.setup_test_reactor()

    def get_react_base_path(self):
        path = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        for _ in range(0, 4):
            path = os.path.dirname(path)
        return os.path.join(path, 'www/react-base')

    def find_matching_line(self, lines, match, start_i):
        for i in range(start_i, len(lines)):
            if match in lines[i]:
                return i
        return None

    def extract_config_json(self, res):
        lines = res.split('\n')

        first_line = self.find_matching_line(lines, '<script id="bb-config">', 0)
        if first_line is None:
            raise RuntimeError("Could not find first config line")
        first_line += 1

        last_line = self.find_matching_line(lines, '</script>', first_line)
        if last_line is None:
            raise RuntimeError("Could not find last config line")

        config_json = '\n'.join(lines[first_line:last_line])
        config_json = config_json.replace('window.buildbotFrontendConfig = ', '').strip()
        config_json = config_json.strip(';').strip()
        return json.loads(config_json)

    @defer.inlineCallbacks
    def test_render(self):
        _auth = auth.NoAuth()
        _auth.maybeAutoLogin = mock.Mock()

        custom_versions = [['test compoent', '0.1.2'], ['test component 2', '0.2.1']]

        master = self.make_master(
            url='h:/a/b/', auth=_auth, versions=custom_versions, plugins={'base_react': True}
        )

        # IndexResource only uses static path to get index.html. In the source checkout
        # index.html resides not in www/base/public but in www/base. Thus
        # base path is sent to IndexResource.
        rsrc = config.IndexResource(master, self.get_react_base_path())
        rsrc.reconfigResource(master.config)

        vjson = [list(v) for v in config.get_environment_versions()] + custom_versions

        res = yield self.render_resource(rsrc, b'/')
        config_json = self.extract_config_json(bytes2unicode(res))

        _auth.maybeAutoLogin.assert_called_with(mock.ANY)
        exp = {
            "authz": {},
            "titleURL": "http://buildbot.net",
            "versions": vjson,
            "title": "Buildbot",
            "auth": {"name": "NoAuth"},
            "user": {"anonymous": True},
            "buildbotURL": "h:/a/b/",
            "multiMaster": False,
            "port": None,
            "plugins": {},
        }
        self.assertEqual(config_json, exp)
