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
#
# note: this file is based on github.py


import json
import re

from dateutil.parser import parse as dateparse

from twisted.python import log

from buildbot.util import bytes2unicode
from buildbot.www.hooks.base import BaseHookHandler


class GitoriousHandler(BaseHookHandler):

    def getChanges(self, request):
        payload = json.loads(bytes2unicode(request.args[b'payload'][0]))
        user = payload['repository']['owner']['name']
        repo = payload['repository']['name']
        repo_url = payload['repository']['url']
        project = payload['project']['name']

        changes = self.process_change(payload, user, repo, repo_url, project)
        log.msg(f"Received {len(changes)} changes from gitorious")
        return (changes, 'git')

    def process_change(self, payload, user, repo, repo_url, project):
        changes = []
        newrev = payload['after']

        branch = payload['ref']
        if re.match(r"^0*$", newrev):
            log.msg(f"Branch `{branch}' deleted, ignoring")
            return []
        else:
            for commit in payload['commits']:
                files = []
                # Gitorious doesn't send these, maybe later
                # if 'added' in commit:
                #     files.extend(commit['added'])
                # if 'modified' in commit:
                #     files.extend(commit['modified'])
                # if 'removed' in commit:
                #     files.extend(commit['removed'])
                when_timestamp = dateparse(commit['timestamp'])

                log.msg(f"New revision: {commit['id'][:8]}")
                changes.append({
                    'author': f"{commit['author']['name']} <{commit['author']['email']}>",
                    'files': files,
                    'comments': commit['message'],
                    'revision': commit['id'],
                    'when_timestamp': when_timestamp,
                    'branch': branch,
                    'revlink': commit['url'],
                    'repository': repo_url,
                    'project': project
                })

        return changes


gitorious = GitoriousHandler
