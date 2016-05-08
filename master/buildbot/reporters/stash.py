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
from twisted.python import log

from buildbot.process.results import SUCCESS
from buildbot.reporters import http

# Magic words understood by Stash REST API
STASH_INPROGRESS = 'INPROGRESS'
STASH_SUCCESSFUL = 'SUCCESSFUL'
STASH_FAILED = 'FAILED'


class StashStatusPush(http.HttpStatusPushBase):
    name = "StashStatusPush"

    @defer.inlineCallbacks
    def reconfigService(self, base_url, user, password, **kwargs):
        yield http.HttpStatusPushBase.reconfigService(self, **kwargs)
        if not base_url.endswith('/'):
            base_url += '/'
        self.base_url = '%srest/build-status/1.0/commits/' % (base_url,)
        self.auth = (user, password)

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
            stash_uri = self.base_url + sha
            response = yield self.session.post(stash_uri, body, auth=self.auth)
            if response.status_code != 200:
                log.msg("%s: unable to upload stash status: %s" %
                        (response.status, response.content))
