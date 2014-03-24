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
import sys

from twisted.internet import defer
from twisted.trial import unittest
from buildbot.test.util import www


class FakeClient(object):
    auth_uri = mock.Mock(return_value="uri://foo")
    request_token = mock.Mock()


class FakeSanction(object):
    transport_headers = "sanction.transport_headers"
    Client = mock.Mock(return_value=FakeClient())


class OAuth2Auth(www.WwwTestMixin, unittest.TestCase):
    # we completely fake the python sanction module, so no need to require
    # it to run the unit tests
    def setUp(self):
        self.oldsanction = sys.modules.get("sanction", None)
        self.sanction = FakeSanction()
        sys.modules["sanction"] = self.sanction
        # need to import it here if we want this trick to work
        from buildbot.www import oauth2

        self.googleAuth = oauth2.GoogleAuth("ggclientID", "clientSECRET")
        self.githubAuth = oauth2.GitHubAuth("ghclientID", "clientSECRET")
        master = self.make_master(url='h:/a/b/', auth=self.googleAuth)
        self.googleAuth.reconfigAuth(master, master.config)
        self.master = master = self.make_master(url='h:/a/b/', auth=self.githubAuth)
        self.githubAuth.reconfigAuth(master, master.config)

    def tearDown(self):
        if self.oldsanction is None:
            del sys.modules["sanction"]
        else:
            sys.modules["sanction"] = self.oldsanction

    @defer.inlineCallbacks
    def test_getGoogleLoginURL(self):
        res = yield self.googleAuth.getLoginURL()
        self.sanction.Client.assert_called_with(
            client_id='ggclientID',
            auth_endpoint='https://accounts.google.com/o/oauth2/auth')
        self.sanction.Client().auth_uri.assert_called_with(
            scope='https://www.googleapis.com/auth/userinfo.email'
                  ' https://www.googleapis.com/auth/userinfo.profile',
            redirect_uri='h:/a/b/login', access_type='offline')
        self.assertEqual(res, "uri://foo")

    @defer.inlineCallbacks
    def test_getGithubLoginURL(self):
        res = yield self.githubAuth.getLoginURL()
        self.sanction.Client.assert_called_with(
            client_id='ghclientID',
            auth_endpoint='https://github.com/login/oauth/authorize')
        self.sanction.Client().auth_uri.assert_called_with(
            redirect_uri='h:/a/b/login')
        self.assertEqual(res, "uri://foo")

    @defer.inlineCallbacks
    def test_GoogleVerifyCode(self):
        self.sanction.Client().request = mock.Mock(return_value=dict(
            name="foo bar",
            sub='foo',
            email="bar@foo", picture="http://pic"))
        res = yield self.googleAuth.verifyCode("code!")
        self.sanction.Client.assert_called_with(
            client_secret='clientSECRET',
            token_endpoint='https://accounts.google.com/o/oauth2/token',
            client_id='ggclientID',
            token_transport="sanction.transport_headers",
            resource_endpoint='https://www.googleapis.com/oauth2/v1')

        self.sanction.Client().request_token.assert_called_with(
            code='code!', redirect_uri='h:/a/b/login')
        self.assertEqual({'avatar_url': 'http://pic', 'email': 'bar@foo',
                         'full_name': 'foo bar', 'username': 'foo'}, res)

    @defer.inlineCallbacks
    def test_GithubVerifyCode(self):
        self.sanction.Client().request = mock.Mock(side_effect=[
            dict(  # /user
                login="bar",
                name="foo bar",
                email="bar@foo"),
            [dict(  # /users/bar/orgs
                login="group",)
             ]])
        res = yield self.githubAuth.verifyCode("code!")
        self.sanction.Client.assert_called_with(
            client_secret='clientSECRET',
            token_endpoint='https://github.com/login/oauth/access_token',
            client_id='ghclientID', token_transport='sanction.transport_headers',
            resource_endpoint='https://api.github.com')

        self.sanction.Client().request_token.assert_called_with(
            code='code!', redirect_uri='h:/a/b/login')

        self.assertEqual(self.sanction.Client().request.call_args_list, [
            mock.call('/user'), mock.call('/users/bar/orgs')])

        self.assertEqual({'email': 'bar@foo',
                          'username': 'bar',
                          'groups': ['group'],
                          'full_name': 'foo bar'}, res)

    @defer.inlineCallbacks
    def test_loginResource(self):
        class fakeAuth(object):
            homeUri = "://me"
            getLoginURL = mock.Mock(side_effect=lambda: defer.succeed("://"))
            verifyCode = mock.Mock(side_effect=lambda code: defer.succeed({"username": "bar"}))

        rsrc = self.githubAuth.getLoginResource(self.master)
        rsrc.auth = fakeAuth()
        res = yield self.render_resource(rsrc, '/')
        rsrc.auth.getLoginURL.assert_called_once_with()
        rsrc.auth.verifyCode.assert_not_called()
        self.assertEqual(res, "://")
        rsrc.auth.getLoginURL.reset_mock()
        rsrc.auth.verifyCode.reset_mock()
        res = yield self.render_resource(rsrc, '/?code=code!')
        rsrc.auth.getLoginURL.assert_not_called()
        rsrc.auth.verifyCode.assert_called_once_with("code!")
        self.assertEqual(self.master.session.user_infos, {'username': 'bar'})
        self.assertEqual(res, {'redirected': '://me'})

    def test_getConfig(self):
        self.assertEqual(self.githubAuth.getConfig(), {'fa_icon': 'fa-github',
                                                       'name': 'GitHub', 'oauth2': True})
        self.assertEqual(self.googleAuth.getConfig(), {'fa_icon': 'fa-google-plus',
                                                       'name': 'Google', 'oauth2': True})
