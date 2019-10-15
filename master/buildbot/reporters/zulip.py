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

from buildbot import config
from buildbot.reporters.http import HttpStatusPushBase
from buildbot.util import httpclientservice
from buildbot.util.logger import Logger

log = Logger()


class ZulipStatusPush(HttpStatusPushBase):
    name = "ZulipStatusPush"
    neededDetails = dict(wantProperties=True)

    def checkConfig(self, endpoint, token, stream=None, **kwargs):
        if not isinstance(endpoint, str):
            config.error("Endpoint must be a string")
        if not isinstance(token, str):
            config.error("Token must be a string")
        super().checkConfig(**kwargs)

    @defer.inlineCallbacks
    def reconfigService(self, endpoint, token, stream=None, **kwargs):
        super().reconfigService(**kwargs)
        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, endpoint,
            debug=self.debug, verify=self.verify)
        self.token = token
        self.stream = stream

    @defer.inlineCallbacks
    def send(self, build):
        event = ("new", "finished")[0 if build["complete_at"] is None else 1]
        jsondata = dict(event=event, buildid=build["buildid"], buildername=build["builder"]["name"], url=build["url"],
                        project=build["properties"]["project"][0])
        if event == "new":
            jsondata["timestamp"] = int(build["started_at"].timestamp())
        elif event == "finished":
            jsondata["timestamp"] = int(build["complete_at"].timestamp())
            jsondata["results"] = build["results"]
        if self.stream is not None:
            url = "/api/v1/external/buildbot?api_key={}&stream={}".format(self.token, self.stream)
        else:
            url = "/api/v1/external/buildbot?api_key={}".format(self.token)
        response = yield self._http.post(url, json=jsondata)
        if response.code != 200:
            content = yield response.content()
            log.error("{code}: Error pushing build status to Zulip: {content}", code=response.code, content=content)
