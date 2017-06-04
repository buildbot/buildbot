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

import json
import re

from dateutil.parser import parse as dateparse

from twisted.python import log

from buildbot.util import bytes2NativeString

_HEADER_EVENT = b'X-Gitlab-Event'
_HEADER_GITLAB_TOKEN = b'X-Gitlab-Token'


def _process_change(payload, user, repo, repo_url, project, event,
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

    # We only care about regular heads or tags
    match = re.match(r"^refs/(heads|tags)/(.+)$", refname)
    if not match:
        log.msg("Ignoring refname `%s': Not a branch" % refname)
        return changes

    branch = match.group(2)
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


def _process_merge_request_change(payload, project, event, codebase=None):
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
    changes = [{
        'author': '%s <%s>' % (commit['author']['name'],
                               commit['author']['email']),
        'files': [],  # @todo use rest API
        'comments': "MR#{}: {}\n\n{}".format(attrs['iid'], attrs['title'], attrs['description']),
        'revision': commit['id'],
        'when_timestamp': when_timestamp,
        'branch': "refs/merge-requests/{}/head".format(attrs['iid']),
        'repository': repo_url.replace(":30302", ''),
        'project': project,
        'category': event,
        'revlink': attrs['url'],
        'properties': {
            'target_branch': attrs['target_branch'],
            'event': event,
        },
    }]
    if codebase is not None:
        changes[0]['codebase'] = codebase
    return changes


def getChanges(request, options=None):
    """
    Reponds only to POST events and starts the build process

    :arguments:
        request
            the http request object
    """
    expected_secret = isinstance(options, dict) and options.get('secret')
    if expected_secret:
        received_secret = request.getHeader(_HEADER_GITLAB_TOKEN)
        if received_secret != expected_secret:
            raise ValueError("Invalid secret")
    try:
        payload = json.load(request.content)
    except Exception as e:
        raise ValueError("Error loading JSON: " + str(e))
    event_type = request.getHeader(_HEADER_EVENT)
    event_type = bytes2NativeString(event_type)
    # newer version of gitlab have a object_kind parameter,
    # which allows not to use the http header
    event_type = payload.get('object_kind', event_type)
    project = request.args.get('project', [''])[0]
    codebase = request.args.get('codebase', [None])[0]
    if event_type in ("push", "tag_push", "Push Hook"):
        user = payload['user_name']
        repo = payload['repository']['name']
        repo_url = payload['repository']['url']
        changes = _process_change(
            payload, user, repo, repo_url, project, event_type, codebase=codebase)
    elif event_type == 'merge_request':
        changes = _process_merge_request_change(
            payload, project, event_type, codebase=codebase)
    else:
        changes = []
    if changes:
        log.msg("Received {} changes from {} gitlab event".format(
            len(changes), event_type))
    return (changes, 'git')
