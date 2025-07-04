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

from __future__ import annotations

import json
import re
import textwrap
from posixpath import join
from typing import TYPE_CHECKING
from typing import Any
from urllib.parse import parse_qs
from urllib.parse import urlencode

import jinja2
import requests
from twisted.internet import defer
from twisted.internet import threads
from twisted.logger import Logger
from twisted.web.error import Error

import buildbot
from buildbot import config
from buildbot.process.properties import Properties
from buildbot.util import bytes2unicode
from buildbot.www import auth
from buildbot.www import resource

if TYPE_CHECKING:
    from buildbot.master import BuildMaster
    from buildbot.util.twisted import InlineCallbacksType


log = Logger()


class OAuth2LoginResource(auth.LoginResource):
    # disable reconfigResource calls
    needsReconfig = False

    def __init__(self, master: BuildMaster, _auth: OAuth2Auth) -> None:
        super().__init__(master)
        self.auth = _auth

    def render_POST(self, request: Any) -> Any:
        return self.asyncRenderHelper(request, self.renderLogin)

    @defer.inlineCallbacks
    def renderLogin(self, request: Any) -> InlineCallbacksType[Any]:
        code = request.args.get(b"code", [b""])[0]
        if not code:
            url = request.args.get(b"redirect", [None])[0]
            url = yield self.auth.getLoginURL(url)
            raise resource.Redirect(url)

        details = yield self.auth.verifyCode(code)

        if self.auth.userInfoProvider is not None:
            infos = yield self.auth.userInfoProvider.getUserInfo(details['username'])
            details.update(infos)
        session = request.getSession()
        session.user_info = details
        session.updateSession(request)
        state = request.args.get(b"state", [b""])[0]

        assert self.auth.homeUri is not None

        if state:
            for redirect in parse_qs(state).get('redirect', []):
                raise resource.Redirect(self.auth.homeUri + "#" + redirect)
        raise resource.Redirect(self.auth.homeUri)


class OAuth2Auth(auth.AuthBase):
    name = 'oauth2'
    getTokenUseAuthHeaders = False
    authUri: str | None = None
    tokenUri: str | None = None
    grantType = 'authorization_code'
    authUriAdditionalParams: dict[str, str] = {}
    tokenUriAdditionalParams: dict[str, str] = {}
    resourceEndpoint: str = ""  # subclasses should override
    faIcon: str = "not-defined"  # subclasses should override
    loginUri = None
    homeUri = None

    def __init__(
        self,
        clientId: str,
        clientSecret: str,
        autologin: bool = False,
        ssl_verify: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.clientId = clientId
        self.clientSecret = clientSecret
        self.autologin = autologin
        self.ssl_verify = ssl_verify

    def reconfigAuth(self, master: BuildMaster, new_config: Any) -> None:
        self.master = master
        self.loginUri = join(new_config.buildbotURL, "auth/login")
        self.homeUri = new_config.buildbotURL

    def getConfigDict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "oauth2": True,
            "fa_icon": self.faIcon,
            "autologin": self.autologin,
        }

    def getLoginResource(self) -> OAuth2LoginResource:
        return OAuth2LoginResource(self.master, self)

    @defer.inlineCallbacks
    def getLoginURL(self, redirect_url: bytes | None) -> InlineCallbacksType[str]:
        """
        Returns the url to redirect the user to for user consent
        """
        p = Properties()
        p.master = self.master
        clientId = yield p.render(self.clientId)
        oauth_params = {
            'redirect_uri': self.loginUri,
            'client_id': clientId,
            'response_type': 'code',
        }
        if redirect_url is not None:
            oauth_params['state'] = urlencode({"redirect": redirect_url})
        oauth_params.update(self.authUriAdditionalParams)
        sorted_oauth_params = sorted(oauth_params.items(), key=lambda val: val[0])
        return f"{self.authUri}?{urlencode(sorted_oauth_params)}"

    def check_token_error(self, token: dict[str, Any]) -> None:
        error = token.get("error")
        if error:
            error_description = token.get("error_description") or error
            msg = f"OAuth2 session: creation failed: {error_description}".encode()
            raise Error(503, msg)

    def createSessionFromToken(self, token: dict[str, Any]) -> requests.Session:
        s: requests.Session = requests.Session()
        s.params = {'access_token': token['access_token']}
        s.verify = self.ssl_verify
        return s

    def get(self, session: requests.Session, path: str) -> Any:
        ret = session.get(self.resourceEndpoint + path)
        if ret.status_code >= 400:
            msg = f'OAuth2 session: error accessing resource {path}: {ret.status_code}'
            extra_info = ret.headers.get('www-authenticate', None)
            if extra_info:
                msg += f' www-authenticate: {extra_info}'
            raise Error(503, msg.encode('utf-8'))
        return ret.json()

    # based on https://github.com/maraujop/requests-oauth
    # from Miguel Araujo, augmented to support header based clientSecret
    # passing
    @defer.inlineCallbacks
    def verifyCode(self, code: bytes) -> InlineCallbacksType[dict[str, Any]]:
        # everything in deferToThread is not counted with trial  --coverage :-(
        def thd(client_id: str, client_secret: str) -> dict[str, Any]:
            url = self.tokenUri
            data = {'redirect_uri': self.loginUri, 'code': code, 'grant_type': self.grantType}
            auth = None
            if self.getTokenUseAuthHeaders:
                auth = (client_id, client_secret)
            else:
                data.update({'client_id': client_id, 'client_secret': client_secret})
            data.update(self.tokenUriAdditionalParams)
            response = requests.post(url, data=data, timeout=30, auth=auth, verify=self.ssl_verify)
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

            self.check_token_error(content)

            session = self.createSessionFromToken(content)
            return self.getUserInfoFromOAuthClient(session)

        p = Properties()
        p.master = self.master
        client_id = yield p.render(self.clientId)
        client_secret = yield p.render(self.clientSecret)
        result = yield threads.deferToThread(thd, client_id, client_secret)
        return result

    def getUserInfoFromOAuthClient(self, c: requests.Session) -> dict[str, Any]:
        return {}


class GoogleAuth(OAuth2Auth):
    name = "Google"
    faIcon = "fa-google-plus"
    resourceEndpoint = "https://www.googleapis.com/oauth2/v1"
    authUri = 'https://accounts.google.com/o/oauth2/auth'
    tokenUri = 'https://accounts.google.com/o/oauth2/token'
    authUriAdditionalParams = {
        "scope": ' '.join([
            'https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/userinfo.profile',
        ])
    }

    def getUserInfoFromOAuthClient(self, c: requests.Session) -> dict[str, Any]:
        data = self.get(c, '/userinfo')
        return {
            "full_name": data["name"],
            "username": data['email'].split("@")[0],
            "email": data["email"],
            "avatar_url": data["picture"],
        }


class GitHubAuth(OAuth2Auth):
    name = "GitHub"
    faIcon = "fa-github"
    authUri = 'https://github.com/login/oauth/authorize'
    authUriAdditionalParams = {'scope': 'user:email read:org'}
    tokenUri = 'https://github.com/login/oauth/access_token'
    resourceEndpoint = 'https://api.github.com'

    getUserTeamsGraphqlTpl = textwrap.dedent(r"""
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
    """)

    def __init__(
        self: GitHubAuth,
        clientId: str,
        clientSecret: str,
        serverURL: str | None = None,
        autologin: bool = False,
        apiVersion: int = 3,
        getTeamsMembership: bool = False,
        debug: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(clientId, clientSecret, autologin, **kwargs)
        self.apiResourceEndpoint = None
        if serverURL is not None:
            # setup for enterprise github
            serverURL = serverURL.rstrip("/")
            # v3 is accessible directly at /api/v3 for enterprise, but directly for SaaS..
            self.resourceEndpoint = serverURL + '/api/v3'
            # v4 is accessible endpoint for enterprise
            self.apiResourceEndpoint = serverURL + '/api/graphql'

            self.authUri = f'{serverURL}/login/oauth/authorize'
            self.tokenUri = f'{serverURL}/login/oauth/access_token'
        self.serverURL = serverURL or self.resourceEndpoint

        if apiVersion not in (3, 4):
            config.error(f'GitHubAuth apiVersion must be 3 or 4 not {apiVersion}')
        self.apiVersion = apiVersion
        if apiVersion == 3:
            if getTeamsMembership is True:
                config.error(
                    'Retrieving team membership information using GitHubAuth is only '
                    'possible using GitHub api v4.'
                )
        else:
            defaultGraphqlEndpoint = self.serverURL + '/graphql'
            self.apiResourceEndpoint = self.apiResourceEndpoint or defaultGraphqlEndpoint
        if getTeamsMembership:
            # GraphQL name aliases must comply with /^[_a-zA-Z][_a-zA-Z0-9]*$/
            self._orgname_slug_sub_re = re.compile(r'[^_a-zA-Z0-9]')
            self.getUserTeamsGraphqlTplC = jinja2.Template(self.getUserTeamsGraphqlTpl.strip())
        self.getTeamsMembership = getTeamsMembership
        self.debug = debug

    def post(self, session: requests.Session, query: str) -> Any:
        if self.debug:
            log.info(
                '{klass} GraphQL POST Request: {endpoint} -> DATA:\n----\n{data}\n----',
                klass=self.__class__.__name__,
                endpoint=self.apiResourceEndpoint,
                data=query,
            )
        ret = session.post(self.apiResourceEndpoint, json={'query': query})
        return ret.json()

    def getUserInfoFromOAuthClient(self, c: requests.Session) -> dict[str, Any]:
        if self.apiVersion == 3:
            return self.getUserInfoFromOAuthClient_v3(c)
        return self.getUserInfoFromOAuthClient_v4(c)

    def getUserInfoFromOAuthClient_v3(self, c: requests.Session) -> dict[str, Any]:
        user = self.get(c, '/user')
        emails = self.get(c, '/user/emails')
        for email in emails:
            if email.get('primary', False):
                user['email'] = email['email']
                break
        orgs = self.get(c, '/user/orgs')
        return {
            "full_name": user['name'],
            "email": user['email'],
            "username": user['login'],
            "groups": [org['login'] for org in orgs],
        }

    def createSessionFromToken(self, token: dict[str, Any]) -> requests.Session:
        s = requests.Session()
        s.headers = {
            'Authorization': 'token ' + token['access_token'],
            'User-Agent': f'buildbot/{buildbot.version}',
        }
        s.verify = self.ssl_verify
        return s

    def getUserInfoFromOAuthClient_v4(self, c: requests.Session) -> dict[str, Any]:
        graphql_query = textwrap.dedent("""
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
        """)
        data = self.post(c, graphql_query.strip())
        data = data['data']
        if self.debug:
            log.info(
                '{klass} GraphQL Response: {response}', klass=self.__class__.__name__, response=data
            )
        user_info = {
            "full_name": data['viewer']['name'],
            "email": data['viewer']['email'],
            "username": data['viewer']['login'],
            "groups": [org['node']['login'] for org in data['viewer']['organizations']['edges']],
        }
        if self.getTeamsMembership:
            orgs_name_slug_mapping = {
                self._orgname_slug_sub_re.sub('_', n): n for n in user_info['groups']
            }
            graphql_query = self.getUserTeamsGraphqlTplC.render({
                'user_info': user_info,
                'organizations': orgs_name_slug_mapping,
            })
            if graphql_query:
                data = self.post(c, graphql_query)
                if self.debug:
                    log.info(
                        '{klass} GraphQL Response: {response}',
                        klass=self.__class__.__name__,
                        response=data,
                    )
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
                        teams.add(f"{orgs_name_slug_mapping[org]}/{node['node']['name']}")
                        teams.add(f"{orgs_name_slug_mapping[org]}/{node['node']['slug']}")
                user_info['groups'].extend(sorted(teams))
        if self.debug:
            log.info(
                '{klass} User Details: {user_info}',
                klass=self.__class__.__name__,
                user_info=user_info,
            )
        return user_info


class GitLabAuth(OAuth2Auth):
    name = "GitLab"
    faIcon = "fa-git"

    def __init__(self, instanceUri: str, clientId: str, clientSecret: str, **kwargs: Any) -> None:
        uri = instanceUri.rstrip("/")
        self.authUri = f"{uri}/oauth/authorize"
        self.tokenUri = f"{uri}/oauth/token"
        self.resourceEndpoint = f"{uri}/api/v4"
        super().__init__(clientId, clientSecret, **kwargs)

    def getUserInfoFromOAuthClient(self, c: requests.Session) -> dict[str, Any]:
        user = self.get(c, "/user")
        groups = self.get(c, "/groups")
        return {
            "full_name": user["name"],
            "username": user["username"],
            "email": user["email"],
            "avatar_url": user["avatar_url"],
            "groups": [g["path"] for g in groups],
        }


class BitbucketAuth(OAuth2Auth):
    name = "Bitbucket"
    faIcon = "fa-bitbucket"
    authUri = 'https://bitbucket.org/site/oauth2/authorize'
    tokenUri = 'https://bitbucket.org/site/oauth2/access_token'
    resourceEndpoint = 'https://api.bitbucket.org/2.0'

    def getUserInfoFromOAuthClient(self, c: requests.Session) -> dict[str, Any]:
        user = self.get(c, '/user')
        emails = self.get(c, '/user/emails')
        for email in emails["values"]:
            if email.get('is_primary', False):
                user['email'] = email['email']
                break
        orgs = self.get(c, '/workspaces?role=member')
        return {
            "full_name": user['display_name'],
            "email": user['email'],
            "username": user['username'],
            "groups": [org['slug'] for org in orgs["values"]],
        }


class KeyCloakAuth(OAuth2Auth):
    name = "KeyCloak"
    faIcon = "fa-key"

    authUriAdditionalParams = {"scope": "openid"}

    def __init__(
        self, instance_uri: str, realm: str, client_id: str, client_secret: str, **kwargs: Any
    ) -> None:
        uri = instance_uri.rstrip("/")
        self.authUri = f"{uri}/realms/{realm}/protocol/openid-connect/auth"
        self.tokenUri = f"{uri}/realms/{realm}/protocol/openid-connect/token"
        self.resourceEndpoint = f"{uri}/realms/{realm}"
        super().__init__(client_id, client_secret, **kwargs)

    def createSessionFromToken(self, token: dict[str, Any]) -> requests.Session:
        s = requests.Session()
        s.headers = {
            'Authorization': 'Bearer ' + token['access_token'],
            'User-Agent': f'buildbot/{buildbot.version}',
        }
        s.verify = self.ssl_verify
        return s

    def getUserInfoFromOAuthClient(self, c: requests.Session) -> dict[str, Any]:
        user = self.get(c, "/protocol/openid-connect/userinfo")
        log.info('qqq {user}', user=user)
        return {
            "full_name": user.get("name", ""),
            "username": user.get("preferred_username", ""),
            "email": user.get("email", ""),
            "avatar_url": user.get("picture", ""),
            "groups": list(user.get("groups", [])),
        }
