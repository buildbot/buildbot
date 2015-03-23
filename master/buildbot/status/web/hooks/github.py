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

import hmac
import logging
import re
import requests

from hashlib import sha1

from dateutil.parser import parse as dateparse
from twisted.python import log

try:
    import json
    assert json
except ImportError:
    import simplejson as json

_HEADER_CT = 'Content-Type'
_HEADER_EVENT = 'X-GitHub-Event'
_HEADER_SIGNATURE = 'X-Hub-Signature'


class GitHubEventHandler(object):
    def __init__(self, secret, strict, codebase=None):
        self._secret = secret
        self._strict = strict
        self._codebase = codebase

        if self._strict and not self._secret:
            raise ValueError('Strict mode is requested '
                             'while no secret is provided')

    def process(self, request):
        payload = self._get_payload(request)

        event_type = request.getHeader(_HEADER_EVENT)
        log.msg("X-GitHub-Event: %r" % (event_type,), logLevel=logging.DEBUG)

        handler = getattr(self, 'handle_%s' % event_type, None)

        if handler is None:
            raise ValueError('Unknown event: %r' % (event_type,))

        return handler(payload)

    def _get_payload(self, request):
        content = request.content.read()

        signature = request.getHeader(_HEADER_SIGNATURE)

        if not signature and self._strict:
            raise ValueError('Request has no required signature')

        if self._secret and signature:
            try:
                hash_type, hexdigest = signature.split('=')
            except ValueError:
                raise ValueError('Wrong signature format: %r' % (signature,))

            if hash_type != 'sha1':
                raise ValueError('Unknown hash type: %s' % (hash_type,))

            mac = hmac.new(self._secret, msg=content, digestmod=sha1)
            # NOTE: hmac.compare_digest should be used, but it's only available
            # starting Python 2.7.7
            if mac.hexdigest() != hexdigest:
                raise ValueError('Hash mismatch')

        content_type = request.getHeader(_HEADER_CT)

        if content_type == 'application/json':
            payload = json.loads(content)
        elif content_type == 'application/x-www-form-urlencoded':
            payload = json.loads(request.args['payload'][0])
        else:
            raise ValueError('Unknown content type: %r' % (content_type,))

        log.msg("Payload: %r" % payload, logLevel=logging.DEBUG)

        return payload

    def handle_ping(self, _):
        return [], 'git'

    def handle_push(self, payload):
        # This field is unused:
        user = None
        # user = payload['pusher']['name']
        repo = payload['repository']['name']
        repo_url = payload['repository']['clone_url']
        # NOTE: what would be a reasonable value for project?
        # project = request.args.get('project', [''])[0]
        project = payload['repository']['name']

        changes = self._process_change(payload, user, repo, repo_url, project)

        log.msg("Received %d changes from github" % len(changes))

        return changes, 'git'

    def handle_pull_request(self, payload):
        # This field is unused:
        user = None
        # user = payload['pusher']['name']
        repo = payload['repository']['name']
        repo_url = payload['repository']['clone_url']
        # NOTE: what would be a reasonable value for project?
        # project = request.args.get('project', [''])[0]
        project = payload['repository']['name']

        changes = self._process_pull_request(payload, user, repo, repo_url, project,
                                       self._codebase)
        log.msg("Received %d PR changes from github" % len(changes))
        return changes, 'git'

    def _process_change(self, payload, user, repo, repo_url, project):
        """
        Consumes the JSON as a python object and actually starts the build.

        :arguments:
            payload
                Python Object that represents the JSON sent by GitHub Service
                Hook.
        """
        changes = []
        refname = payload['ref']

        # We only care about regular heads, i.e. branches
        match = re.match(r"^refs\/heads\/(.+)$", refname)
        if not match:
            log.msg("Ignoring refname `%s': Not a branch" % refname)
            return changes

        branch = match.group(1)
        if payload.get('deleted'):
            log.msg("Branch `%s' deleted, ignoring" % branch)
            return changes

        for commit in payload['commits']:
            if not commit.get('distinct', True):
                log.msg('Commit `%s` is a non-distinct commit, ignoring...' %
                        (commit['id'],))
                continue

            files = []
            for kind in ('added', 'modified', 'removed'):
                files.extend(commit.get(kind, []))

            when_timestamp = dateparse(commit['timestamp'])

            log.msg("New revision: %s" % commit['id'][:8])

            change = {
                'author': '%s <%s>' % (commit['author']['name'],
                                       commit['author']['email']),
                'files': files,
                'comments': commit['message'],
                'revision': commit['id'],
                'when_timestamp': when_timestamp,
                'branch': branch,
                'revlink': commit['url'],
                'repository': repo_url,
                'project': project
            }

            if self._codebase is not None:
                change['codebase'] = self._codebase

            changes.append(change)

        return changes

    def _process_pull_request(self, payload, user, repo, repo_url, project, codebase=None):
        changes = []
        number = payload['number']

        # We only care about opened/reopened/synchronize pull requests
        if payload['action'] not in ['opened', 'reopened', 'synchronize']:
            log.msg("Ignoring `%s': Not an opened pull request" % number)
            return changes

        # refname = payload['pull_request']['head']['ref']
        branch = 'refs/pull/%s/head' % number
        category = 'pull-request'

        if payload['pull_request']['mergeable'] == False:
            log.msg("Pull request `%s' not mergeable, ignoring" % branch)
            return changes

        r = requests.get(payload['pull_request']['commits_url'] + "?per_page=100")
        commits = json.loads(r.text)

        for commit in commits:
            if 'distinct' in commit and not commit['distinct']:
                log.msg('Commit `%s` is a non-distinct commit, ignoring...' %
                        (commit['sha'],))
                continue

            files = []
            commit_url = ''
            if 'url' in commit:
                commit_url = commit['url']
                r = requests.get(commit_url)
                commit_files = json.loads(r.text)

                if commit_files and 'files' in commit_files:
                    for f in commit_files['files']:
                        if f['status'] == 'added':
                            files.append(f['filename'])
                        if f['status'] == 'modified':
                            files.append(f['filename'])
                        if f['status'] == 'removed':
                            files.append(f['filename'])

            when_timestamp = dateparse(commit['commit']['author']['date'])

            log.msg("New PR revision: %s" % commit['sha'][:8])

            change = {
                'author': '%s <%s>' % (commit['commit']['author']['name'],
                                       commit['commit']['author']['email']),
                'files': files,
                'comments': commit['commit']['message'],
                'revision': commit['sha'],
                'when_timestamp': when_timestamp,
                'branch': branch,
                'category': category,
                'revlink': commit_url,
                'repository': repo_url,
                'project': project
            }

            if codebase is not None:
                change['codebase'] = codebase

            changes.append(change)

        return changes


def getChanges(request, options=None):
    """
    Responds only to POST events and starts the build process

    :arguments:
        request
            the http request object
    """
    if options is None:
        options = {}

    klass = options.get('class', GitHubEventHandler)

    handler = klass(options.get('secret', None),
                    options.get('strict', False),
                    options.get('codebase', None))
    return handler.process(request)
