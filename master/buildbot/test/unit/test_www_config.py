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

import json

import mock

from twisted.internet import defer
from twisted.python import log
from twisted.python import util
from twisted.trial import unittest

from buildbot.test.util import www
from buildbot.util import bytes2NativeString
from buildbot.www import auth
from buildbot.www import config


class IndexResource(www.WwwTestMixin, unittest.TestCase):

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
                 for v in rsrc.getEnvironmentVersions()] + custom_versions

        res = yield self.render_resource(rsrc, b'/')
        res = json.loads(bytes2NativeString(res))
        _auth.maybeAutoLogin.assert_called_with(mock.ANY)
        exp = {"authz": {}, "titleURL": "http://buildbot.net", "versions": vjson, "title": "Buildbot", "auth": {
            "name": "NoAuth"}, "user": {"anonymous": True}, "buildbotURL": "h:/a/b/", "multiMaster": False, "port": None}
        self.assertEqual(res, exp)

        master.session.user_info = dict(name="me", email="me@me.org")
        res = yield self.render_resource(rsrc, b'/')
        res = json.loads(bytes2NativeString(res))
        exp = {"authz": {}, "titleURL": "http://buildbot.net", "versions": vjson, "title": "Buildbot", "auth": {"name": "NoAuth"},
               "user": {"email": "me@me.org", "name": "me"}, "buildbotURL": "h:/a/b/", "multiMaster": False, "port": None}
        self.assertEqual(res, exp)

        master = self.make_master(
            url='h:/a/c/', auth=_auth, versions=custom_versions)
        rsrc.reconfigResource(master.config)
        res = yield self.render_resource(rsrc, b'/')
        res = json.loads(bytes2NativeString(res))
        exp = {"authz": {}, "titleURL": "http://buildbot.net", "versions": vjson, "title": "Buildbot", "auth": {
            "name": "NoAuth"}, "user": {"anonymous": True}, "buildbotURL": "h:/a/b/", "multiMaster": False, "port": None}
        self.assertEqual(res, exp)

    def test_parseCustomTemplateDir(self):
        exp = {'views/builds.html': json.dumps('<div>\n</div>')}
        try:
            # we make the test work if pyjade is present or note
            # It is better than just skip if pyjade is not there
            import pyjade
            [pyjade]
            exp.update({'plugin/views/plugin.html':
                        json.dumps(u'<div class="myclass"><pre>this is customized</pre></div>')})
        except ImportError:
            log.msg("Only testing html based template override")
        template_dir = util.sibpath(__file__, "test_templates_dir")
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
        self.assertNotIn('custom_templates_dir', master.config.www)
        self.assertEqual('returnvalue', rsrc.custom_templates)
