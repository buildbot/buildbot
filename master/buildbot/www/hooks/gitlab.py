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

from dateutil.parser import parse as dateparse

from twisted.internet.defer import inlineCallbacks
from twisted.python import log

from buildbot.process.properties import Properties
from buildbot.util import bytes2unicode
from buildbot.www.hooks.base import BaseHookHandler

_HEADER_EVENT = b'X-Gitlab-Event'
_HEADER_GITLAB_TOKEN = b'X-Gitlab-Token'


class GitLabHandler(BaseHookHandler):

    def _process_change(self, payload, user, repo, repo_url, event,
                        codebase=None):
        """
        Consumes the JSON as a python object and actually starts the build.

        :arguments:
            payload
                Python Object that represents the JSON sent by GitLab Service
                Hook.
        """
        changes = []
        refname = payload['ref']
        # project name from http headers is empty for me, so get it from repository/name
        project = payload['repository']['name']

        # We only care about regular heads or tags
        match = re.match(r"^refs/(heads|tags)/(.+)$", refname)
        if not match:
            log.msg(f"Ignoring refname `{refname}': Not a branch")
            return changes

        branch = match.group(2)
        if payload.get('deleted'):
            log.msg(f"Branch `{branch}' deleted, ignoring")
            return changes

        for commit in payload['commits']:
            if not commit.get('distinct', True):
                log.msg(f"Commit `{commit['id']}` is a non-distinct commit, ignoring...")
                continue

            files = []
            for kind in ('added', 'modified', 'removed'):
                files.extend(commit.get(kind, []))

            when_timestamp = dateparse(commit['timestamp'])

            log.msg(f"New revision: {commit['id'][:8]}")

            change = {
                'author': f"{commit['author']['name']} <{commit['author']['email']}>",
                'files': files,
                'comments': commit['message'],
                'revision': commit['id'],
                'when_timestamp': when_timestamp,
                'branch': branch,
                'revlink': commit['url'],
                'repository': repo_url,
                'project': project,
                'category': event,
                'properties': {
                    'event': event,
                },
            }

            if codebase is not None:
                change['codebase'] = codebase

            changes.append(change)

        return changes

    def _process_merge_request_change(self, payload, event, codebase=None):
        """
        Consumes the merge_request JSON as a python object and turn it into a buildbot change.

        :arguments:
            payload
                Python Object that represents the JSON sent by GitLab Service
                Hook.
        """
        attrs = payload['object_attributes']
        commit = attrs['last_commit']
        when_timestamp = dateparse(commit['timestamp'])
        # @todo provide and document a way to choose between http and ssh url
        repo_url = attrs['target']['git_http_url']
        # project name from http headers is empty for me, so get it from
        # object_attributes/target/name
        project = attrs['target']['name']

        # Filter out uninteresting events
        state = attrs['state']
        if re.match('^(closed|merged|approved)$', state):
            log.msg(f"GitLab MR#{attrs['iid']}: Ignoring because state is {state}")
            return []
        action = attrs['action']
        if not re.match('^(open|reopen)$', action) and \
                not (action == "update" and "oldrev" in attrs):
            log.msg(f"GitLab MR#{attrs['iid']}: Ignoring because action {action} was not open or "
                    "reopen or an update that added code")
            return []

        changes = [{
            'author': f"{commit['author']['name']} <{commit['author']['email']}>",
            'files': [],  # @todo use rest API
            'comments': f"MR#{attrs['iid']}: {attrs['title']}\n\n{attrs['description']}",
            'revision': commit['id'],
            'when_timestamp': when_timestamp,
            'branch': attrs['target_branch'],
            'repository': repo_url,
            'project': project,
            'category': event,
            'revlink': attrs['url'],
            'properties': {
                'source_branch': attrs['source_branch'],
                'source_project_id': attrs['source_project_id'],
                'source_repository': attrs['source']['git_http_url'],
                'source_git_ssh_url': attrs['source']['git_ssh_url'],
                'target_branch': attrs['target_branch'],
                'target_project_id': attrs['target_project_id'],
                'target_repository': attrs['target']['git_http_url'],
                'target_git_ssh_url': attrs['target']['git_ssh_url'],
                'event': event,
            },
        }]
        if codebase is not None:
            changes[0]['codebase'] = codebase
        return changes

    def _process_note_addition_to_merge_request(self, payload, event, codebase=None):
        """
        Consumes a note event JSON as a python object and turn it into a buildbot change.

        :arguments:
            payload
                Python Object that represents the JSON sent by GitLab Service
                Hook.

        Comments in merge_requests are send as note events by the API
        """
        attrs = payload['object_attributes']

        # handle only note events coming from merge_requests
        # this can be direct comments or comments added to a changeset of the MR
        #
        # editing a comment does NOT lead to an event at all
        if 'merge_request' not in payload:
            log.msg(f"Found note event (id {attrs['id']}) without corresponding MR - ignore")
            return []

        # change handling is very similar to the method above, but
        commit = payload['merge_request']['last_commit']
        when_timestamp = dateparse(commit['timestamp'])
        # @todo provide and document a way to choose between http and ssh url
        repo_url = payload['merge_request']['target']['git_http_url']
        # project name from http headers is empty for me, so get it from
        # object_attributes/target/name
        mr = payload['merge_request']
        project = mr['target']['name']

        log.msg(f"Found notes on MR#{mr['iid']}: {attrs['note']}")
        changes = [{
            'author': f"{commit['author']['name']} <{commit['author']['email']}>",
            'files': [],  # not provided by rest API
            'comments': f"MR#{mr['iid']}: {mr['title']}\n\n{mr['description']}",
            'revision': commit['id'],
            'when_timestamp': when_timestamp,
            'branch': mr['target_branch'],
            'repository': repo_url,
            'project': project,
            'category': event,
            'revlink': mr['url'],
            'properties': {
                'source_branch': mr['source_branch'],
                'source_project_id': mr['source_project_id'],
                'source_repository': mr['source']['git_http_url'],
                'source_git_ssh_url': mr['source']['git_ssh_url'],
                'target_branch': mr['target_branch'],
                'target_project_id': mr['target_project_id'],
                'target_repository': mr['target']['git_http_url'],
                'target_git_ssh_url': mr['target']['git_ssh_url'],
                'event': event,
                'comments': attrs['note'],
            },
        }]
        if codebase is not None:
            changes[0]['codebase'] = codebase
        return changes

    @inlineCallbacks
    def getChanges(self, request):
        """
        Reponds only to POST events and starts the build process

        :arguments:
            request
                the http request object
        """
        expected_secret = isinstance(self.options, dict) and self.options.get('secret')
        if expected_secret:
            received_secret = request.getHeader(_HEADER_GITLAB_TOKEN)
            received_secret = bytes2unicode(received_secret)

            p = Properties()
            p.master = self.master
            expected_secret_value = yield p.render(expected_secret)

            if received_secret != expected_secret_value:
                raise ValueError("Invalid secret")
        try:
            content = request.content.read()
            payload = json.loads(bytes2unicode(content))
        except Exception as e:
            raise ValueError("Error loading JSON: " + str(e)) from e
        event_type = request.getHeader(_HEADER_EVENT)
        event_type = bytes2unicode(event_type)
        # newer version of gitlab have a object_kind parameter,
        # which allows not to use the http header
        event_type = payload.get('object_kind', event_type)
        codebase = request.args.get(b'codebase', [None])[0]
        codebase = bytes2unicode(codebase)
        if event_type in ("push", "tag_push", "Push Hook"):
            user = payload['user_name']
            repo = payload['repository']['name']
            repo_url = payload['repository']['url']
            changes = self._process_change(
                payload, user, repo, repo_url, event_type, codebase=codebase)
        elif event_type == 'merge_request':
            changes = self._process_merge_request_change(
                payload, event_type, codebase=codebase)
        elif event_type == 'note':
            changes = self._process_note_addition_to_merge_request(
                payload, event_type, codebase=codebase)
        else:
            changes = []
        if changes:
            log.msg(f"Received {len(changes)} changes from {event_type} gitlab event")
        return (changes, 'git')


gitlab = GitLabHandler
