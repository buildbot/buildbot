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

from __future__ import absolute_import
from __future__ import print_function

import json

from twisted.python import log

from buildbot.util import bytes2NativeString

GIT_BRANCH_REF = "refs/heads/{}"
GIT_MERGE_REF = "refs/pull-requests/{}/merge"
GIT_TAG_REF = "refs/tags/{}"

_HEADER_EVENT = b'X-Event-Key'


class BitbucketCloudEventHandler(object):

    def __init__(self, master, options=None):
        if options is None:
            options = {}
        self.master = master
        if not isinstance(options, dict):
            options = {}
        self.options = options
        self._codebase = self.options.get('codebase', None)

    def process(self, request):
        payload = self._get_payload(request)
        event_type = request.getHeader(_HEADER_EVENT)
        event_type = bytes2NativeString(event_type)
        log.msg("Processing event {header}: {event}"
                .format(header=_HEADER_EVENT, event=event_type))
        event_type = event_type.replace(":", "_")
        handler = getattr(self, 'handle_{}'.format(event_type), None)

        if handler is None:
            raise ValueError('Unknown event: {}'.format(event_type))

        return handler(payload)

    def _get_payload(self, request):
        content = request.content.read()
        content = bytes2NativeString(content)
        content_type = request.getHeader(b'Content-Type')
        content_type = bytes2NativeString(content_type)
        if content_type.startswith('application/json'):
            payload = json.loads(content)
        else:
            raise ValueError('Unknown content type: {}'
                             .format(content_type))

        log.msg("Payload: {}".format(payload))

        return payload

    def handle_repo_push(self, payload):
        changes = []
        project = payload['repository']['project']['name']
        repo_url = payload['repository']['links']['self']['href']
        web_url = payload['repository']['links']['html']['href']

        for payload_change in payload['push']['changes']:
            if payload_change['new']:
                age = 'new'
                category = 'push'
            else:  # when new is null the ref is deleted
                age = 'old'
                category = 'ref-deleted'

            commit_hash = payload_change[age]['target']['hash']

            if payload_change[age]['type'] == 'branch':
                branch = GIT_BRANCH_REF.format(payload_change[age]['name'])
            elif payload_change[age]['type'] == 'tag':
                branch = GIT_TAG_REF.format(payload_change[age]['name'])

            change = {
                'revision': commit_hash,
                'revlink': '{}/commits/{}'.format(web_url, commit_hash),
                'repository': repo_url,
                'author': '{} <{}>'.format(payload['actor']['display_name'],
                                           payload['actor']['username']),
                'comments': 'Bitbucket Cloud commit {}'.format(commit_hash),
                'branch': branch,
                'project': project,
                'category': category
            }

            if callable(self._codebase):
                change['codebase'] = self._codebase(payload)
            elif self._codebase is not None:
                change['codebase'] = self._codebase

            changes.append(change)

        return (changes, payload['repository']['scm'])

    def handle_pullrequest_created(self, payload):
        return self.handle_pullrequest(
            payload,
            GIT_MERGE_REF.format(int(payload['pullrequest']['id'])),
            "pull-created")

    def handle_pullrequest_updated(self, payload):
        return self.handle_pullrequest(
            payload,
            GIT_MERGE_REF.format(int(payload['pullrequest']['id'])),
            "pull-updated")

    def handle_pullrequest_fulfilled(self, payload):
        return self.handle_pullrequest(
            payload,
            GIT_BRANCH_REF.format(
                payload['pullrequest']['toRef']['branch']['name']),
            "pull-fulfilled")

    def handle_pullrequest_rejected(self, payload):
        return self.handle_pullrequest(
            payload,
            GIT_BRANCH_REF.format(
                payload['pullrequest']['fromRef']['branch']['name']),
            "pull-rejected")

    def handle_pullrequest(self, payload, refname, category):
        pr_number = int(payload['pullrequest']['id'])
        repo_url = payload['repository']['links']['self']['href']
        change = {
            'revision': payload['pullrequest']['fromRef']['commit']['hash'],
            'revlink': payload['pullrequest']['link'],
            'repository': repo_url,
            'author': '{} <{}>'.format(payload['actor']['display_name'],
                                       payload['actor']['username']),
            'comments': 'Bitbucket Cloud Pull Request #{}'.format(pr_number),
            'branch': refname,
            'project': payload['repository']['project']['name'],
            'category': category,
            'properties': {'pullrequesturl': payload['pullrequest']['link']}
        }

        if callable(self._codebase):
            change['codebase'] = self._codebase(payload)
        elif self._codebase is not None:
            change['codebase'] = self._codebase

        return [change], payload['repository']['scm']

    def getChanges(self, request):
        return self.process(request)


bitbucketcloud = BitbucketCloudEventHandler
