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
import time
from collections import namedtuple

import jwt

from twisted.internet import defer

from buildbot.util.httpclientservice import HTTPClientService
from buildbot.util.logger import Logger
from buildbot.util.service import SharedService

log = Logger()


class GithubApiService(SharedService):

    API_ROOT_URL = 'https://api.github.com'

    InstallationAuthorization = namedtuple('InstallationAuthorization',
                                           ['token', 'expires_at', 'on_behalf_of'])

    def __init__(self,
                 oauth_token=None,
                 integration_id=None,
                 private_key=None,
                 installation_id=None,
                 api_root_url=None,
                 verify=False,
                 debug=False):

        super(GithubApiService, self).__init__()

        self.oauth_token = oauth_token
        self.integration_id = integration_id
        self.private_key = private_key
        self.installation_id = installation_id
        if api_root_url is None:
            api_root_url = self.API_ROOT_URL
        if api_root_url.endswith('/'):
            api_root_url = api_root_url[:-1]
        self.api_root_url = api_root_url
        self.verify = verify
        self.debug = debug
        self._api_rate_limit = None
        self._api_rate_limit_remaining = None
        self._api_rate_limit_reset = None
        self._jwt_token = self._jwt_token_expire = None
        self._access_tokens = {}
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
        # Get the asked for oauth_token
        if self.integration_id and self.private_key and self.installation_id:
            token = yield self.get_access_token()
        else:
            token = self.oauth_token
        defer.returnValue(token)

    def get_jwt_token(self):
        """
        Creates a signed JWT, valid for 10 minutes which is the maximum
        GitHub allows
        """
        log.info('Getting JST Token. Token: {token}; Expire: {expire}; Now: {now}',
                 token=self._jwt_token, expire=self._jwt_token_expire, now=int(time.time()))
        if self._jwt_token is not None:
            if self._jwt_token_expire < int(time.time()):
                self._jwt_token = self._jwt_token_expire = None
        if self._jwt_token is None:
            now = int(time.time())
            # Maximum token age GitHub allows is 10 minutes. We generate the token
            # for just 8 minutes to allow some clock skew
            token_expire = now + 60 * 8
            payload = {
                "iat": now,
                "exp": token_expire,
                "iss": self.integration_id
            }
            self._jwt_token_expire = token_expire
            if self.debug:
                log.info('Generated JWT Token at {now}: {token}',
                         now=datetime.datetime.utcnow(), token=payload)
            self._jwt_token = jwt.encode(
                payload,
                key=self.private_key,
                algorithm="RS256"
            )
        return self._jwt_token

    @defer.inlineCallbacks
    def get_access_token(self, user_id=None):
        """
        Get an access token for the given installation id.
        POSTs https://api.github.com/installations/<installation_id>/access_tokens
        """
        if self._access_tokens.get(user_id, None) is not None:
            expire_date = datetime.datetime.utcnow() + datetime.timedelta(minutes=5)
            if self._access_tokens[user_id].expires_at < expire_date:
                self._access_tokens.pop(user_id)
        if self._access_tokens.get(user_id, None) is None:
            body = None
            if user_id:
                body = {"user_id": user_id}

            client = yield self.get_http_client()
            response = yield client.post(
                "/installations/{}/access_tokens".format(self.installation_id),
                headers={
                    "Authorization": "Bearer {}".format(self.get_jwt_token()),
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
                self._access_tokens[user_id] = self.InstallationAuthorization(
                    token,
                    expires_at,
                    on_behalf_of)
            else:
                body = yield response.content()
                log.warn(
                    'Unable to get GitHub installation auth token. HTTP Code: {code}. '
                    'Error: {error}',
                    code=response.code,
                    error=body
                )
        if self._access_tokens.get(user_id, None) is not None:
            defer.returnValue(self._access_tokens[user_id].token)
        else:
            defer.returnValue(None)

    @defer.inlineCallbacks
    def _doRequest(self, method, endpoint, **kwargs):
        client = yield self.get_http_client()
        request_kwargs = yield self._prepare_request_kwargs(**kwargs)
        deferred = getattr(client, method)(endpoint, **request_kwargs)
        deferred.addCallback(self._update_rate_limit_information)
        response = yield deferred
        defer.returnValue(response)

    def get(self, endpoint, **kwargs):
        return self._doRequest('get', endpoint, **kwargs)

    def post(self, endpoint, **kwargs):
        return self._doRequest('post', endpoint, **kwargs)

    def put(self, endpoint, **kwargs):
        return self._doRequest('put', endpoint, **kwargs)

    def delete(self, endpoint, **kwargs):
        return self._doRequest('delete', endpoint, **kwargs)

    @defer.inlineCallbacks
    def _prepare_request_kwargs(self, **kwargs):
        headers = kwargs.get('headers', {})
        if 'Authorization' not in headers:
            oauth_token = yield self.get_oauth_token()
            if oauth_token:
                headers['Authorization'] = 'token ' + oauth_token
                kwargs['headers'] = headers
        defer.returnValue(kwargs)

    def _update_rate_limit_information(self, response):
        if self.debug:
            log.info('Response Headers:\n{headers}',
                     headers=pprint.pformat(response.headers))
        api_rate_limit = response.headers.getRawHeaders(b'X-RateLimit-Limit', default=None)
        if api_rate_limit:
            self._api_rate_limit = int(api_rate_limit[0])
        api_rate_limit_remaining = response.headers.getRawHeaders(b'X-RateLimit-Remaining', default=None)
        if api_rate_limit_remaining:
            self._api_rate_limit_remaining = int(api_rate_limit_remaining[0])
        api_rate_limit_reset = response.headers.getRawHeaders(b'X-RateLimit-Reset', default=None)
        if api_rate_limit_reset:
            self._api_rate_limit_reset = datetime.datetime.utcfromtimestamp(int(api_rate_limit_reset[0]))
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
