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
import re
import textwrap
from posixpath import join
from urllib.parse import parse_qs
from urllib.parse import urlencode

import jinja2
import requests

from twisted.internet import defer
from twisted.internet import threads

from buildbot import config
from buildbot.process.properties import Properties
from buildbot.util import bytes2unicode
from buildbot.util.logger import Logger
from buildbot.www import auth
from buildbot.www import resource

log = Logger()


class OAuth2LoginResource(auth.LoginResource):
    # disable reconfigResource calls
    needsReconfig = False

    def __init__(self, master, _auth):
        super().__init__(master)
        self.auth = _auth

    def render_POST(self, request):
        return self.asyncRenderHelper(request, self.renderLogin)

    @defer.inlineCallbacks
    def renderLogin(self, request):
        code = request.args.get(b"code", [b""])[0]
        token = request.args.get(b"token", [b""])[0]
        if not token and not code:
            url = request.args.get(b"redirect", [None])[0]
            url = yield self.auth.getLoginURL(url)
            raise resource.Redirect(url)

        if not token:
            details = yield self.auth.verifyCode(code)
        else:
            details = yield self.auth.acceptToken(token)
        if self.auth.userInfoProvider is not None:
            infos = yield self.auth.userInfoProvider.getUserInfo(details['username'])
            details.update(infos)
        session = request.getSession()
        session.user_info = details
        session.updateSession(request)
        state = request.args.get(b"state", [b""])[0]
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
        super().__init__(**kwargs)
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

    @defer.inlineCallbacks
    def getLoginURL(self, redirect_url):
        """
        Returns the url to redirect the user to for user consent
        """
        p = Properties()
        p.master = self.master
        clientId = yield p.render(self.clientId)
        oauth_params = {'redirect_uri': self.loginUri,
                        'client_id': clientId, 'response_type': 'code'}
        if redirect_url is not None:
            oauth_params['state'] = urlencode(dict(redirect=redirect_url))
        oauth_params.update(self.authUriAdditionalParams)
        sorted_oauth_params = sorted(oauth_params.items(), key=lambda val: val[0])
        return "%s?%s" % (self.authUri, urlencode(sorted_oauth_params))

    def createSessionFromToken(self, token):
        s = requests.Session()
        s.params = {'access_token': token['access_token']}
        s.verify = self.sslVerify
        return s

    def get(self, session, path):
        ret = session.get(self.resourceEndpoint + path)
        return ret.json()

    # If the user wants to authenticate directly with an access token they
    # already have, go ahead and just directly accept an access_token from them.
    def acceptToken(self, token):
        def thd():
            session = self.createSessionFromToken({'access_token': token})
            return self.getUserInfoFromOAuthClient(session)
        return threads.deferToThread(thd)

    # based on https://github.com/maraujop/requests-oauth
    # from Miguel Araujo, augmented to support header based clientSecret
    # passing
    @defer.inlineCallbacks
    def verifyCode(self, code):
        # everything in deferToThread is not counted with trial  --coverage :-(
        def thd(client_id, client_secret):
            url = self.tokenUri
            data = {'redirect_uri': self.loginUri, 'code': code,
                    'grant_type': self.grantType}
            auth = None
            if self.getTokenUseAuthHeaders:
                auth = (client_id, client_secret)
            else:
                data.update(
                    {'client_id': client_id, 'client_secret': client_secret})
            data.update(self.tokenUriAdditionalParams)
            response = requests.post(
                url, data=data, auth=auth, verify=self.sslVerify)
            response.raise_for_status()
            responseContent = bytes2unicode(response.content)
            try:
                content = json.loads(responseContent)
            except ValueError:
                content = parse_qs(responseContent)
                for k, v in content.items():
                    content[k] = v[0]
            except TypeError:
                content = responseContent

            session = self.createSessionFromToken(content)
            return self.getUserInfoFromOAuthClient(session)
        p = Properties()
        p.master = self.master
        client_id = yield p.render(self.clientId)
        client_secret = yield p.render(self.clientSecret)
        result = yield threads.deferToThread(thd, client_id, client_secret)
        return result

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
    authUriAdditionalParams = {'scope': 'user:email read:org'}
    tokenUri = 'https://github.com/login/oauth/access_token'
    resourceEndpoint = 'https://api.github.com'

    getUserTeamsGraphqlTpl = textwrap.dedent(r'''
        {%- if organizations %}
        query getOrgTeamMembership {
          {%- for org_slug, org_name in organizations.items() %}
          {{ org_slug }}: organization(login: "{{ org_name }}") {
            teams(first: 100 userLogins: ["{{ user_info.username }}"]) {
              edges {
                node {
                  name,
                  slug
                }
              }
            }
          }
          {%- endfor %}
        }
        {%- endif %}
    ''')

    def __init__(self,
                 clientId, clientSecret, serverURL=None, autologin=False,
                 apiVersion=3, getTeamsMembership=False, debug=False,
                 **kwargs):

        super().__init__(clientId, clientSecret, autologin, **kwargs)
        if serverURL is not None:
            # setup for enterprise github
            if serverURL.endswith("/"):
                serverURL = serverURL[:-1]
            # v3 is accessible directly at /api/v3 for enterprise, but directly for SaaS..
            self.resourceEndpoint = serverURL + '/api/v3'

            self.authUri = '{0}/login/oauth/authorize'.format(serverURL)
            self.tokenUri = '{0}/login/oauth/access_token'.format(serverURL)
        self.serverURL = serverURL or self.resourceEndpoint

        if apiVersion not in (3, 4):
            config.error(
                'GitHubAuth apiVersion must be 3 or 4 not {}'.format(
                    apiVersion))
        self.apiVersion = apiVersion
        if apiVersion == 3:
            if getTeamsMembership is True:
                config.error(
                    'Retrieving team membership information using GitHubAuth is only '
                    'possible using GitHub api v4.')
        else:
            self.apiResourceEndpoint = self.serverURL + '/graphql'
        if getTeamsMembership:
            # GraphQL name aliases must comply with /^[_a-zA-Z][_a-zA-Z0-9]*$/
            self._orgname_slug_sub_re = re.compile(r'[^_a-zA-Z0-9]')
            self.getUserTeamsGraphqlTplC = jinja2.Template(
                self.getUserTeamsGraphqlTpl.strip())
        self.getTeamsMembership = getTeamsMembership
        self.debug = debug

    def post(self, session, query):
        if self.debug:
            log.info('{klass} GraphQL POST Request: {endpoint} -> '
                     'DATA:\n----\n{data}\n----',
                     klass=self.__class__.__name__,
                     endpoint=self.apiResourceEndpoint,
                     data=query)
        ret = session.post(self.apiResourceEndpoint, json={'query': query})
        return ret.json()

    def getUserInfoFromOAuthClient(self, c):
        if self.apiVersion == 3:
            return self.getUserInfoFromOAuthClient_v3(c)
        return self.getUserInfoFromOAuthClient_v4(c)

    def getUserInfoFromOAuthClient_v3(self, c):
        user = self.get(c, '/user')
        emails = self.get(c, '/user/emails')
        for email in emails:
            if email.get('primary', False):
                user['email'] = email['email']
                break
        orgs = self.get(c, '/user/orgs')
        return dict(full_name=user['name'],
                    email=user['email'],
                    username=user['login'],
                    groups=[org['login'] for org in orgs])

    def getUserInfoFromOAuthClient_v4(self, c):
        graphql_query = textwrap.dedent('''
            query {
              viewer {
                email
                login
                name
                organizations(first: 100) {
                  edges {
                    node {
                      login
                    }
                  }
                }
              }
            }
        ''')
        data = self.post(c, graphql_query.strip())
        data = data['data']
        if self.debug:
            log.info('{klass} GraphQL Response: {response}',
                     klass=self.__class__.__name__,
                     response=data)
        user_info = dict(full_name=data['viewer']['name'],
                         email=data['viewer']['email'],
                         username=data['viewer']['login'],
                         groups=[org['node']['login'] for org in
                                 data['viewer']['organizations']['edges']])
        if self.getTeamsMembership:
            orgs_name_slug_mapping = {
                self._orgname_slug_sub_re.sub('_', n): n
                for n in user_info['groups']}
            graphql_query = self.getUserTeamsGraphqlTplC.render(
                {'user_info': user_info,
                 'organizations': orgs_name_slug_mapping})
            if graphql_query:
                data = self.post(c, graphql_query)
                if self.debug:
                    log.info('{klass} GraphQL Response: {response}',
                             klass=self.__class__.__name__,
                             response=data)
                teams = set()
                for org, team_data in data['data'].items():
                    if team_data is None:
                        # Organizations can have OAuth App access restrictions enabled,
                        # disallowing team data access to third-parties.
                        continue
                    for node in team_data['teams']['edges']:
                        # On github we can mentions organization teams like
                        # @org-name/team-name. Let's keep the team formatting
                        # identical with the inclusion of the organization
                        # since different organizations might share a common
                        # team name
                        teams.add('%s/%s' % (orgs_name_slug_mapping[org], node['node']['name']))
                        teams.add('%s/%s' % (orgs_name_slug_mapping[org], node['node']['slug']))
                user_info['groups'].extend(sorted(teams))
        if self.debug:
            log.info('{klass} User Details: {user_info}',
                     klass=self.__class__.__name__,
                     user_info=user_info)
        return user_info


class GitLabAuth(OAuth2Auth):
    name = "GitLab"
    faIcon = "fa-git"

    def __init__(self, instanceUri, clientId, clientSecret, **kwargs):
        uri = instanceUri.rstrip("/")
        self.authUri = "%s/oauth/authorize" % uri
        self.tokenUri = "%s/oauth/token" % uri
        self.resourceEndpoint = "%s/api/v4" % uri
        super(GitLabAuth, self).__init__(clientId, clientSecret, **kwargs)

    def getUserInfoFromOAuthClient(self, c):
        user = self.get(c, "/user")
        groups = self.get(c, "/groups")
        return dict(full_name=user["name"],
                    username=user["username"],
                    email=user["email"],
                    avatar_url=user["avatar_url"],
                    groups=[g["path"] for g in groups])


class BitbucketAuth(OAuth2Auth):
    name = "Bitbucket"
    faIcon = "fa-bitbucket"
    authUri = 'https://bitbucket.org/site/oauth2/authorize'
    tokenUri = 'https://bitbucket.org/site/oauth2/access_token'
    resourceEndpoint = 'https://api.bitbucket.org/2.0'

    def getUserInfoFromOAuthClient(self, c):
        user = self.get(c, '/user')
        emails = self.get(c, '/user/emails')
        for email in emails["values"]:
            if email.get('is_primary', False):
                user['email'] = email['email']
                break
        orgs = self.get(c, '/teams?role=member')
        return dict(full_name=user['display_name'],
                    email=user['email'],
                    username=user['username'],
                    groups=[org['username'] for org in orgs["values"]])
