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

import sanction

from buildbot.www import auth
from buildbot.www import resource
from posixpath import join
from twisted.internet import defer
from twisted.internet import threads


class OAuth2LoginResource(auth.LoginResource):
    # disable reconfigResource calls
    needsReconfig = False

    def __init__(self, master, _auth):
        auth.LoginResource.__init__(self, master)
        self.auth = _auth

    @defer.inlineCallbacks
    def renderLogin(self, request):
        code = request.args.get("code", [""])[0]
        if not code:
            url = yield self.auth.getLoginURL()
            defer.returnValue(url)
        else:
            details = yield self.auth.verifyCode(code)
            request.getSession().user_info = details
            raise resource.Redirect(self.auth.homeUri)


class OAuth2Auth(auth.AuthBase):
    name = 'oauth2'

    def __init__(self, authUri, tokenUri, clientId,
                 authUriConfig, tokenConfig, **kwargs):
        auth.AuthBase.__init__(self, **kwargs)
        self.authUri = authUri
        self.tokenUri = tokenUri
        self.clientId = clientId
        self.authUriConfig = authUriConfig
        self.tokenConfig = tokenConfig

    def reconfigAuth(self, master, new_config):
        self.master = master
        self.loginUri = join(new_config.www['url'], "login")
        self.homeUri = new_config.www['url']

    def getConfigDict(self):
        return dict(name=self.name,
                    oauth2=True,
                    fa_icon=self.faIcon
                    )
        pass

    def getLoginResource(self, master):
        return OAuth2LoginResource(master, self)

    def getLoginURL(self):
        def thd():
            c = sanction.Client(auth_endpoint=self.authUri,
                                client_id=self.clientId)
            return c.auth_uri(redirect_uri=self.loginUri,
                              **self.authUriConfig)
        return threads.deferToThread(thd)

    def verifyCode(self, code):
        def thd():  # everything in deferToThread is not counted with trial  --coverage :-(
            c = sanction.Client(token_endpoint=self.tokenUri,
                                client_id=self.clientId,
                                **self.tokenConfig)
            c.request_token(code=code,
                            redirect_uri=self.loginUri)

            return self.getUserInfoFromOAuthClient(c)
        return threads.deferToThread(thd)

    def getUserInfoFromOAuthClient(self, c):
        return {}


class GoogleAuth(OAuth2Auth):
    name = "Google"
    faIcon = "fa-google-plus"

    def __init__(self, clientId, clientSecret, **kwargs):
        OAuth2Auth.__init__(self,
                            authUri='https://accounts.google.com/o/oauth2/auth',
                            tokenUri='https://accounts.google.com/o/oauth2/token',
                            clientId=clientId,
                            authUriConfig=dict(scope=" ".join([
                                               'https://www.googleapis.com/auth/userinfo.email',
                                               'https://www.googleapis.com/auth/userinfo.profile',
                                               ]),
                                               access_type='offline'),
                            tokenConfig=dict(
                                resource_endpoint='https://www.googleapis.com/oauth2/v1',
                                client_secret=clientSecret,
                                token_transport=sanction.transport_headers),
                            **kwargs
                            )

    def getUserInfoFromOAuthClient(self, c):
        data = c.request('/userinfo')
        return dict(full_name=data["name"],
                    username=data['sub'],
                    email=data["email"],
                    avatar_url=data["picture"])


class GitHubAuth(OAuth2Auth):
    name = "GitHub"
    faIcon = "fa-github"

    def __init__(self, clientId, clientSecret, **kwargs):
        OAuth2Auth.__init__(self,
                            authUri='https://github.com/login/oauth/authorize',
                            tokenUri='https://github.com/login/oauth/access_token',
                            clientId=clientId,
                            authUriConfig=dict(),
                            tokenConfig=dict(
                                resource_endpoint='https://api.github.com',
                                client_secret=clientSecret,
                                token_transport=sanction.transport_headers),
                            **kwargs
                            )

    def getUserInfoFromOAuthClient(self, c):
        user = c.request('/user')
        orgs = c.request(join('/users', user['login'], "orgs"))
        return dict(full_name=user['name'],
                    email=user['email'],
                    username=user['login'],
                    groups=[org['login'] for org in orgs])
