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
# Copyright 2013 (c) Mamba Team


import json

from dateutil.parser import parse as dateparse

from twisted.python import log

from buildbot.util import bytes2unicode
from buildbot.www.hooks.base import BaseHookHandler

_HEADER_EVENT = b'X-Event-Key'


class BitBucketHandler(BaseHookHandler):

    def requestParse(self, jsoned_req, repo, repo_url, event_type):
        changes = []
        for commit in jsoned_req['commits']:
            changes.append({
                'author': commit['author']['raw'],
                'comments': commit['summary']['raw'],
                'revision': commit['hash'],
                'when_timestamp': dateparse(commit['date']),
                'branch': jsoned_req['new']['name'],
                'revlink': commit['links']['html']['href'],
                'project': repo,
                'repository': repo_url,
                'properties': {
                    'event': event_type,
                }
            })
            log.msg('New revision: {}'.format(commit['links']['html']['href']))
        
        return changes

    def getChanges(self, request):
        """Catch a POST request from BitBucket and start a build process

        Check the URL below if you require more information about bitbucket's webhooks
        https://confluence.atlassian.com/bitbucket/manage-webhooks-735643732.html

        :param request: the http request Twisted object
        """

        event_type = request.getHeader(_HEADER_EVENT)
        event_type = bytes2unicode(event_type)
        payload = json.loads(bytes2unicode(request.content.read()))

        repo = payload['repository']['name']
        repo_url = payload['repository']['links']['html']['href']
        changes = self.requestParse(payload['push']['changes'][0], repo, repo_url, event_type)

        log.msg('Received {} changes from bitbucket'.format(len(changes)))
        return (changes, payload['repository']['scm'])


bitbucket = BitBucketHandler
