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

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from twisted.internet import defer
from twisted.python import log

from buildbot.reporters.base import ReporterBase
from buildbot.reporters.generators.build import BuildStatusGenerator
from buildbot.reporters.message import MessageFormatterFunction
from buildbot.util import httpclientservice

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class HttpStatusPush(ReporterBase):
    name: str | None = "HttpStatusPush"
    secrets = ["auth"]

    def checkConfig(  # type: ignore[override]
        self,
        serverUrl: str,
        auth: Any = None,
        headers: Any = None,
        debug: bool | None = None,
        verify: bool | None = None,
        cert: Any = None,
        skip_encoding: bool = False,
        generators: list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        if generators is None:
            generators = self._create_default_generators()

        super().checkConfig(generators=generators, **kwargs)

    @defer.inlineCallbacks
    def reconfigService(  # type: ignore[override]
        self,
        serverUrl: str,
        auth: Any = None,
        headers: Any = None,
        debug: bool | None = None,
        verify: bool | None = None,
        cert: Any = None,
        skip_encoding: bool = False,
        generators: list[Any] | None = None,
        **kwargs: Any,
    ) -> InlineCallbacksType[None]:
        self.debug = debug
        self.verify = verify
        self.cert = cert

        if generators is None:
            generators = self._create_default_generators()

        yield super().reconfigService(generators=generators, **kwargs)

        self._http = yield httpclientservice.HTTPSession(
            self.master.httpservice,
            serverUrl,
            auth=auth,
            headers=headers,
            debug=self.debug,
            verify=self.verify,
            cert=self.cert,
            skip_encoding=skip_encoding,
        )

    def _create_default_generators(self) -> list[Any]:
        formatter = MessageFormatterFunction(lambda context: context['build'], 'json')
        return [BuildStatusGenerator(message_formatter=formatter, report_new=True)]  # type: ignore[arg-type]

    def is_status_2xx(self, code: int) -> bool:
        return code // 100 == 2

    @defer.inlineCallbacks
    def sendMessage(self, reports: list[Any]) -> InlineCallbacksType[None]:
        response = yield self._http.post("", json=reports[0]['body'])
        if not self.is_status_2xx(response.code):
            log.msg(f"{response.code}: unable to upload status: {response.content}")
