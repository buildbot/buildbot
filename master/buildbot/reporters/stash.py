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

from twisted.internet import defer

from buildbot.process.properties import Interpolate
from buildbot.process.properties import Properties
from buildbot.process.results import SUCCESS
from buildbot.reporters import http
from buildbot.util import httpclientservice
from buildbot.util.logger import Logger

log = Logger()

# Magic words understood by Stash REST API
STASH_INPROGRESS = 'INPROGRESS'
STASH_SUCCESSFUL = 'SUCCESSFUL'
STASH_FAILED = 'FAILED'


class StashStatusPush(http.HttpStatusPushBase):
    name = "StashStatusPush"

    @defer.inlineCallbacks
    def reconfigService(self, base_url, user, password, key=None, statusName=None,
                        startDescription=None, endDescription=None,
                        verbose=False, **kwargs):
        yield http.HttpStatusPushBase.reconfigService(self, wantProperties=True,
                                                      **kwargs)
        self.key = key or Interpolate('%(prop:buildername)s')
        self.statusName = statusName
        self.endDescription = endDescription or 'Build done.'
        self.startDescription = startDescription or 'Build started.'
        self.verbose = verbose
        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, base_url, auth=(user, password),
            debug=self.debug, verify=self.verify)

    @defer.inlineCallbacks
    def send(self, build):
        props = Properties.fromDict(build['properties'])
        results = build['results']
        if build['complete']:
            status = STASH_SUCCESSFUL if results == SUCCESS else STASH_FAILED
            description = self.endDescription
        else:
            status = STASH_INPROGRESS
            description = self.startDescription
        for sourcestamp in build['buildset']['sourcestamps']:
            sha = sourcestamp['revision']
            key = yield props.render(self.key)
            payload = {
                'state': status,
                'url': build['url'],
                'key': key,
            }
            if description:
                payload['description'] = yield props.render(description)
            if self.statusName:
                payload['name'] = yield props.render(self.statusName)
            response = yield self._http.post('/rest/build-status/1.0/commits/' + sha,
                                             json=payload)
            if response.code == 204:
                if self.verbose:
                    log.info('Status "{status}" sent for {sha}.',
                             status=status, sha=sha)
            else:
                content = yield response.content()
                log.error("{code}: Unable to send Stash status: {content}",
                          code=response.code, content=content)
