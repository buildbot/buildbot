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

from twisted.trial import unittest

from buildbot.reporters.zulip import ZulipStatusPush
from buildbot.test.fake import fakemaster
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.test.util.logging import LoggingMixin
from buildbot.test.util.reporter import ReporterTestMixin


class TestZulipStatusPush(
    unittest.TestCase, ReporterTestMixin, LoggingMixin, ConfigErrorsMixin, TestReactorMixin
):
    def setUp(self):
        self.setup_test_reactor()
        self.setup_reporter_test()
        self.master = fakemaster.make_master(testcase=self, wantData=True, wantDb=True, wantMq=True)

    async def tearDown(self):
        if self.master.running:
            await self.master.stopService()

    async def setupZulipStatusPush(self, endpoint="http://example.com", token="123", stream=None):
        self.sp = ZulipStatusPush(endpoint=endpoint, token=token, stream=stream)
        self._http = await fakehttpclientservice.HTTPClientService.getService(
            self.master, self, endpoint, debug=None, verify=None
        )
        await self.sp.setServiceParent(self.master)
        await self.master.startService()

    async def test_build_started(self):
        await self.setupZulipStatusPush(stream="xyz")
        build = await self.insert_build_new()
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
        await self.sp._got_event(('builds', 20, 'new'), build)

    async def test_build_finished(self):
        await self.setupZulipStatusPush(stream="xyz")
        build = await self.insert_build_finished()
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
        await self.sp._got_event(('builds', 20, 'finished'), build)

    async def test_stream_none(self):
        await self.setupZulipStatusPush(stream=None)
        build = await self.insert_build_finished()
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
        await self.sp._got_event(('builds', 20, 'finished'), build)

    def test_endpoint_string(self):
        with self.assertRaisesConfigError("Endpoint must be a string"):
            ZulipStatusPush(endpoint=1234, token="abcd")

    def test_token_string(self):
        with self.assertRaisesConfigError("Token must be a string"):
            ZulipStatusPush(endpoint="http://example.com", token=1234)

    async def test_invalid_json_data(self):
        await self.setupZulipStatusPush(stream="xyz")
        build = await self.insert_build_new()
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
        await self.sp._got_event(('builds', 20, 'new'), build)
        self.assertLogged('500: Error pushing build status to Zulip')

    async def test_invalid_url(self):
        await self.setupZulipStatusPush(stream="xyz")
        build = await self.insert_build_new()
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
        await self.sp._got_event(('builds', 20, 'new'), build)
        self.assertLogged('404: Error pushing build status to Zulip')

    async def test_invalid_token(self):
        await self.setupZulipStatusPush(stream="xyz")
        build = await self.insert_build_new()
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
        await self.sp._got_event(('builds', 20, 'new'), build)
        self.assertLogged('401: Error pushing build status to Zulip')
