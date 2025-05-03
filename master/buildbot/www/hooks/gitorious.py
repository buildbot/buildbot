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


from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING
from typing import Any

from dateutil.parser import parse as dateparse
from twisted.internet import defer
from twisted.python import log

from buildbot.util import bytes2unicode
from buildbot.www.hooks.base import BaseHookHandler

if TYPE_CHECKING:
    from twisted.web.server import Request


class GitoriousHandler(BaseHookHandler):
    def getChanges(
        self, request: Request
    ) -> defer.Deferred[tuple[list[dict[str, Any]], str | None]]:
        args: dict[bytes, list[bytes]] = request.args or {}
        payload_bytes = args.get(b'payload', [b'{}'])[0]
        payload = json.loads(bytes2unicode(payload_bytes))
        user = payload['repository']['owner']['name']
        repo = payload['repository']['name']
        repo_url = payload['repository']['url']
        project = payload['project']['name']

        changes = self.process_change(payload, user, repo, repo_url, project)
        log.msg(f"Received {len(changes)} changes from gitorious")
        return defer.succeed((changes, 'git'))

    def process_change(
        self, payload: dict[str, Any], user: str, repo: str, repo_url: str, project: str
    ) -> list[dict[str, Any]]:
        changes = []
        newrev = payload['after']

        branch = payload['ref']
        if re.match(r"^0*$", newrev):
            log.msg(f"Branch `{branch}' deleted, ignoring")
            return []
        else:
            for commit in payload['commits']:
                files: list[str] = []
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
                    'project': project,
                })

        return changes


gitorious = GitoriousHandler
