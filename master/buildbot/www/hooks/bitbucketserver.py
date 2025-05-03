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
# Copyright Mamba Team


from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Any

from twisted.python import log

from buildbot.util import bytes2unicode
from buildbot.util.pullrequest import PullRequestMixin

if TYPE_CHECKING:
    from twisted.web.server import Request

    from buildbot.master import BuildMaster

GIT_BRANCH_REF = "refs/heads/{}"
GIT_MERGE_REF = "refs/pull-requests/{}/merge"
GIT_TAG_REF = "refs/tags/{}"

_HEADER_EVENT = b'X-Event-Key'


class BitbucketServerEventHandler(PullRequestMixin):
    property_basename = "bitbucket"

    def __init__(self, master: BuildMaster, options: dict[str, Any] | None = None):
        if options is None:
            options = {}
        self.master = master
        if not isinstance(options, dict):
            options = {}
        self.options = options
        self._codebase = self.options.get('codebase', None)
        self.external_property_whitelist = self.options.get('bitbucket_property_whitelist', [])

    def process(self, request: Request) -> tuple[list[dict[str, Any]], str]:
        payload = self._get_payload(request)
        header = request.getHeader(_HEADER_EVENT)
        if header is None:
            raise ValueError(f'Header {_HEADER_EVENT.decode()} is not present')

        event_type = bytes2unicode(header)
        log.msg(f"Processing event {_HEADER_EVENT.decode()}: {event_type}")
        event_type = event_type.replace(":", "_")
        handler = getattr(self, f'handle_{event_type}', None)

        if handler is None:
            raise ValueError(f'Unknown event: {event_type}')

        return handler(payload)

    def _get_payload(self, request: Request) -> dict[str, Any]:
        assert request.content is not None

        content = bytes2unicode(request.content.read())
        content_type = bytes2unicode(request.getHeader(b'Content-Type'))

        if content_type.startswith('application/json'):
            payload = json.loads(content)
        else:
            raise ValueError(f'Unknown content type: {content_type!r}')

        log.msg(f"Payload: {payload}")

        return payload

    def handle_repo_refs_changed(self, payload: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
        return self._handle_repo_refs_changed_common(payload)

    def handle_repo_push(self, payload: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
        # repo:push works exactly like repo:refs_changed, but is no longer documented (not even
        # in the historical documentation of old versions of Bitbucket Server). The old code path
        # has been preserved for backwards compatibility.
        return self._handle_repo_refs_changed_common(payload)

    def _handle_repo_refs_changed_common(
        self, payload: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], str]:
        changes = []
        project = payload['repository']['project']['name']
        repo_url = payload['repository']['links']['self'][0]['href']
        repo_url = repo_url.rstrip('browse')

        for payload_change in payload['push']['changes']:
            if payload_change['new']:
                age = 'new'
                category = 'push'
            else:  # when new is null the ref is deleted
                age = 'old'
                category = 'ref-deleted'

            commit_hash = payload_change[age]['target']['hash']

            branch = None
            if payload_change[age]['type'] == 'branch':
                branch = GIT_BRANCH_REF.format(payload_change[age]['name'])
            elif payload_change[age]['type'] == 'tag':
                branch = GIT_TAG_REF.format(payload_change[age]['name'])

            change = {
                'revision': commit_hash,
                'revlink': f'{repo_url}commits/{commit_hash}',
                'repository': repo_url,
                'author': f"{payload['actor']['displayName']} <{payload['actor']['username']}>",
                'comments': f'Bitbucket Server commit {commit_hash}',
                'branch': branch,
                'project': project,
                'category': category,
            }

            if callable(self._codebase):
                change['codebase'] = self._codebase(payload)
            elif self._codebase is not None:
                change['codebase'] = self._codebase

            changes.append(change)

        return (changes, payload['repository']['scmId'])

    def handle_pullrequest_created(
        self, payload: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], str]:
        return self.handle_pullrequest(
            payload, GIT_MERGE_REF.format(int(payload['pullrequest']['id'])), "pull-created"
        )

    def handle_pullrequest_updated(
        self, payload: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], str]:
        return self.handle_pullrequest(
            payload, GIT_MERGE_REF.format(int(payload['pullrequest']['id'])), "pull-updated"
        )

    def handle_pullrequest_fulfilled(
        self, payload: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], str]:
        return self.handle_pullrequest(
            payload,
            GIT_BRANCH_REF.format(payload['pullrequest']['toRef']['branch']['name']),
            "pull-fulfilled",
        )

    def handle_pullrequest_rejected(
        self, payload: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], str]:
        return self.handle_pullrequest(
            payload,
            GIT_BRANCH_REF.format(payload['pullrequest']['fromRef']['branch']['name']),
            "pull-rejected",
        )

    def handle_pullrequest(
        self, payload: dict[str, Any], refname: str, category: str
    ) -> tuple[list[dict[str, Any]], str]:
        pr_number = int(payload['pullrequest']['id'])
        repo_url = payload['repository']['links']['self'][0]['href']
        repo_url = repo_url.rstrip('browse')
        revlink = payload['pullrequest']['link']
        change = {
            'revision': payload['pullrequest']['fromRef']['commit']['hash'],
            'revlink': revlink,
            'repository': repo_url,
            'author': f"{payload['actor']['displayName']} <{payload['actor']['username']}>",
            'comments': f'Bitbucket Server Pull Request #{pr_number}',
            'branch': refname,
            'project': payload['repository']['project']['name'],
            'category': category,
            'properties': {
                'pullrequesturl': revlink,
                **self.extractProperties(payload['pullrequest']),
            },
        }

        if callable(self._codebase):
            change['codebase'] = self._codebase(payload)
        elif self._codebase is not None:
            change['codebase'] = self._codebase

        return [change], payload['repository']['scmId']

    def getChanges(self, request: Request) -> tuple[list[dict[str, Any]], str]:
        return self.process(request)


bitbucketserver = BitbucketServerEventHandler
