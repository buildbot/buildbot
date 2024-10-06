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

from unittest import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process.builder import Builder
from buildbot.process.properties import Interpolate
from buildbot.process.results import CANCELLED
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.reporters.gitlab import HOSTED_BASE_URL
from buildbot.reporters.gitlab import GitLabStatusPush
from buildbot.test.fake import fakemaster
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import logging
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.test.util.reporter import ReporterTestMixin


class TestGitLabStatusPush(
    TestReactorMixin, ConfigErrorsMixin, unittest.TestCase, ReporterTestMixin, logging.LoggingMixin
):
    async def setUp(self):
        self.setup_test_reactor()

        self.setup_reporter_test()
        # repository must be in the form http://gitlab/<owner>/<project>
        self.reporter_test_repo = 'http://gitlab/buildbot/buildbot'

        self.master = fakemaster.make_master(self, wantData=True, wantDb=True, wantMq=True)

        await self.master.startService()
        self._http = await fakehttpclientservice.HTTPClientService.getService(
            self.master,
            self,
            HOSTED_BASE_URL,
            headers={'PRIVATE-TOKEN': 'XXYYZZ'},
            debug=None,
            verify=None,
        )
        self.sp = GitLabStatusPush(Interpolate('XXYYZZ'))
        await self.sp.setServiceParent(self.master)

        def setup_properties(props):
            props.setProperty("buildername", "Builder0", "Builder")
            return defer.succeed(None)

        builder = mock.Mock(spec=Builder)
        builder.master = self.master
        builder.name = "Builder0"
        builder.setup_properties = setup_properties
        self.master.botmaster.getBuilderById = mock.Mock(return_value=builder)

    def tearDown(self):
        return self.master.stopService()

    async def test_buildrequest(self):
        buildrequest = await self.insert_buildrequest_new()
        self._http.expect('get', '/api/v4/projects/buildbot%2Fbuildbot', content_json={"id": 1})
        self._http.expect(
            'post',
            '/api/v4/projects/1/statuses/d34db33fd43db33f',
            json={
                'state': 'pending',
                'target_url': 'http://localhost:8080/#/buildrequests/11',
                'ref': 'master',
                'description': 'Build pending.',
                'name': 'buildbot/Builder0',
            },
        )
        self._http.expect(
            'post',
            '/api/v4/projects/1/statuses/d34db33fd43db33f',
            json={
                'state': 'canceled',
                'target_url': 'http://localhost:8080/#/buildrequests/11',
                'ref': 'master',
                'description': 'Build pending.',
                'name': 'buildbot/Builder0',
            },
        )

        await self.sp._got_event(('buildrequests', 11, 'new'), buildrequest)
        await self.sp._got_event(('buildrequests', 11, 'cancel'), buildrequest)

    async def test_basic(self):
        build = await self.insert_build_new()
        self._http.expect('get', '/api/v4/projects/buildbot%2Fbuildbot', content_json={"id": 1})
        self._http.expect(
            'post',
            '/api/v4/projects/1/statuses/d34db33fd43db33f',
            json={
                'state': 'running',
                'target_url': 'http://localhost:8080/#/builders/79/builds/0',
                'ref': 'master',
                'description': 'Build started.',
                'name': 'buildbot/Builder0',
            },
        )
        self._http.expect(
            'post',
            '/api/v4/projects/1/statuses/d34db33fd43db33f',
            json={
                'state': 'success',
                'target_url': 'http://localhost:8080/#/builders/79/builds/0',
                'ref': 'master',
                'description': 'Build done.',
                'name': 'buildbot/Builder0',
            },
        )
        self._http.expect(
            'post',
            '/api/v4/projects/1/statuses/d34db33fd43db33f',
            json={
                'state': 'failed',
                'target_url': 'http://localhost:8080/#/builders/79/builds/0',
                'ref': 'master',
                'description': 'Build done.',
                'name': 'buildbot/Builder0',
            },
        )
        self._http.expect(
            'post',
            '/api/v4/projects/1/statuses/d34db33fd43db33f',
            json={
                'state': 'canceled',
                'target_url': 'http://localhost:8080/#/builders/79/builds/0',
                'ref': 'master',
                'description': 'Build done.',
                'name': 'buildbot/Builder0',
            },
        )

        await self.sp._got_event(('builds', 20, 'new'), build)
        build['complete'] = True
        build['results'] = SUCCESS
        await self.sp._got_event(('builds', 20, 'finished'), build)
        build['results'] = FAILURE
        await self.sp._got_event(('builds', 20, 'finished'), build)
        build['results'] = CANCELLED
        await self.sp._got_event(('builds', 20, 'finished'), build)

    async def test_sshurl(self):
        self.reporter_test_repo = 'git@gitlab:buildbot/buildbot.git'
        build = await self.insert_build_new()
        self._http.expect('get', '/api/v4/projects/buildbot%2Fbuildbot', content_json={"id": 1})
        self._http.expect(
            'post',
            '/api/v4/projects/1/statuses/d34db33fd43db33f',
            json={
                'state': 'running',
                'target_url': 'http://localhost:8080/#/builders/79/builds/0',
                'ref': 'master',
                'description': 'Build started.',
                'name': 'buildbot/Builder0',
            },
        )
        build['complete'] = False
        await self.sp._got_event(('builds', 20, 'new'), build)

    async def test_merge_request_forked(self):
        self.reporter_test_repo = 'git@gitlab:buildbot/buildbot.git'
        self.reporter_test_props['source_project_id'] = 20922342342
        build = await self.insert_build_new()
        self._http.expect(
            'post',
            '/api/v4/projects/20922342342/statuses/d34db33fd43db33f',
            json={
                'state': 'running',
                'target_url': 'http://localhost:8080/#/builders/79/builds/0',
                'ref': 'master',
                'description': 'Build started.',
                'name': 'buildbot/Builder0',
            },
        )
        build['complete'] = False
        await self.sp._got_event(('builds', 20, 'new'), build)
        # Don't run these tests in parallel!
        del self.reporter_test_props['source_project_id']

    async def test_noproject(self):
        self.reporter_test_repo = 'git@gitlab:buildbot/buildbot.git'
        self.setUpLogging()
        build = await self.insert_build_new()
        self._http.expect(
            'get',
            '/api/v4/projects/buildbot%2Fbuildbot',
            content_json={"message": 'project not found'},
            code=404,
        )
        build['complete'] = False
        await self.sp._got_event(('builds', 20, 'new'), build)
        self.assertLogged(
            r"Unknown \(or hidden\) gitlab projectbuildbot%2Fbuildbot: project not found"
        )

    async def test_nourl(self):
        self.reporter_test_repo = ''
        build = await self.insert_build_new()
        build['complete'] = False
        await self.sp._got_event(('builds', 20, 'new'), build)
        # implicit check that no http request is done
        # nothing is logged as well

    async def test_senderror(self):
        self.setUpLogging()
        build = await self.insert_build_new()
        self._http.expect('get', '/api/v4/projects/buildbot%2Fbuildbot', content_json={"id": 1})
        self._http.expect(
            'post',
            '/api/v4/projects/1/statuses/d34db33fd43db33f',
            json={
                'state': 'running',
                'target_url': 'http://localhost:8080/#/builders/79/builds/0',
                'ref': 'master',
                'description': 'Build started.',
                'name': 'buildbot/Builder0',
            },
            content_json={'message': 'sha1 not found for branch master'},
            code=404,
        )
        build['complete'] = False
        await self.sp._got_event(('builds', 20, 'new'), build)
        self.assertLogged(
            "Could not send status \"running\" for"
            " http://gitlab/buildbot/buildbot at d34db33fd43db33f:"
            " sha1 not found for branch master"
        )

    async def test_badchange(self):
        self.setUpLogging()
        build = await self.insert_build_new()
        self._http.expect('get', '/api/v4/projects/buildbot%2Fbuildbot', content_json={"id": 1})
        build['complete'] = False
        await self.sp._got_event(('builds', 20, 'new'), build)
        self.assertLogged(
            "Failed to send status \"running\" for"
            " http://gitlab/buildbot/buildbot at d34db33fd43db33f\n"
            "Traceback"
        )
        self.flushLoggedErrors(AssertionError)
