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

from twisted.internet import defer

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
    def reconfigService(self, base_url, user, password, **kwargs):
        yield http.HttpStatusPushBase.reconfigService(self, **kwargs)
        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, base_url, auth=(user, password))

    @defer.inlineCallbacks
    def send(self, build):
        results = build['results']
        if build['complete']:
            status = STASH_SUCCESSFUL if results == SUCCESS else STASH_FAILED
        else:
            status = STASH_INPROGRESS
        for sourcestamp in build['buildset']['sourcestamps']:
            sha = sourcestamp['revision']
            body = {'state': status, 'key': build[
                'builder']['name'], 'url': build['url']}
            response = yield self._http.post('/rest/build-status/1.0/commits/' + sha,
                                            json=body)
            if response.code != 204:
                content = yield response.content()
                log.error("%s: unable to upload stash status: %s" %
                          (response.code, content))
