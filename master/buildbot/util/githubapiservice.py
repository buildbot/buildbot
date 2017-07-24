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

import datetime
import pprint
import textwrap
import time
from collections import OrderedDict
from collections import namedtuple

import jinja2
import jwt

from twisted.internet import defer

from buildbot.util.httpclientservice import HTTPClientService
from buildbot.util.logger import Logger
from buildbot.util.service import SharedService

log = Logger()

InstallationAuthorization = namedtuple('InstallationAuthorization', ['token', 'expires_at', 'on_behalf_of'])


class GithubIntegration(SharedService):

    API_ROOT_URL = 'https://api.github.com'

    def __init__(self, integration_id, private_key, api_root_url=None,
                 debug=False, verify=None, **kwargs):
        super(GithubIntegration, self).__init__()
        self.integration_id = integration_id
        self.private_key = private_key
        self.api_root_url = api_root_url or self.API_ROOT_URL
        self.debug = debug
        self.verify = verify
        self._tokens = {}
        self._http = None

    # Totally inspired in PyGithub https://goo.gl/xKXUtr

    @defer.inlineCallbacks
    def get_http_client(self):
        if self._http is None:
            self._http = yield HTTPClientService.getService(
                self.master,
                self.api_root_url,
                headers={'User-Agent': 'Buildbot'},
                debug=self.debug, verify=self.verify)
        defer.returnValue(self._http)

    def create_jwt(self):
        """
        Creates a signed JWT, valid for 60 seconds
        """
        now = int(time.time())
        payload = {
            "iat": now,
            "exp": now + 60,
            "iss": self.integration_id
        }
        return jwt.encode(
            payload,
            key=self.private_key,
            algorithm="RS256"
        )

    @defer.inlineCallbacks
    def get_access_token(self, installation_id, user_id=None):
        """
        Get an access token for the given installation id.
        POSTs https://api.github.com/installations/<installation_id>/access_tokens
        :param user_id: int
        :param installation_id: int
        """
        iauth = self._tokens.get((installation_id, user_id), None)
        if iauth is not None:
            if iauth.expires_at < (datetime.datetime.utcnow() + datetime.timedelta(minutes=5)):
                self._tokens.pop((installation_id, user_id))
                iauth = None
        elif iauth is None:
            body = None
            if user_id:
                body = {"user_id": user_id}

            client = yield self.get_http_client()
            response = yield client.post(
                "/installations/{}/access_tokens".format(installation_id),
                headers={
                    "Authorization": "Bearer {}".format(self.create_jwt()),
                    "Accept": "application/vnd.github.machine-man-preview+json",
                },
                json=body
            )

            if response.code == 201:
                data = yield response.json()
                token = data['token']
                expires_at = data['expires_at']
                if len(expires_at) == 25:
                    expires_at = datetime.datetime.strptime(
                        expires_at[:19], "%Y-%m-%dT%H:%M:%S") + (
                                1 if expires_at[19] == '-' else -1) * datetime.timedelta(
                                        hours=int(expires_at[20:22]),
                                        minutes=int(expires_at[23:25]))
                else:
                    expires_at = datetime.datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%SZ")
                on_behalf_of = data.get('on_behalf_of', None)
                iauth = InstallationAuthorization(token, expires_at, on_behalf_of)
                self._tokens[(installation_id, user_id)] = iauth
            else:
                iauth = InstallationAuthorization(None, None, None)
                body = yield response.content()
                log.warn(
                    'Unable to get GitHub installation auth token. HTTP Code: {code}. '
                    'Error: {error}',
                    code=response.code,
                    error=body
                )
        defer.returnValue(iauth)


class GithubApiService(SharedService):

    API_ROOT_URL = 'https://api.github.com'

    def __init__(self,
                 oauth_token=None,
                 integration_id=None,
                 private_key=None,
                 installation_id=None,
                 api_root_url=None,
                 debug=False,
                 verify=None):
        super(GithubApiService, self).__init__()
        self.oauth_token = oauth_token
        self.integration_id = integration_id
        self.private_key = private_key
        self.installation_id = installation_id
        self.debug = debug
        self.verify = verify
        self.api_root_url = api_root_url or self.API_ROOT_URL
        self._github_integration = None
        self._api_rate_limit = None
        self._api_rate_limit_remaining = None
        self._api_rate_limit_reset = None
        self._http = None

    @defer.inlineCallbacks
    def get_http_client(self):
        if self._http is None:
            self._http = yield HTTPClientService.getService(
                self.master,
                self.api_root_url,
                headers={'User-Agent': 'Buildbot'},
                debug=self.debug, verify=self.verify)
        defer.returnValue(self._http)

    @defer.inlineCallbacks
    def get_oauth_token(self):
        yield self.get_http_client()
        if self.oauth_token:
            token = self.oauth_token
        else:
            if self._github_integration is None:
                self._github_integration = yield GithubIntegration.getService(
                    self.master,
                    self.integration_id,
                    self.private_key,
                    api_root_url=self.api_root_url,
                    debug=self.debug,
                    verify=self.verify
                )
            token = yield self._github_integration.get_access_token(self.installation_id)
        defer.returnValue(token)

    @defer.inlineCallbacks
    def _prepare_request(self, endpoint, **kwargs):
        headers = kwargs.get('headers', {})
        if 'Authorization' not in headers:
            oauth_token = yield self.get_oauth_token()
            headers['Authorization'] = 'token ' + oauth_token
            kwargs['headers'] = headers
        defer.returnValue((endpoint, kwargs))

    @defer.inlineCallbacks
    def _get(self, endpoint, **kwargs):
        endpoint, kwargs = yield self._prepare_request(endpoint, **kwargs)
        deferred = self._http.get(endpoint, **kwargs)
        deferred.addCallback(self._update_rate_limit_information)
        response = yield deferred
        defer.returnValue(response)

    @defer.inlineCallbacks
    def _post(self, endpoint, **kwargs):
        endpoint, kwargs = yield self._prepare_request(endpoint, **kwargs)
        deferred = self._http.post(endpoint, **kwargs)
        deferred.addCallback(self._update_rate_limit_information)
        response = yield deferred
        defer.returnValue(response)

    def _update_rate_limit_information(self, response):
        if self.debug:
            log.info('Response Headers:\n{headers}',
                     headers=pprint.pformat(response.headers))
        api_rate_limit = response.headers.get('X-RateLimit-Limit') or None
        if api_rate_limit:
            self._api_rate_limit = int(api_rate_limit)
        api_rate_limit_remaining = response.headers.get('X-RateLimit-Remaining') or None
        if api_rate_limit_remaining:
            self._api_rate_limit_remaining = int(api_rate_limit_remaining)
        api_rate_limit_reset = response.headers.get('X-RateLimit-Reset') or None
        if api_rate_limit_reset:
            self._api_rate_limit_reset = datetime.datetime.utcfromtimestamp(int(api_rate_limit_reset))
        self._log_rate_limit_information()
        return response

    def _log_rate_limit_information(self):
        if not self._api_rate_limit or \
                not self._api_rate_limit_reset or \
                not self._api_rate_limit_reset:
            return
        log.info(
            'GitHub API rate limit information. Limit: {limit}; '
            'Remaining: {remaining}; Reset: {reset} UTC;',
            limit=self._api_rate_limit,
            remaining=self._api_rate_limit_remaining,
            reset=self._api_rate_limit_reset)

    @defer.inlineCallbacks
    def get_pull_request_changes(self, repo_owner, repo_name, pr_num,
                                 graphql_template=None):
        compiled_template = getattr(self, 'getPrDetailsTplC', None)
        if compiled_template is None:
            if graphql_template is None:
                graphql_template = textwrap.dedent('''
                    query getPrDetails {
                      repository(owner: "{{ repo_owner }}", name: "{{ repo_name }}") {
                        pullRequest(number: {{ pr_num }}) {
                          commits(first: 100 {%- if end_cursor %}, after: "{{ end_cursor }}"{% endif %}) {
                            pageInfo {
                              endCursor
                              hasNextPage
                            }
                            nodes {
                              commit {
                                oid
                                message
                                messageBody
                                messageHeadline
                                author {
                                  name
                                  email
                                  user {
                                    login
                                  }
                                }
                              }
                            }
                          }
                        }
                      }
                    }
                ''').strip()
            compiled_template = self.getPrDetailsTplC = jinja2.Template(graphql_template)

        # We might have to paginate all data, so, loop in a while True loop until we have all
        # the information we need
        end_cursor = None
        changes = OrderedDict()

        while True:
            graphql_query = compiled_template.render(
                repo_owner=repo_owner,
                repo_name=repo_name,
                pr_num=pr_num,
                end_cursor=end_cursor)

            if self.debug:
                log.info('{klass} GraphQL POST Request: -> '
                         'DATA:\n----\n{query}\n----',
                         klass=self.__class__.__name__,
                         query=graphql_query)
            # POST the GraphQL query
            response = yield self._post('/graphql', json={'query': graphql_query})
            if response.code != 200:
                content = yield response.content()
                log.error("{code}: unable to POST GraphQL query: {content}",
                          code=response.code, content=content)
                break

            data = yield response.json()
            if 'errors' in data:
                log.error('Unable to send query. Errors: {errors}', errors=data['errors'])
                break
            if 'data' not in data:
                log.error('Unable to retrieve query response out of: {data}', data=data)
                break

            data = data['data']
            if self.debug:
                log.info('{klass} GraphQL Response: {response}',
                         klass=self.__class__.__name__,
                         response=data)

            if data['repository']['pullRequest']['commits']['pageInfo']['hasNextPage']:
                # Do we have a next page? If so, get the endCursor to pass along to
                # the next query
                end_cursor = data['repository']['pullRequest']['commits']['pageInfo']['endCursor']
            else:
                end_cursor = None

            for node in data['repository']['pullRequest']['commits']['nodes']:
                change_author_login = node['commit']['author']['user']['login']

                change_author = u'{} <{}>'.format(node['commit']['author']['name'],
                                                  node['commit']['author']['email'])

                sha = node['commit']['oid']
                title = node['commit']['messageHeadline']
                body = node['commit']['messageBody']
                message = node['commit']['message']
                changes[sha] = {
                    'login': change_author_login,
                    'author': change_author,
                    'title': title,
                    'body': body,
                    'message': message
                }

            if end_cursor is None:
                # No next page? Break the loop
                break

        defer.returnValue(changes)

    @defer.inlineCallbacks
    def get_pull_request_changed_files(self, repo_owner, repo_name, pr_num):
        response = yield self._get(
            '/repos/{}/{}/pulls/{}/files'.format(repo_owner, repo_name, pr_num),
            headers={'Accept': 'application/vnd.github.v3+json'})
        files = set()
        changed_files = yield response.json()
        if self.debug:
            log.info(
                'Changed files payload listing for {owner}/{repo} PR#{num}: {files}',
                owner=repo_owner, repo=repo_name, num=pr_num, files=changed_files
            )
        for payload in changed_files:
            files.add(payload['filename'])
        defer.returnValue(sorted(files))
