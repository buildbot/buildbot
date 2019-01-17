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

import datetime

from dateutil.tz import tzutc

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process.results import SUCCESS
from buildbot.reporters.zulip import ZulipStatusPush
from buildbot.test.fake import fakemaster
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.test.util.logging import LoggingMixin
from buildbot.test.util.misc import TestReactorMixin
from buildbot.test.util.reporter import ReporterTestMixin


class TestZulipStatusPush(unittest.TestCase, ReporterTestMixin, LoggingMixin, ConfigErrorsMixin, TestReactorMixin):

    def setUp(self):
        self.setUpTestReactor()
        self.master = fakemaster.make_master(
            testcase=self, wantData=True, wantDb=True, wantMq=True)

    @defer.inlineCallbacks
    def tearDown(self):
        if self.master.running:
            yield self.master.stopService()

    @defer.inlineCallbacks
    def setupZulipStatusPush(self, endpoint="http://example.com", token="123", stream=None):
        self.sp = ZulipStatusPush(
            endpoint=endpoint, token=token, stream=stream)
        self._http = yield fakehttpclientservice.HTTPClientService.getFakeService(
            self.master, self, endpoint, debug=None, verify=None)
        yield self.sp.setServiceParent(self.master)
        yield self.master.startService()

    @defer.inlineCallbacks
    def setupBuildResults(self):
        self.insertTestData([SUCCESS], SUCCESS)
        build = yield self.master.data.get(("builds", 20))
        return build

    @defer.inlineCallbacks
    def test_build_started(self):
        yield self.setupZulipStatusPush(stream="xyz")
        build = yield self.setupBuildResults()
        build["started_at"] = datetime.datetime(
            2019, 4, 1, 23, 38, 43, 154354, tzinfo=tzutc())
        self._http.expect(
            'post',
            '/api/v1/external/buildbot?api_key=123&stream=xyz',
            json={
                "event": "new",
                "buildid": 20,
                "buildername": "Builder0",
                "url": "http://localhost:8080/#builders/79/builds/0",
                "project": "testProject",
                "timestamp": 1554161923
            })
        self.sp.buildStarted(('build', 20, 'new'), build)

    @defer.inlineCallbacks
    def test_build_finished(self):
        yield self.setupZulipStatusPush(stream="xyz")
        build = yield self.setupBuildResults()
        build["complete_at"] = datetime.datetime(
            2019, 4, 1, 23, 38, 43, 154354, tzinfo=tzutc())
        self._http.expect(
            'post',
            '/api/v1/external/buildbot?api_key=123&stream=xyz',
            json={
                "event": "finished",
                "buildid": 20,
                "buildername": "Builder0",
                "url": "http://localhost:8080/#builders/79/builds/0",
                "project": "testProject",
                "timestamp": 1554161923,
                "results": 0
            })
        self.sp.buildFinished(('build', 20, 'finished'), build)

    @defer.inlineCallbacks
    def test_stream_none(self):
        yield self.setupZulipStatusPush(stream=None)
        build = yield self.setupBuildResults()
        build["complete_at"] = datetime.datetime(
            2019, 4, 1, 23, 38, 43, 154354, tzinfo=tzutc())
        self._http.expect(
            'post',
            '/api/v1/external/buildbot?api_key=123',
            json={
                "event": "finished",
                "buildid": 20,
                "buildername": "Builder0",
                "url": "http://localhost:8080/#builders/79/builds/0",
                "project": "testProject",
                "timestamp": 1554161923,
                "results": 0
            })
        self.sp.buildFinished(('build', 20, 'finished'), build)

    def test_endpoint_string(self):
        with self.assertRaisesConfigError(
                "Endpoint must be a string"):
            ZulipStatusPush(endpoint=1234, token="abcd")

    def test_token_string(self):
        with self.assertRaisesConfigError(
                "Token must be a string"):
            ZulipStatusPush(endpoint="http://example.com", token=1234)

    @defer.inlineCallbacks
    def test_invalid_json_data(self):
        yield self.setupZulipStatusPush(stream="xyz")
        build = yield self.setupBuildResults()
        build["started_at"] = datetime.datetime(
            2019, 4, 1, 23, 38, 43, 154354, tzinfo=tzutc())
        self._http.expect(
            'post',
            '/api/v1/external/buildbot?api_key=123&stream=xyz',
            json={
                "event": "new",
                "buildid": 20,
                "buildername": "Builder0",
                "url": "http://localhost:8080/#builders/79/builds/0",
                "project": "testProject",
                "timestamp": 1554161923
            }, code=500)
        self.setUpLogging()
        self.sp.buildStarted(("build", 20, "new"), build)
        self.assertLogged('500: Error pushing build status to Zulip')

    @defer.inlineCallbacks
    def test_invalid_url(self):
        yield self.setupZulipStatusPush(stream="xyz")
        build = yield self.setupBuildResults()
        build["started_at"] = datetime.datetime(
            2019, 4, 1, 23, 38, 43, 154354, tzinfo=tzutc())
        self._http.expect(
            'post',
            '/api/v1/external/buildbot?api_key=123&stream=xyz',
            json={
                "event": "new",
                "buildid": 20,
                "buildername": "Builder0",
                "url": "http://localhost:8080/#builders/79/builds/0",
                "project": "testProject",
                "timestamp": 1554161923
            }, code=404)
        self.setUpLogging()
        self.sp.buildStarted(("build", 20, "new"), build)
        self.assertLogged('404: Error pushing build status to Zulip')

    @defer.inlineCallbacks
    def test_invalid_token(self):
        yield self.setupZulipStatusPush(stream="xyz")
        build = yield self.setupBuildResults()
        build["started_at"] = datetime.datetime(
            2019, 4, 1, 23, 38, 43, 154354, tzinfo=tzutc())
        self._http.expect(
            'post',
            '/api/v1/external/buildbot?api_key=123&stream=xyz',
            json={
                "event": "new",
                "buildid": 20,
                "buildername": "Builder0",
                "url": "http://localhost:8080/#builders/79/builds/0",
                "project": "testProject",
                "timestamp": 1554161923
            }, code=401, content_json={"result": "error", "msg": "Invalid API key", "code": "INVALID_API_KEY"})
        self.setUpLogging()
        self.sp.buildStarted(("build", 20, "new"), build)
        self.assertLogged('401: Error pushing build status to Zulip')
