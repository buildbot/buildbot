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
from posixpath import join

import requests
from future.moves.urllib.parse import parse_qs
from future.moves.urllib.parse import urlencode
from future.utils import iteritems
from twisted.internet import defer
from twisted.internet import threads

from buildbot.util import json
from buildbot.www import auth
from buildbot.www import resource


class OAuth2LoginResource(auth.LoginResource):
    # disable reconfigResource calls
    needsReconfig = False

    def __init__(self, master, _auth):
        auth.LoginResource.__init__(self, master)
        self.auth = _auth

    def render_POST(self, request):
        return self.asyncRenderHelper(request, self.renderLogin)

    @defer.inlineCallbacks
    def renderLogin(self, request):
        code = request.args.get("code", [""])[0]
        if not code:
            url = request.args.get("redirect", [None])[0]
            url = yield self.auth.getLoginURL(url)
            raise resource.Redirect(url)
        else:
            details = yield self.auth.verifyCode(code)
            if self.auth.userInfoProvider is not None:
                infos = yield self.auth.userInfoProvider.getUserInfo(details['username'])
                details.update(infos)
            request.getSession().user_info = details
            state = request.args.get("state", [""])[0]
            print repr(state)
            if state:
                for redirect in parse_qs(state).get('redirect', []):
                    raise resource.Redirect(self.auth.homeUri + "#" + redirect)
            raise resource.Redirect(self.auth.homeUri)


class OAuth2Auth(auth.AuthBase):
    name = 'oauth2'
    getTokenUseAuthHeaders = False
    authUri = None
    tokenUri = None
    grantType = 'authorization_code'
    authUriAdditionalParams = {}
    tokenUriAdditionalParams = {}
    loginUri = None
    homeUri = None
    sslVerify = None

    def __init__(self,
                 clientId, clientSecret, autologin=False, **kwargs):
        auth.AuthBase.__init__(self, **kwargs)
        self.clientId = clientId
        self.clientSecret = clientSecret
        self.autologin = autologin

    def reconfigAuth(self, master, new_config):
        self.master = master
        self.loginUri = join(new_config.buildbotURL, "auth/login")
        self.homeUri = new_config.buildbotURL

    def getConfigDict(self):
        return dict(name=self.name,
                    oauth2=True,
                    fa_icon=self.faIcon,
                    autologin=self.autologin
                    )

    def getLoginResource(self):
        return OAuth2LoginResource(self.master, self)

    def getLoginURL(self, redirect_url):
        """
        Returns the url to redirect the user to for user consent
        """
        oauth_params = {'redirect_uri': self.loginUri,
                        'client_id': self.clientId, 'response_type': 'code'}
        if redirect_url is not None:
            oauth_params['state'] = urlencode(dict(redirect=redirect_url))
        oauth_params.update(self.authUriAdditionalParams)
        return defer.succeed("%s?%s" % (self.authUri, urlencode(oauth_params)))

    def createSessionFromToken(self, token):
        s = requests.Session()
        s.params = {'access_token': token['access_token']}
        return s

    def get(self, session, path):
        ret = session.get(self.resourceEndpoint + path)
        return ret.json()

    # based on https://github.com/maraujop/requests-oauth
    # from Miguel Araujo, augmented to support header based clientSecret
    # passing
    def verifyCode(self, code):
        # everything in deferToThread is not counted with trial  --coverage :-(
        def thd():
            url = self.tokenUri
            data = {'redirect_uri': self.loginUri, 'code': code,
                    'grant_type': self.grantType}
            auth = None
            if self.getTokenUseAuthHeaders:
                auth = (self.clientId, self.clientSecret)
            else:
                data.update(
                    {'client_id': self.clientId, 'client_secret': self.clientSecret})
            data.update(self.tokenUriAdditionalParams)
            response = requests.post(
                url, data=data, auth=auth, verify=self.sslVerify)
            response.raise_for_status()
            if isinstance(response.content, basestring):
                try:
                    content = json.loads(response.content)
                except ValueError:
                    content = parse_qs(response.content)
                    for k, v in iteritems(content):
                        content[k] = v[0]
            else:
                content = response.content

            session = self.createSessionFromToken(content)
            return self.getUserInfoFromOAuthClient(session)
        return threads.deferToThread(thd)

    def getUserInfoFromOAuthClient(self, c):
        return {}


class GoogleAuth(OAuth2Auth):
    name = "Google"
    faIcon = "fa-google-plus"
    resourceEndpoint = "https://www.googleapis.com/oauth2/v1"
    authUri = 'https://accounts.google.com/o/oauth2/auth'
    tokenUri = 'https://accounts.google.com/o/oauth2/token'
    authUriAdditionalParams = dict(scope=" ".join([
                                   'https://www.googleapis.com/auth/userinfo.email',
                                   'https://www.googleapis.com/auth/userinfo.profile'
                                   ]))

    def getUserInfoFromOAuthClient(self, c):
        data = self.get(c, '/userinfo')
        return dict(full_name=data["name"],
                    username=data['email'].split("@")[0],
                    email=data["email"],
                    avatar_url=data["picture"])


class GitHubAuth(OAuth2Auth):
    name = "GitHub"
    faIcon = "fa-github"
    authUri = 'https://github.com/login/oauth/authorize'
    tokenUri = 'https://github.com/login/oauth/access_token'
    resourceEndpoint = 'https://api.github.com'

    def getUserInfoFromOAuthClient(self, c):
        user = self.get(c, '/user')
        orgs = self.get(c, join('/users', user['login'], "orgs"))
        return dict(full_name=user['name'],
                    email=user['email'],
                    username=user['login'],
                    groups=[org['login'] for org in orgs])


class GitLabAuth(OAuth2Auth):
    name = "GitLab"
    faIcon = "fa-git"

    def __init__(self, instanceUri, clientId, clientSecret, **kwargs):
        uri = instanceUri.rstrip("/")
        self.authUri = "%s/oauth/authorize" % uri
        self.tokenUri = "%s/oauth/token" % uri
        self.resourceEndpoint = "%s/api/v3" % uri
        super(GitLabAuth, self).__init__(clientId, clientSecret, **kwargs)

    def getUserInfoFromOAuthClient(self, c):
        user = self.get(c, "/user")
        groups = self.get(c, "/groups")
        return dict(full_name=user["name"],
                    username=user["username"],
                    email=user["email"],
                    avatar_url=user["avatar_url"],
                    groups=[g["path"] for g in groups])
