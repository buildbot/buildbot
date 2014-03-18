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

import re

from dateutil.parser import parse as dateparse
from twisted.python import log

try:
    import json
    assert json
except ImportError:
    import simplejson as json


def getChanges(request, options=None):
    """
    Responds only to POST events and starts the build process

    :arguments:
        request
            the http request object
    """
    payload = json.loads(request.args['payload'][0])
    user = payload['repository']['owner']['name']
    repo = payload['repository']['name']
    repo_url = payload['repository']['url']
    raw_project = request.args.get('project', None)
    project = raw_project[0] if raw_project is not None else ''
    # This field is unused:
    #private = payload['repository']['private']
    changes = process_change(payload, user, repo, repo_url, project)
    log.msg("Received %s changes from github" % len(changes))
    return (changes, 'git')


def process_change(payload, user, repo, repo_url, project, codebase=None):
    """
    Consumes the JSON as a python object and actually starts the build.

    :arguments:
        payload
            Python Object that represents the JSON sent by GitHub Service
            Hook.
    """
    changes = []
    newrev = payload['after']
    refname = payload['ref']

    # We only care about regular heads, i.e. branches
    match = re.match(r"^refs\/heads\/(.+)$", refname)
    if not match:
        log.msg("Ignoring refname `%s': Not a branch" % refname)
    else:
        branch = match.group(1)
        if re.match(r"^0*$", newrev):
            log.msg("Branch `%s' deleted, ignoring" % branch)
        else:
            for commit in payload['commits']:
                if 'distinct' in commit and not commit['distinct']:
                    log.msg(
                        'Commit `%s` is a non-distinct commit, ignoring...' % (
                            commit['id'])
                    )
                    continue

                files = []
                if 'added' in commit:
                    files.extend(commit['added'])
                if 'modified' in commit:
                    files.extend(commit['modified'])
                if 'removed' in commit:
                    files.extend(commit['removed'])
                when_timestamp = dateparse(commit['timestamp'])

                log.msg("New revision: %s" % commit['id'][:8])

                change = {
                    'author': '%s <%s>' % (
                        commit['author']['name'], commit['author']['email']
                    ),
                    'files': files,
                    'comments': commit['message'],
                    'revision': commit['id'],
                    'when_timestamp': when_timestamp,
                    'branch': branch,
                    'revlink': commit['url'],
                    'repository': repo_url,
                    'project': project
                }

                if codebase is not None:
                    change['codebase'] = codebase

                changes.append(change)

    return changes
