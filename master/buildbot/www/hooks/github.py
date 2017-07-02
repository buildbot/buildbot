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
import hmac
import json
import pprint
import re
import textwrap
from hashlib import sha1

from dateutil.parser import parse as dateparse

import jinja2
from twisted.internet import defer

from buildbot.changes.github import PullRequestMixin
from buildbot.util import bytes2unicode
from buildbot.util import httpclientservice
from buildbot.util import unicode2bytes
from buildbot.util.logger import Logger
from buildbot.www.hooks.base import BaseHookHandler

_HEADER_EVENT = b'X-GitHub-Event'
_HEADER_SIGNATURE = b'X-Hub-Signature'

DEFAULT_SKIPS_PATTERN = (r'\[ *skip *ci *\]', r'\[ *ci *skip *\]')
DEFAULT_GITHUB_API_URL = 'https://api.github.com'

log = Logger()


class GitHubEventHandler(PullRequestMixin):

    getPrCommitAuthorDetailsTpl = textwrap.dedent('''
        query repoCommitsOwners {
          repository(owner: "{{ repo_owner }}", name: "{{ repo_name }}") {
            pullRequest(number: {{ pr_num }}) {
              commits(first: 100 {%- if end_cursor %}, after: "{{ end_cursor }}"{% endif %}) {
                pageInfo {
                  endCursor
                  hasNextPage
                }
                nodes {
                  commit {
                    abbreviatedOid
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

    def __init__(self, secret, strict,
                 codebase=None,
                 github_property_whitelist=None,
                 master=None,
                 skips=None,
                 oauth_token=None,
                 github_api_endpoint='https://api.github.com',
                 debug=False,
                 verify=False):
        self._secret = secret
        self._strict = strict
        self._codebase = codebase
        self.github_property_whitelist = github_property_whitelist
        self.skips = skips
        self.github_api_endpoint = github_api_endpoint
        self.master = master
        if github_property_whitelist is None:
            self.github_property_whitelist = []
        if skips is None:
            self.skips = DEFAULT_SKIPS_PATTERN
        if github_api_endpoint is None:
            self.github_api_endpoint = DEFAULT_GITHUB_API_URL

        if self._strict and not self._secret:
            raise ValueError('Strict mode is requested '
                             'while no secret is provided')
        self.oauth_token = oauth_token
        self.github_api_endpoint = github_api_endpoint
        self.debug = debug
        self.verify = verify
        self._http = None
        self._api_rate_limit = None
        self._api_rate_limit_remaining = None
        self._api_rate_limit_reset = None
        if oauth_token is not None:
            self._user_details_cache = {}
            self.getPrCommitAuthorDetailsTplC = jinja2.Template(
                self.getPrCommitAuthorDetailsTpl
            )

    @defer.inlineCallbacks
    def process(self, request):
        payload = self._get_payload(request)

        event_type = request.getHeader(_HEADER_EVENT)
        event_type = bytes2unicode(event_type)
        log.debug("X-GitHub-Event: {event_type}", event_type=event_type)

        handler = getattr(self, 'handle_{}'.format(event_type), None)

        if handler is None:
            raise ValueError('Unknown event: {}'.format(event_type))

        result = yield defer.maybeDeferred(lambda: handler(payload, event_type))
        self._log_rate_limit_information()
        defer.returnValue(result)

    def _get_payload(self, request):
        content = request.content.read()
        content = bytes2unicode(content)

        signature = request.getHeader(_HEADER_SIGNATURE)
        signature = bytes2unicode(signature)

        if not signature and self._strict:
            raise ValueError('Request has no required signature')

        if self._secret and signature:
            try:
                hash_type, hexdigest = signature.split('=')
            except ValueError:
                raise ValueError(
                    'Wrong signature format: {}'.format(signature))

            if hash_type != 'sha1':
                raise ValueError('Unknown hash type: {}'.format(hash_type))

            mac = hmac.new(unicode2bytes(self._secret),
                           msg=unicode2bytes(content),
                           digestmod=sha1)
            # NOTE: hmac.compare_digest should be used, but it's only available
            # starting Python 2.7.7
            if mac.hexdigest() != hexdigest:
                raise ValueError('Hash mismatch')

        content_type = request.getHeader(b'Content-Type')

        if content_type == b'application/json':
            payload = json.loads(content)
        elif content_type == b'application/x-www-form-urlencoded':
            payload = json.loads(bytes2unicode(request.args[b'payload'][0]))
        else:
            raise ValueError('Unknown content type: {}'.format(content_type))

        log.debug("Payload: {payload}", payload=payload)

        return payload

    def handle_ping(self, _, __):
        return [], 'git'

    def handle_push(self, payload, event):
        # This field is unused:
        user = None
        # user = payload['pusher']['name']
        repo = payload['repository']['name']
        repo_url = payload['repository']['html_url']
        # NOTE: what would be a reasonable value for project?
        # project = request.args.get('project', [''])[0]
        project = payload['repository']['full_name']

        # Inject some additional white-listed event payload properties
        properties = self.extractProperties(payload)
        changes = self._process_change(payload, user, repo, repo_url, project,
                                       event, properties)

        log.info("Received {num_changes} changes from github", num_changes=len(changes))

        return changes, 'git'

    @defer.inlineCallbacks
    def handle_pull_request(self, payload, event):
        changes = []
        number = payload['number']
        refname = 'refs/pull/{}/merge'.format(number)
        commits = payload['pull_request']['commits']
        title = payload['pull_request']['title']
        comments = payload['pull_request']['body']
        repo_full_name = payload['repository']['full_name']
        head_sha = payload['pull_request']['head']['sha']

        log.debug('Processing GitHub PR #{pr_num}', pr_num=number)

        head_msg = yield self._get_commit_msg(repo_full_name, head_sha)
        if self._has_skip(head_msg):
            log.info("GitHub PR #{pr_num}, Ignoring: head commit message "
                     "contains skip pattern", pr_num=number)
            defer.returnValue(([], 'git'))

        action = payload.get('action')
        if action not in ('opened', 'reopened', 'synchronize'):
            log.info("GitHub PR #{pr_num} {action}, ignoring", pr_num=number, action=action)
            defer.returnValue((changes, 'git'))

        properties = self.extractProperties(payload['pull_request'])
        properties.update({'event': event})
        files = None
        change_author = None
        user_login = payload['pull_request']['user']['login']
        repo_owner = payload['pull_request']['base']['user']['login']
        repo_name = payload['pull_request']['base']['repo']['name']
        if self.oauth_token is not None:
            files = yield self._get_changed_files(repo_owner, repo_name, number)
            change_author = self._user_details_cache.get(user_login, None)
            if change_author is None:
                change_author = yield self._fetch_user_details(
                    user_login,
                    repo_owner=payload['pull_request']['base']['user']['login'],
                    repo_name=payload['pull_request']['base']['repo']['name'],
                    pr_num=number,
                )

        if change_author is None:
            # The owner should be the pull request owner, not the
            # event sender
            change_author = user_login

        change = {
            'revision': payload['pull_request']['head']['sha'],
            'when_timestamp': dateparse(payload['pull_request']['created_at']),
            'branch': refname,
            'revlink': payload['pull_request']['_links']['html']['href'],
            'repository': payload['repository']['html_url'],
            'project': payload['pull_request']['base']['repo']['full_name'],
            'category': 'pull',
            'author': change_author,
            'comments': u'GitHub Pull Request #{0} ({1} commit{2})\n{3}\n{4}'.format(
                number, commits, 's' if commits != 1 else '', title, comments),
            'properties': properties,
        }
        if files is not None:
            change['files'] = files

        if callable(self._codebase):
            change['codebase'] = self._codebase(payload)
        elif self._codebase is not None:
            change['codebase'] = self._codebase

        changes.append(change)

        log.info("Received {num_changes} changes from GitHub PR #{pr_num}",
                 num_changes=len(changes), pr_num=number)
        defer.returnValue((changes, 'git'))

    @defer.inlineCallbacks
    def _get_commit_msg(self, repo, sha):
        '''
        :param repo: the repo full name, ``{owner}/{project}``.
            e.g. ``buildbot/buildbot``
        '''
        url = '/repos/{}/commits/{}'.format(repo, sha)
        http = yield httpclientservice.HTTPClientService.getService(
            self.master, self.github_api_endpoint,
            debug=self.debug, verify=self.verify)
        res = yield http.get(url)
        data = yield res.json()
        msg = data['commit']['message']
        defer.returnValue(msg)

    def _process_change(self, payload, user, repo, repo_url, project, event,
                        properties):
        """
        Consumes the JSON as a python object and actually starts the build.

        :arguments:
            payload
                Python Object that represents the JSON sent by GitHub Service
                Hook.
        """
        changes = []
        refname = payload['ref']

        # We only care about regular heads or tags
        match = re.match(r"^refs/(heads|tags)/(.+)$", refname)
        if not match:
            log.info("Ignoring refname '{refname}': Not a branch", refname=refname)
            return changes

        branch = match.group(2)
        if payload.get('deleted'):
            log.info("Branch '{branch}' deleted, ignoring", branch=branch)
            return changes

        # check skip pattern in commit message. e.g.: [ci skip] and [skip ci]
        head_msg = payload['head_commit'].get('message', '')
        if self._has_skip(head_msg):
            return changes

        for commit in payload['commits']:
            files = []
            for kind in ('added', 'modified', 'removed'):
                files.extend(commit.get(kind, []))

            when_timestamp = dateparse(commit['timestamp'])

            log.info("New revision: {revision}", revision=commit['id'][:8])

            change = {
                'author': u'{} <{}>'.format(commit['author']['name'],
                                            commit['author']['email']),
                'files': files,
                'comments': commit['message'],
                'revision': commit['id'],
                'when_timestamp': when_timestamp,
                'branch': branch,
                'revlink': commit['url'],
                'repository': repo_url,
                'project': project,
                'properties': {
                    'github_distinct': commit.get('distinct', True),
                    'event': event,
                },
            }
            # Update with any white-listed github event properties
            change['properties'].update(properties)

            if callable(self._codebase):
                change['codebase'] = self._codebase(payload)
            elif self._codebase is not None:
                change['codebase'] = self._codebase

            changes.append(change)

        return changes

    def _has_skip(self, msg):
        '''
        The message contains the skipping keyword no not.

        :return type: Bool
        '''
        for skip in self.skips:
            if re.search(skip, msg):
                return True
        return False

    @defer.inlineCallbacks
    def _get_http_client(self):
        if self._http is None:
            # Instanticate an http client service to user
            self._http = yield httpclientservice.HTTPClientService.getService(
                self.master, self.github_api_endpoint, headers={
                    'Authorization': 'token ' + self.oauth_token,
                    'User-Agent': 'Buildbot',
                    'Accept': 'application/vnd.github.v3+json'
                },
                debug=self.debug, verify=self.verify)
            # Get rate limits
            response = yield self._http.get('/rate_limit')
            rate_limit_info = yield response.json()
            core_limits = rate_limit_info['resources']['core']
            self._api_rate_limit = core_limits['limit']
            self._api_rate_limit_remaining = core_limits['remaining']
            self._api_rate_limit_reset = datetime.datetime.utcfromtimestamp(core_limits['reset'])
            self._log_rate_limit_information()
        defer.returnValue(self._http)

    def _update_rate_limit_information(self, response):
        log.info('Response Headers:\n{headers}', headers=pprint.pformat(response.headers))
        api_rate_limit = response.headers.get('X-RateLimit-Limit') or None
        if api_rate_limit:
            self._api_rate_limit = int(api_rate_limit)
        api_rate_limit_remaining = response.headers.get('X-RateLimit-Remaining') or None
        if api_rate_limit_remaining:
            self._api_rate_limit_remaining = int(api_rate_limit_remaining)
        api_rate_limit_reset = response.headers.get('X-RateLimit-Reset') or None
        if api_rate_limit_reset:
            self._api_rate_limit_reset = datetime.datetime.utcfromtimestamp(int(api_rate_limit_reset))

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
    def _fetch_user_details(self, login,
                            repo_owner=None,
                            repo_name=None,
                            pr_num=None):

        httpclient = yield self._get_http_client()

        end_cursor = None
        ret_change_author = None

        while True:
            graphql_query = self.getPrCommitAuthorDetailsTplC.render(
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
            response = yield httpclient.post('/graphql', json={'query': graphql_query})
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
                if change_author_login is None:
                    # Migrated repositories don't always have a correspoding GitHub
                    # user account
                    continue

                if change_author_login in self._user_details_cache:
                    continue

                change_author = u'{} <{}>'.format(node['commit']['author']['name'],
                                                  node['commit']['author']['email'])

                self._user_details_cache[change_author_login] = change_author
                if change_author_login == login:
                    ret_change_author = change_author

            if end_cursor is None:
                # No next page? Break the loop
                break

        # Return the matching change_author login
        defer.returnValue(ret_change_author)

    @defer.inlineCallbacks
    def _get_changed_files(self, repo_owner, repo_name, pr_num):
        httpclient = yield self._get_http_client()
        response = yield httpclient.get(
            '/repos/{}/{}/pulls/{}/files'.format(repo_owner, repo_name, pr_num))
        files = set()
        changed_files = yield response.json()
        log.info('Changed files: {c}', c=changed_files)
        for payload in changed_files:
            files.add(payload['filename'])
        defer.returnValue(sorted(files))

# for GitHub, we do another level of indirection because
# we already had documented API that encouraged people to subclass GitHubEventHandler
# so we need to be careful not breaking that API.


class GitHubHandler(BaseHookHandler):
    def __init__(self, master, options):
        if options is None:
            options = {}
        BaseHookHandler.__init__(self, master, options)

        klass = options.get('class', GitHubEventHandler)
        klass_kwargs = {
            'master': master,
            'codebase': options.get('codebase', None),
            'github_property_whitelist': options.get('github_property_whitelist', None),
            'skips': options.get('skips', None),
            'oauth_token': options.get('oauth_token', None),
            'github_api_endpoint': options.get('github_api_endpoint', None) or 'https://api.github.com',
            'debug': options.get('debug', None) or False,
            'verify': options.get('verify', None) or False,
        }
        handler = klass(options.get('secret', None),
                        options.get('strict', False),
                        **klass_kwargs)
        self.handler = handler

    def getChanges(self, request):
        return self.handler.process(request)


github = GitHubHandler
