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
# Copyright Buildbot Team Member

from __future__ import annotations

from twisted.internet import defer
from twisted.logger import Logger

from buildbot import config
from buildbot.reporters.base import ReporterBase
from buildbot.reporters.generators.build import BuildStartEndStatusGenerator
from buildbot.reporters.generators.buildrequest import BuildRequestGenerator
from buildbot.reporters.message import MessageFormatterRenderable
from buildbot.util import httpclientservice

log = Logger()


class ZulipStatusPush(ReporterBase):
    # name: str | None = "ZulipStatusPush"  # type: ignore[assignment]

    def checkConfig(self, endpoint, token, stream=None, debug=None, verify=None, generators=None):
        if not isinstance(endpoint, str):
            config.error("Endpoint must be a string")
        if not isinstance(token, str):
            config.error("Token must be a string")
        if generators is None:
            generators = self._create_default_generators()

        super().checkConfig(generators=generators)

    @defer.inlineCallbacks
    def reconfigService(
        self, endpoint, token, stream=None, debug=None, verify=None, generators=None
    ):
        self.debug = debug
        self.verify = verify
        if generators is None:
            generators = self._create_default_generators()
        yield super().reconfigService(generators=generators)
        self._http = yield httpclientservice.HTTPSession(
            self.master.httpservice, endpoint, debug=self.debug, verify=self.verify
        )
        self.token = token
        self.stream = stream

    def _create_default_generators(self):
        start_formatter = MessageFormatterRenderable('Build started.')
        end_formatter = MessageFormatterRenderable('Build done.')
        pending_formatter = MessageFormatterRenderable('Build pending.')

        return [
            BuildRequestGenerator(formatter=pending_formatter),
            BuildStartEndStatusGenerator(
                start_formatter=start_formatter, end_formatter=end_formatter
            ),
        ]

    @defer.inlineCallbacks
    def sendMessage(self, reports):
        build = reports[0]['builds'][0]
        event = ("new", "finished")[0 if build["complete"] is False else 1]
        jsondata = {
            "event": event,
            "buildid": build["buildid"],
            "buildername": build["builder"]["name"],
            "url": build["url"],
            "project": build["properties"]["project"][0],
        }
        if event == "new":
            jsondata["timestamp"] = int(build["started_at"].timestamp())
        elif event == "finished":
            jsondata["timestamp"] = int(build["complete_at"].timestamp())
            jsondata["results"] = build["results"]
        if self.stream is not None:
            url = f"/api/v1/external/buildbot?api_key={self.token}&stream={self.stream}"
        else:
            url = f"/api/v1/external/buildbot?api_key={self.token}"
        response = yield self._http.post(url, json=jsondata)
        if response.code != 200:
            content = yield response.content()
            log.error(
                "{code}: Error pushing build status to Zulip: {content}",
                code=response.code,
                content=content,
            )
