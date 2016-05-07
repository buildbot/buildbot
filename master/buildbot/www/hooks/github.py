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
        repo_url = payload['repository']['html_url']
        # NOTE: what would be a reasonable value for project?
        # project = request.args.get('project', [''])[0]
        project = payload['repository']['full_name']

        changes = self._process_change(payload, user, repo, repo_url, project)

        log.msg("Received %d changes from github" % len(changes))

        return changes, 'git'

    def handle_pull_request(self, payload):
        changes = []
        number = payload['number']
        refname = 'refs/pull/%d/head' % (number,)
        commits = payload['pull_request']['commits']

        log.msg('Processing GitHub PR #%d' % number, logLevel=logging.DEBUG)

        action = payload.get('action')
        if action not in ('opened', 'reopened', 'synchronize'):
            log.msg("GitHub PR #%d %s, ignoring" % (number, action))
            return changes, 'git'

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
            'comments': 'GitHub Pull Request #%d (%d commit%s)' % (
                number, commits, 's' if commits != 1 else ''),
        }

        if callable(self._codebase):
            change['codebase'] = self._codebase(payload)
        elif self._codebase is not None:
            change['codebase'] = self._codebase

        changes.append(change)

        log.msg("Received %d changes from GitHub PR #%d" % (
            len(changes), number))
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
        match = re.match(r"^refs/heads/(.+)$", refname)
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

            if callable(self._codebase):
                change['codebase'] = self._codebase(payload)
            elif self._codebase is not None:
                change['codebase'] = self._codebase

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
