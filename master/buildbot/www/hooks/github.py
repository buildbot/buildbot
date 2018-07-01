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

import hmac
import json
import logging
import re
from hashlib import sha1

from dateutil.parser import parse as dateparse

from twisted.internet import defer
from twisted.python import log

from buildbot.changes.github import PullRequestMixin
from buildbot.util import bytes2unicode
from buildbot.util import httpclientservice
from buildbot.util import unicode2bytes
from buildbot.www.hooks.base import BaseHookHandler

_HEADER_EVENT = b'X-GitHub-Event'
_HEADER_SIGNATURE = b'X-Hub-Signature'

DEFAULT_SKIPS_PATTERN = (r'\[ *skip *ci *\]', r'\[ *ci *skip *\]')
DEFAULT_GITHUB_API_URL = 'https://api.github.com'


class GitHubEventHandler(PullRequestMixin):

    def __init__(self, secret, strict,
                 codebase=None,
                 github_property_whitelist=None,
                 master=None,
                 skips=None,
                 github_api_endpoint=None,
                 pullrequest_ref=None,
                 token=None,
                 debug=False,
                 verify=False):
        self._secret = secret
        self._strict = strict
        self._token = token
        self._codebase = codebase
        self.pullrequest_ref = pullrequest_ref
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
        self.debug = debug
        self.verify = verify

    @defer.inlineCallbacks
    def process(self, request):
        payload = self._get_payload(request)

        event_type = request.getHeader(_HEADER_EVENT)
        event_type = bytes2unicode(event_type)
        log.msg("X-GitHub-Event: {}".format(
            event_type), logLevel=logging.DEBUG)

        handler = getattr(self, 'handle_{}'.format(event_type), None)

        if handler is None:
            raise ValueError('Unknown event: {}'.format(event_type))

        result = yield defer.maybeDeferred(lambda: handler(payload, event_type))
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

            def _cmp(a, b):
                try:
                    # try the more secure compare_digest() first
                    from hmac import compare_digest
                    return compare_digest(a, b)
                except ImportError:  # pragma: no cover
                    # and fallback to the insecure simple comparison otherwise
                    return a == b

            if not _cmp(bytes2unicode(mac.hexdigest()), hexdigest):
                raise ValueError('Hash mismatch')

        content_type = request.getHeader(b'Content-Type')

        if content_type == b'application/json':
            payload = json.loads(content)
        elif content_type == b'application/x-www-form-urlencoded':
            payload = json.loads(bytes2unicode(request.args[b'payload'][0]))
        else:
            raise ValueError('Unknown content type: {}'.format(content_type))

        log.msg("Payload: {}".format(payload), logLevel=logging.DEBUG)

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

        log.msg("Received {} changes from github".format(len(changes)))

        return changes, 'git'

    @defer.inlineCallbacks
    def handle_pull_request(self, payload, event):
        changes = []
        number = payload['number']
        refname = 'refs/pull/{}/{}'.format(number, self.pullrequest_ref)
        commits = payload['pull_request']['commits']
        title = payload['pull_request']['title']
        comments = payload['pull_request']['body']
        repo_full_name = payload['repository']['full_name']
        head_sha = payload['pull_request']['head']['sha']

        log.msg('Processing GitHub PR #{}'.format(number),
                logLevel=logging.DEBUG)

        head_msg = yield self._get_commit_msg(repo_full_name, head_sha)
        if self._has_skip(head_msg):
            log.msg("GitHub PR #{}, Ignoring: "
                    "head commit message contains skip pattern".format(number))
            defer.returnValue(([], 'git'))

        action = payload.get('action')
        if action not in ('opened', 'reopened', 'synchronize'):
            log.msg("GitHub PR #{} {}, ignoring".format(number, action))
            defer.returnValue((changes, 'git'))

        properties = self.extractProperties(payload['pull_request'])
        properties.update({'event': event})
        change = {
            'revision': payload['pull_request']['head']['sha'],
            'when_timestamp': dateparse(payload['pull_request']['created_at']),
            'branch': refname,
            'revlink': payload['pull_request']['_links']['html']['href'],
            'repository': payload['repository']['html_url'],
            'project': payload['pull_request']['base']['repo']['full_name'],
            'category': 'pull',
            # TODO: Get author name based on login id using txgithub module
            'author': payload['sender']['login'],
            'comments': u'GitHub Pull Request #{0} ({1} commit{2})\n{3}\n{4}'.format(
                number, commits, 's' if commits != 1 else '', title, comments),
            'properties': properties,
        }

        if callable(self._codebase):
            change['codebase'] = self._codebase(payload)
        elif self._codebase is not None:
            change['codebase'] = self._codebase

        changes.append(change)

        log.msg("Received {} changes from GitHub PR #{}".format(
            len(changes), number))
        defer.returnValue((changes, 'git'))

    @defer.inlineCallbacks
    def _get_commit_msg(self, repo, sha):
        '''
        :param repo: the repo full name, ``{owner}/{project}``.
            e.g. ``buildbot/buildbot``
        '''
        headers = {
            'User-Agent': 'Buildbot'
        }
        if self._token:
            headers['Authorization'] = 'token ' + self._token

        url = '/repos/{}/commits/{}'.format(repo, sha)
        http = yield httpclientservice.HTTPClientService.getService(
            self.master, self.github_api_endpoint, headers=headers,
            debug=self.debug, verify=self.verify)
        res = yield http.get(url)
        data = yield res.json()
        msg = data.get('commit', {'message': 'No message field'})['message']
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
            log.msg("Ignoring refname `{}': Not a branch".format(refname))
            return changes
        category = None  # None is the legacy category for when hook only supported push
        if match.group(1) == "tags":
            category = "tag"

        branch = match.group(2)
        if payload.get('deleted'):
            log.msg("Branch `{}' deleted, ignoring".format(branch))
            return changes

        # check skip pattern in commit message. e.g.: [ci skip] and [skip ci]
        head_msg = payload['head_commit'].get('message', '')
        if self._has_skip(head_msg):
            return changes
        commits = payload['commits']
        if payload.get('created'):
            commits = [payload['head_commit']]
        for commit in commits:
            files = []
            for kind in ('added', 'modified', 'removed'):
                files.extend(commit.get(kind, []))

            when_timestamp = dateparse(commit['timestamp'])

            log.msg("New revision: {}".format(commit['id'][:8]))

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
                'category': category
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
            'github_api_endpoint': options.get('github_api_endpoint', None) or 'https://api.github.com',
            'pullrequest_ref': options.get('pullrequest_ref', None) or 'merge',
            'token': options.get('token', None),
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
