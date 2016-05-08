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
import os
import webbrowser

import mock
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import threads
from twisted.python import failure
from twisted.trial import unittest
from twisted.web.resource import Resource
from twisted.web.server import Site

from buildbot.test.util import www
from buildbot.util import json

try:
    import requests
except ImportError:
    requests = None


if requests:
    from buildbot.www import oauth2


class FakeResponse(object):

    def __init__(self, _json):
        self.json = lambda: _json
        self.content = json.dumps(_json)

    def raise_for_status(self):
        pass


class OAuth2Auth(www.WwwTestMixin, unittest.TestCase):

    def setUp(self):
        if requests is None:
            raise unittest.SkipTest("Need to install requests to test oauth2")

        self.patch(requests, 'request', mock.Mock(spec=requests.request))
        self.patch(requests, 'post', mock.Mock(spec=requests.post))
        self.patch(requests, 'get', mock.Mock(spec=requests.get))

        self.googleAuth = oauth2.GoogleAuth("ggclientID", "clientSECRET")
        self.githubAuth = oauth2.GitHubAuth("ghclientID", "clientSECRET")
        self.gitlabAuth = oauth2.GitLabAuth(
            "https://gitlab.test/", "glclientID", "clientSECRET")

        for auth in [self.googleAuth, self.githubAuth, self.gitlabAuth]:
            self._master = master = self.make_master(url='h:/a/b/', auth=auth)
            auth.reconfigAuth(master, master.config)

    @defer.inlineCallbacks
    def test_getGoogleLoginURL(self):
        res = yield self.googleAuth.getLoginURL('http://redir')
        exp = ("https://accounts.google.com/o/oauth2/auth?scope=https%3A%2F%2F"
               "www.googleapis.com%2Fauth%2Fuserinfo.email+https%3A%2F%2Fwww.go"
               "ogleapis.com%2Fauth%2Fuserinfo.profile&state=redirect%3Dhttp%253A%252F%252Fredir&redirect_uri=h%3A%2Fa%2Fb"
               "%2Fauth%2Flogin&response_type=code&client_id=ggclientID")
        self.assertEqual(res, exp)
        res = yield self.googleAuth.getLoginURL(None)
        exp = ("https://accounts.google.com/o/oauth2/auth?scope=https%3A%2F%2F"
               "www.googleapis.com%2Fauth%2Fuserinfo.email+https%3A%2F%2Fwww.go"
               "ogleapis.com%2Fauth%2Fuserinfo.profile&redirect_uri=h%3A%2Fa%2Fb"
               "%2Fauth%2Flogin&response_type=code&client_id=ggclientID")
        self.assertEqual(res, exp)

    @defer.inlineCallbacks
    def test_getGithubLoginURL(self):
        res = yield self.githubAuth.getLoginURL('http://redir')
        exp = ("https://github.com/login/oauth/authorize?state=redirect%3Dhttp%253A%252F%252Fredir&redirect_uri="
               "h%3A%2Fa%2Fb%2Fauth%2Flogin&response_type=code&client_id=ghclientID")
        self.assertEqual(res, exp)
        res = yield self.githubAuth.getLoginURL(None)
        exp = ("https://github.com/login/oauth/authorize?redirect_uri="
               "h%3A%2Fa%2Fb%2Fauth%2Flogin&response_type=code&client_id=ghclientID")
        self.assertEqual(res, exp)

    @defer.inlineCallbacks
    def test_getGitLabLoginURL(self):
        res = yield self.gitlabAuth.getLoginURL('http://redir')
        exp = ("https://gitlab.test/oauth/authorize"
               "?state=redirect%3Dhttp%253A%252F%252Fredir"
               "&redirect_uri=h%3A%2Fa%2Fb%2Fauth%2Flogin"
               "&response_type=code"
               "&client_id=glclientID")
        self.assertEqual(res, exp)
        res = yield self.gitlabAuth.getLoginURL(None)
        exp = ("https://gitlab.test/oauth/authorize"
               "?redirect_uri=h%3A%2Fa%2Fb%2Fauth%2Flogin"
               "&response_type=code"
               "&client_id=glclientID")
        self.assertEqual(res, exp)

    @defer.inlineCallbacks
    def test_GoogleVerifyCode(self):
        requests.get.side_effect = []
        requests.post.side_effect = [
            FakeResponse(dict(access_token="TOK3N"))]
        self.googleAuth.get = mock.Mock(side_effect=[dict(
            name="foo bar",
            email="bar@foo", picture="http://pic")])
        res = yield self.googleAuth.verifyCode("code!")
        self.assertEqual({'avatar_url': 'http://pic', 'email': 'bar@foo',
                          'full_name': 'foo bar', 'username': 'bar'}, res)

    @defer.inlineCallbacks
    def test_GithubVerifyCode(self):
        requests.get.side_effect = []
        requests.post.side_effect = [
            FakeResponse(dict(access_token="TOK3N"))]
        self.githubAuth.get = mock.Mock(side_effect=[
            dict(  # /user
                login="bar",
                name="foo bar",
                email="bar@foo"),
            [dict(  # /users/bar/orgs
                login="group",)
             ]])
        res = yield self.githubAuth.verifyCode("code!")
        self.assertEqual({'email': 'bar@foo',
                          'username': 'bar',
                          'groups': ['group'],
                          'full_name': 'foo bar'}, res)

    @defer.inlineCallbacks
    def test_GitlabVerifyCode(self):
        requests.get.side_effect = []
        requests.post.side_effect = [
            FakeResponse(dict(access_token="TOK3N"))]
        self.gitlabAuth.get = mock.Mock(side_effect=[
            {  # /user
                "name": "Foo Bar",
                "username": "fbar",
                "id": 5,
                "avatar_url": "https://avatar/fbar.png",
                "email": "foo@bar",
                "twitter": "fb",
            },
            [  # /groups
                {"id": 10, "name": "Hello", "path": "hello"},
                {"id": 20, "name": "Group", "path": "grp"},
            ]])
        res = yield self.gitlabAuth.verifyCode("code!")
        self.assertEqual({"full_name": "Foo Bar",
                          "username": "fbar",
                          "email": "foo@bar",
                          "avatar_url": "https://avatar/fbar.png",
                          "groups": ["hello", "grp"]}, res)

    @defer.inlineCallbacks
    def test_loginResource(self):
        class fakeAuth(object):
            homeUri = "://me"
            getLoginURL = mock.Mock(side_effect=lambda x: defer.succeed("://"))
            verifyCode = mock.Mock(
                side_effect=lambda code: defer.succeed({"username": "bar"}))
            userInfoProvider = None

        rsrc = self.githubAuth.getLoginResource()
        rsrc.auth = fakeAuth()
        res = yield self.render_resource(rsrc, '/')
        rsrc.auth.getLoginURL.assert_called_once_with(None)
        rsrc.auth.verifyCode.assert_not_called()
        self.assertEqual(res, {'redirected': '://'})
        rsrc.auth.getLoginURL.reset_mock()
        rsrc.auth.verifyCode.reset_mock()
        res = yield self.render_resource(rsrc, '/?code=code!')
        rsrc.auth.getLoginURL.assert_not_called()
        rsrc.auth.verifyCode.assert_called_once_with("code!")
        self.assertEqual(self.master.session.user_info, {'username': 'bar'})
        self.assertEqual(res, {'redirected': '://me'})

    def test_getConfig(self):
        self.assertEqual(self.githubAuth.getConfigDict(), {'fa_icon': 'fa-github', 'autologin': False,
                                                           'name': 'GitHub', 'oauth2': True})
        self.assertEqual(self.googleAuth.getConfigDict(), {'fa_icon': 'fa-google-plus', 'autologin': False,
                                                           'name': 'Google', 'oauth2': True})
        self.assertEqual(self.gitlabAuth.getConfigDict(), {'fa_icon': 'fa-git', 'autologin': False,
                                                           'name': 'GitLab', 'oauth2': True})

# unit tests are not very usefull to write new oauth support
# so following is an e2e test, which opens a browser, and do the oauth
# negociation. The browser window close in the end of the test

# in order to use this tests, you need to create Github/Google ClientID (see doc on how to do it)
# point OAUTHCONF environment variable to a file with following params:
#  {
#  "GitHubAuth": {
#     "CLIENTID": "XX
#     "CLIENTSECRET": "XX"
#  },
#  "GoogleAuth": {
#     "CLIENTID": "XX",
#     "CLIENTSECRET": "XX"
#  }
#  "GitLabAuth": {
#     "INSTANCEURI": "XX",
#     "CLIENTID": "XX",
#     "CLIENTSECRET": "XX"
#  }
#  }


class OAuth2AuthGitHubE2E(www.WwwTestMixin, unittest.TestCase):
    authClass = "GitHubAuth"

    def _instantiateAuth(self, cls, config):
        return cls(config["CLIENTID"], config["CLIENTSECRET"])

    def setUp(self):
        if requests is None:
            raise unittest.SkipTest("Need to install requests to test oauth2")

        if "OAUTHCONF" not in os.environ:
            raise unittest.SkipTest(
                "Need to pass OAUTHCONF path to json file via environ to run this e2e test")

        import json
        config = json.load(open(os.environ['OAUTHCONF']))[self.authClass]
        from buildbot.www import oauth2
        self.auth = self._instantiateAuth(
            getattr(oauth2, self.authClass), config)

        # 5000 has to be hardcoded, has oauth clientids are bound to a fully
        # classified web site
        master = self.make_master(url='http://localhost:5000/', auth=self.auth)
        self.auth.reconfigAuth(master, master.config)

    def tearDown(self):
        from twisted.internet.tcp import Server
        # browsers has the bad habbit on not closing the persistent
        # connections, so we need to hack them away to make trial happy
        f = failure.Failure(Exception("test end"))
        for reader in reactor.getReaders():
            if isinstance(reader, Server):
                reader.connectionLost(f)

    @defer.inlineCallbacks
    def test_E2E(self):
        d = defer.Deferred()
        import twisted
        twisted.web.http._logDateTimeUsers = 1

        class HomePage(Resource):
            isLeaf = True

            def render_GET(self, request):
                info = request.getSession().user_info
                reactor.callLater(0, d.callback, info)
                return "<html><script>setTimeout(close,1000)</script><body>WORKED: %s</body></html>" % (info)

        class MySite(Site):

            def makeSession(self):
                uid = self._mkuid()
                session = self.sessions[uid] = self.sessionFactory(self, uid)
                return session
        root = Resource()
        root.putChild("", HomePage())
        auth = Resource()
        root.putChild('auth', auth)
        auth.putChild('login', self.auth.getLoginResource())
        site = MySite(root)
        l = reactor.listenTCP(5000, site)

        def thd():
            res = requests.get('http://localhost:5000/auth/login')
            webbrowser.open(res.content)
        threads.deferToThread(thd)
        res = yield d
        yield l.stopListening()
        yield site.stopFactory()

        self.assertIn("full_name", res)
        self.assertIn("email", res)
        self.assertIn("username", res)


class OAuth2AuthGoogleE2E(OAuth2AuthGitHubE2E):
    authClass = "GoogleAuth"


class OAuth2AuthGitLabE2E(OAuth2AuthGitHubE2E):
    authClass = "GitLabAuth"

    def _instantiateAuth(self, cls, config):
        return cls(config["INSTANCEURI"], config["CLIENTID"], config["CLIENTSECRET"])
