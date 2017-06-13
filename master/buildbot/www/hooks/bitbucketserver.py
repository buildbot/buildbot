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

GIT_MERGE_REF = "refs/pull-requests/{}/merge"
GIT_HEAD_REF = "refs/heads/{}"

_HEADER_CT = 'Content-Type'
_HEADER_EVENT = 'X-Event-Key'

class BitbucketServerEventHandler(object):

    def __init__(self, codebase=None, options={}):
        self._codebase = codebase
        self.options = options

    def process(self, request):
        payload = self._get_payload(request)
        event_type = request.getHeader(_HEADER_EVENT)
        log.msg("Processing event {header}: {event}"
                .format(header=_HEADER_EVENT, event=event_type))
        event_type = event_type.replace(":", "_")
        handler = getattr(self, 'handle_{}'.format(event_type), None)

        if handler is None:
            raise ValueError('Unknown event: {}'.format(event_type))

        return handler(payload)

    def _get_payload(self, request):
        content = request.content.read()
        content_type = request.getHeader(_HEADER_CT)
        if content_type.startswith('application/json'):
            payload = json.loads(content)
        elif content_type.startswith('application/x-www-form-urlencoded'):
            payload = json.loads(request.args['payload'][0])
        else:
            raise ValueError('Unknown content type: {}'
                             .format(content_type))

        log.msg("Payload: {}".format(payload))

        return payload

    def handle_repo_push(self, payload):
        changes = []
        project = payload['repository']['project']['name']
        repo_url = payload['repository']['links']['self'][0]['href']
        repo_url = repo_url.rstrip('browse')

        for payload_change in payload['push']['changes']:
            if not payload_change['new']:
                # skip change if deleting a tag or a branch
                continue

            change = {
                'revision': payload_change['new']['target']['hash'],
                'revlink': '{}commits/{}'.format(
                    repo_url, payload_change['new']['target']['hash']),
                'repository': repo_url,
                'author': '{} <{}>'.format(payload['actor']['displayName'],
                                           payload['actor']['username']),
                'comments': 'Bitbucket Server commit {}'.format(
                    payload_change['new']['target']['hash']),
                'branch': GIT_HEAD_REF.format(payload_change['new']['name']),
                'project' : project,
                'category' : 'push'
            }

            if callable(self._codebase):
                change['codebase'] = self._codebase(payload)
            elif self._codebase is not None:
                change['codebase'] = self._codebase

            changes.append(change)

        return (changes, payload['repository']['scmId'])

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
            GIT_HEAD_REF.format(
                payload['pullrequest']['toRef']['branch']['name']),
            "pull-fulfilled")

    def handle_pullrequest_rejected(self, payload):
        return self.handle_pullrequest(
            payload,
            GIT_HEAD_REF.format(
                payload['pullrequest']['fromRef']['branch']['name']),
            "pull-rejected")

    def handle_pullrequest(self, payload, refname, category):
        pr_number = int(payload['pullrequest']['id'])
        repo_url = payload['repository']['links']['self'][0]['href']
        repo_url = repo_url.rstrip('browse')
        change = {
            'revision': None,
            'revlink': payload['pullrequest']['link'],
            'repository': repo_url,
            'author': '{} <{}>'.format(payload['actor']['displayName'],
                                       payload['actor']['username']),
            'comments': 'Bitbucket Server Pull Request #{}'.format(pr_number),
            'branch' : refname,
            'project': payload['repository']['project']['name'],
            'category': category,
            'properties' : {'pullrequesturl' : payload['pullrequest']['link']}
        }

        if callable(self._codebase):
            change['codebase'] = self._codebase(payload)
        elif self._codebase is not None:
            change['codebase'] = self._codebase

        return [change], payload['repository']['scmId']


def getChanges(request, options=None):
    if not isinstance(options, dict):
        options = {}

    handler = BitbucketServerEventHandler(options.get('codebase', None),
            options)
    return handler.process(request)
