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

import mock

from twisted.internet import defer
from twisted.python import log
from twisted.trial import unittest

from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import www
from buildbot.util import bytes2unicode
from buildbot.www import auth
from buildbot.www import config


class TestConfigResource(TestReactorMixin, www.WwwTestMixin, unittest.TestCase):
    def setUp(self):
        self.setup_test_reactor()

    @defer.inlineCallbacks
    def test_render(self):
        _auth = auth.NoAuth()
        _auth.maybeAutoLogin = mock.Mock()

        custom_versions = [
            ['test compoent', '0.1.2'],
            ['test component 2', '0.2.1']
        ]

        master = self.make_master(url='h:/a/b/', auth=_auth, versions=custom_versions)
        rsrc = config.ConfigResource(master)
        rsrc.reconfigResource(master.config)

        vjson = [list(v)
                 for v in config.get_environment_versions()] + custom_versions

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
            "port": None
        }
        self.assertEqual(res, exp)


class IndexResource(TestReactorMixin, www.WwwTestMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()

    @defer.inlineCallbacks
    def test_render(self):
        _auth = auth.NoAuth()
        _auth.maybeAutoLogin = mock.Mock()

        custom_versions = [
            ['test compoent', '0.1.2'], ['test component 2', '0.2.1']]

        master = self.make_master(
            url='h:/a/b/', auth=_auth, versions=custom_versions)
        rsrc = config.IndexResource(master, "foo")
        rsrc.reconfigResource(master.config)
        rsrc.jinja = mock.Mock()
        template = mock.Mock()
        rsrc.jinja.get_template = lambda x: template
        template.render = lambda configjson, config, custom_templates: configjson

        vjson = [list(v)
                 for v in config.get_environment_versions()] + custom_versions

        res = yield self.render_resource(rsrc, b'/')
        res = json.loads(bytes2unicode(res))
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
            "port": None
        }
        self.assertEqual(res, exp)

        master.session.user_info = dict(name="me", email="me@me.org")
        res = yield self.render_resource(rsrc, b'/')
        res = json.loads(bytes2unicode(res))
        exp = {
            "authz": {},
            "titleURL": "http://buildbot.net",
            "versions": vjson,
            "title": "Buildbot",
            "auth": {"name": "NoAuth"},
            "user": {"email": "me@me.org", "name": "me"},
            "buildbotURL": "h:/a/b/",
            "multiMaster": False,
            "port": None
        }
        self.assertEqual(res, exp)

        master = self.make_master(
            url='h:/a/c/', auth=_auth, versions=custom_versions)
        rsrc.reconfigResource(master.config)
        res = yield self.render_resource(rsrc, b'/')
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
            "port": None
        }
        self.assertEqual(res, exp)

    def test_parseCustomTemplateDir(self):
        exp = {'views/builds.html': '<div>\n</div>'}
        try:
            # we make the test work if pypugjs is present or note
            # It is better than just skip if pypugjs is not there
            import pypugjs  # pylint: disable=import-outside-toplevel
            [pypugjs]
            exp.update({'plugin/views/plugin.html':
                        '<div class="myclass"><pre>this is customized</pre></div>'})
        except ImportError:
            log.msg("Only testing html based template override")
        template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    'test_templates_dir')
        master = self.make_master(url='h:/a/b/')
        rsrc = config.IndexResource(master, "foo")
        res = rsrc.parseCustomTemplateDir(template_dir)
        self.assertEqual(res, exp)

    def test_CustomTemplateDir(self):
        master = self.make_master(url='h:/a/b/')
        rsrc = config.IndexResource(master, "foo")
        master.config.www['custom_templates_dir'] = 'foo'
        rsrc.parseCustomTemplateDir = mock.Mock(return_value="returnvalue")
        rsrc.reconfigResource(master.config)
        self.assertNotIn('custom_templates_dir', rsrc.frontend_config)
        self.assertEqual('returnvalue', rsrc.custom_templates)


class IndexResourceReactTest(TestReactorMixin, www.WwwTestMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()

    def get_react_static_path(self):
        path = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        for _ in range(0, 4):
            path = os.path.dirname(path)
        return os.path.join(path, 'www/react-base/public')

    def find_matching_line(self, lines, match, start_i):
        for i in range(start_i, len(lines)):
            if match in lines[i]:
                return i
        return None

    def extract_config_json(self, res):
        lines = res.split('\n')

        first_line = self.find_matching_line(lines, '<script id="bb-config">', 0)
        if first_line is None:
            raise Exception("Could not find first config line")
        first_line += 1

        last_line = self.find_matching_line(lines, '</script>', first_line)
        if last_line is None:
            raise Exception("Could not find last config line")

        config_json = '\n'.join(lines[first_line:last_line])
        config_json = config_json.replace('window.buildbotFrontendConfig = ', '').strip()
        config_json = config_json.strip(';').strip()
        return json.loads(config_json)

    @defer.inlineCallbacks
    def test_render(self):
        _auth = auth.NoAuth()
        _auth.maybeAutoLogin = mock.Mock()

        custom_versions = [['test compoent', '0.1.2'], ['test component 2', '0.2.1']]

        master = self.make_master(url='h:/a/b/', auth=_auth, versions=custom_versions,
                                  plugins=['base_react'])

        rsrc = config.IndexResourceReact(master, self.get_react_static_path())
        rsrc.reconfigResource(master.config)

        vjson = [list(v)
                 for v in config.get_environment_versions()] + custom_versions

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
            "plugins": ["base_react"],
        }
        self.assertEqual(config_json, exp)
