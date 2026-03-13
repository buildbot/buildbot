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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.reporters.zulip import ZulipStatusPush
from buildbot.test.fake import fakemaster
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.test.util.logging import LoggingMixin
from buildbot.test.util.reporter import ReporterTestMixin

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class TestZulipStatusPush(
    ReporterTestMixin, LoggingMixin, ConfigErrorsMixin, TestReactorMixin, unittest.TestCase
):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.setup_reporter_test()
        self.master = yield fakemaster.make_master(
            testcase=self, wantData=True, wantDb=True, wantMq=True
        )

        @defer.inlineCallbacks
        def cleanup() -> InlineCallbacksType[None]:
            if self.master.running:
                yield self.master.stopService()

        self.addCleanup(cleanup)

    @defer.inlineCallbacks
    def setupZulipStatusPush(
        self, endpoint: str = "http://example.com", token: str = "123", stream: str | None = None
    ) -> InlineCallbacksType[None]:
        self.sp = ZulipStatusPush(endpoint=endpoint, token=token, stream=stream)
        self._http = yield fakehttpclientservice.HTTPClientService.getService(
            self.master, self, endpoint, debug=None, verify=None
        )
        yield self.sp.setServiceParent(self.master)
        yield self.master.startService()

    @defer.inlineCallbacks
    def test_build_started(self) -> InlineCallbacksType[None]:
        yield self.setupZulipStatusPush(stream="xyz")
        build = yield self.insert_build_new()
        self._http.expect(
            'post',
            '/api/v1/external/buildbot?api_key=123&stream=xyz',
            json={
                "event": 'new',
                "buildid": 20,
                "buildername": "Builder0",
                "url": "http://localhost:8080/#/builders/79/builds/0",
                "project": "testProject",
                "timestamp": 10000001,
            },
        )
        yield self.sp._got_event(('builds', 20, 'new'), build)  # type: ignore[arg-type]

    @defer.inlineCallbacks
    def test_build_finished(self) -> InlineCallbacksType[None]:
        yield self.setupZulipStatusPush(stream="xyz")
        build = yield self.insert_build_finished()
        self._http.expect(
            'post',
            '/api/v1/external/buildbot?api_key=123&stream=xyz',
            json={
                "event": "finished",
                "buildid": 20,
                "buildername": "Builder0",
                "url": "http://localhost:8080/#/builders/79/builds/0",
                "project": "testProject",
                "timestamp": 10000005,
                "results": 0,
            },
        )
        yield self.sp._got_event(('builds', 20, 'finished'), build)  # type: ignore[arg-type]

    @defer.inlineCallbacks
    def test_stream_none(self) -> InlineCallbacksType[None]:
        yield self.setupZulipStatusPush(stream=None)
        build = yield self.insert_build_finished()
        self._http.expect(
            'post',
            '/api/v1/external/buildbot?api_key=123',
            json={
                "event": "finished",
                "buildid": 20,
                "buildername": "Builder0",
                "url": "http://localhost:8080/#/builders/79/builds/0",
                "project": "testProject",
                "timestamp": 10000005,
                "results": 0,
            },
        )
        yield self.sp._got_event(('builds', 20, 'finished'), build)  # type: ignore[arg-type]

    def test_endpoint_string(self) -> None:
        with self.assertRaisesConfigError("Endpoint must be a string"):
            ZulipStatusPush(endpoint=1234, token="abcd")

    def test_token_string(self) -> None:
        with self.assertRaisesConfigError("Token must be a string"):
            ZulipStatusPush(endpoint="http://example.com", token=1234)

    @defer.inlineCallbacks
    def test_invalid_json_data(self) -> InlineCallbacksType[None]:
        yield self.setupZulipStatusPush(stream="xyz")
        build = yield self.insert_build_new()
        self._http.expect(
            'post',
            '/api/v1/external/buildbot?api_key=123&stream=xyz',
            json={
                "event": 'new',
                "buildid": 20,
                "buildername": "Builder0",
                "url": "http://localhost:8080/#/builders/79/builds/0",
                "project": "testProject",
                "timestamp": 10000001,
            },
            code=500,
        )
        self.setUpLogging()
        yield self.sp._got_event(('builds', 20, 'new'), build)  # type: ignore[arg-type]
        self.assertLogged('500: Error pushing build status to Zulip')

    @defer.inlineCallbacks
    def test_invalid_url(self) -> InlineCallbacksType[None]:
        yield self.setupZulipStatusPush(stream="xyz")
        build = yield self.insert_build_new()
        self._http.expect(
            'post',
            '/api/v1/external/buildbot?api_key=123&stream=xyz',
            json={
                "event": 'new',
                "buildid": 20,
                "buildername": "Builder0",
                "url": "http://localhost:8080/#/builders/79/builds/0",
                "project": "testProject",
                "timestamp": 10000001,
            },
            code=404,
        )
        self.setUpLogging()
        yield self.sp._got_event(('builds', 20, 'new'), build)  # type: ignore[arg-type]
        self.assertLogged('404: Error pushing build status to Zulip')

    @defer.inlineCallbacks
    def test_invalid_token(self) -> InlineCallbacksType[None]:
        yield self.setupZulipStatusPush(stream="xyz")
        build = yield self.insert_build_new()
        self._http.expect(
            'post',
            '/api/v1/external/buildbot?api_key=123&stream=xyz',
            json={
                "event": 'new',
                "buildid": 20,
                "buildername": "Builder0",
                "url": "http://localhost:8080/#/builders/79/builds/0",
                "project": "testProject",
                "timestamp": 10000001,
            },
            code=401,
            content_json={"result": "error", "msg": "Invalid API key", "code": "INVALID_API_KEY"},
        )
        self.setUpLogging()
        yield self.sp._got_event(('builds', 20, 'new'), build)  # type: ignore[arg-type]
        self.assertLogged('401: Error pushing build status to Zulip')
