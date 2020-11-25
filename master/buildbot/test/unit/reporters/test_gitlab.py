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

from mock import Mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot import config
from buildbot.process.properties import Interpolate
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.reporters.gitlab import HOSTED_BASE_URL
from buildbot.reporters.gitlab import GitLabStatusPush
from buildbot.test.fake import fakemaster
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.util import logging
from buildbot.test.util.misc import TestReactorMixin
from buildbot.test.util.reporter import ReporterTestMixin
from buildbot.test.util.warnings import assertProducesWarnings
from buildbot.warnings import DeprecatedApiWarning


class TestGitLabStatusPush(TestReactorMixin, unittest.TestCase,
                           ReporterTestMixin, logging.LoggingMixin):

    @defer.inlineCallbacks
    def setUp(self):
        self.setUpTestReactor()

        self.setup_reporter_test()
        # repository must be in the form http://gitlab/<owner>/<project>
        self.reporter_test_repo = 'http://gitlab/buildbot/buildbot'

        # ignore config error if txrequests is not installed
        self.patch(config, '_errors', Mock())
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True,
                                             wantMq=True)

        yield self.master.startService()
        self._http = yield fakehttpclientservice.HTTPClientService.getService(
            self.master, self,
            HOSTED_BASE_URL, headers={'PRIVATE-TOKEN': 'XXYYZZ'},
            debug=None, verify=None)
        self.sp = GitLabStatusPush(Interpolate('XXYYZZ'))
        self.sp.sessionFactory = Mock(return_value=Mock())
        yield self.sp.setServiceParent(self.master)

    def tearDown(self):
        return self.master.stopService()

    @defer.inlineCallbacks
    def test_basic(self):
        build = yield self.insert_build_new()
        # we make sure proper calls to txrequests have been made
        self._http.expect(
            'get',
            '/api/v4/projects/buildbot%2Fbuildbot', content_json={
                "id": 1
            })
        self._http.expect(
            'post',
            '/api/v4/projects/1/statuses/d34db33fd43db33f',
            json={'state': 'running',
                  'target_url': 'http://localhost:8080/#builders/79/builds/0',
                  'ref': 'master',
                  'description': 'Build started.', 'name': 'buildbot/Builder0'})
        self._http.expect(
            'post',
            '/api/v4/projects/1/statuses/d34db33fd43db33f',
            json={'state': 'success',
                  'target_url': 'http://localhost:8080/#builders/79/builds/0',
                  'ref': 'master',
                  'description': 'Build done.', 'name': 'buildbot/Builder0'})
        self._http.expect(
            'post',
            '/api/v4/projects/1/statuses/d34db33fd43db33f',
            json={'state': 'failed',
                  'target_url': 'http://localhost:8080/#builders/79/builds/0',
                  'ref': 'master',
                  'description': 'Build done.', 'name': 'buildbot/Builder0'})

        yield self.sp._got_event(('builds', 20, 'new'), build)
        build['complete'] = True
        build['results'] = SUCCESS
        yield self.sp._got_event(('builds', 20, 'finished'), build)
        build['results'] = FAILURE
        yield self.sp._got_event(('builds', 20, 'finished'), build)

    @defer.inlineCallbacks
    def test_sshurl(self):
        self.reporter_test_repo = 'git@gitlab:buildbot/buildbot.git'
        build = yield self.insert_build_new()
        # we make sure proper calls to txrequests have been made
        self._http.expect(
            'get',
            '/api/v4/projects/buildbot%2Fbuildbot', content_json={
                "id": 1
            })
        self._http.expect(
            'post',
            '/api/v4/projects/1/statuses/d34db33fd43db33f',
            json={'state': 'running',
                  'target_url': 'http://localhost:8080/#builders/79/builds/0',
                  'ref': 'master',
                  'description': 'Build started.', 'name': 'buildbot/Builder0'})
        build['complete'] = False
        yield self.sp._got_event(('builds', 20, 'new'), build)

    @defer.inlineCallbacks
    def test_merge_request_forked(self):
        self.reporter_test_repo = 'git@gitlab:buildbot/buildbot.git'
        self.reporter_test_props['source_project_id'] = 20922342342
        build = yield self.insert_build_new()
        self._http.expect(
            'post',
            '/api/v4/projects/20922342342/statuses/d34db33fd43db33f',
            json={'state': 'running',
                  'target_url': 'http://localhost:8080/#builders/79/builds/0',
                  'ref': 'master',
                  'description': 'Build started.', 'name': 'buildbot/Builder0'})
        build['complete'] = False
        yield self.sp._got_event(('builds', 20, 'new'), build)
        # Don't run these tests in parallel!
        del self.reporter_test_props['source_project_id']

    @defer.inlineCallbacks
    def test_noproject(self):
        self.reporter_test_repo = 'git@gitlab:buildbot/buildbot.git'
        self.setUpLogging()
        build = yield self.insert_build_new()
        # we make sure proper calls to txrequests have been made
        self._http.expect(
            'get',
            '/api/v4/projects/buildbot%2Fbuildbot', content_json={
                "message": 'project not found'
            }, code=404)
        build['complete'] = False
        yield self.sp._got_event(('builds', 20, 'new'), build)
        self.assertLogged(r"Unknown \(or hidden\) gitlab projectbuildbot%2Fbuildbot:"
                          r" project not found")

    @defer.inlineCallbacks
    def test_nourl(self):
        self.reporter_test_repo = ''
        build = yield self.insert_build_new()
        build['complete'] = False
        yield self.sp._got_event(('builds', 20, 'new'), build)
        # implicit check that no http request is done
        # nothing is logged as well

    @defer.inlineCallbacks
    def test_senderror(self):
        self.setUpLogging()
        build = yield self.insert_build_new()
        # we make sure proper calls to txrequests have been made
        self._http.expect(
            'get',
            '/api/v4/projects/buildbot%2Fbuildbot', content_json={
                "id": 1
            })
        self._http.expect(
            'post',
            '/api/v4/projects/1/statuses/d34db33fd43db33f',
            json={'state': 'running',
                  'target_url': 'http://localhost:8080/#builders/79/builds/0',
                  'ref': 'master',
                  'description': 'Build started.', 'name': 'buildbot/Builder0'},
            content_json={'message': 'sha1 not found for branch master'},
            code=404)
        build['complete'] = False
        yield self.sp._got_event(('builds', 20, 'new'), build)
        self.assertLogged("Could not send status \"running\" for"
                          " http://gitlab/buildbot/buildbot at d34db33fd43db33f:"
                          " sha1 not found for branch master")

    @defer.inlineCallbacks
    def test_badchange(self):
        self.setUpLogging()
        build = yield self.insert_build_new()
        # we make sure proper calls to txrequests have been made
        self._http.expect(
            'get',
            '/api/v4/projects/buildbot%2Fbuildbot', content_json={
                "id": 1
            })
        build['complete'] = False
        yield self.sp._got_event(('builds', 20, 'new'), build)
        self.assertLogged("Failed to send status \"running\" for"
                          " http://gitlab/buildbot/buildbot at d34db33fd43db33f\n"
                          "Traceback")
        self.flushLoggedErrors(AssertionError)


class GitLabStatusPushDeprecatedSend(GitLabStatusPush):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.send_called_count = 0

    @defer.inlineCallbacks
    def send(self, build):
        self.send_called_count += 1
        yield super().send(build)


class TestGitLabStatusPushDeprecatedSend(TestReactorMixin, unittest.TestCase,
                                         ReporterTestMixin, logging.LoggingMixin):

    @defer.inlineCallbacks
    def setUp(self):
        self.setUpTestReactor()

        self.setup_reporter_test()
        # repository must be in the form http://gitlab/<owner>/<project>
        self.reporter_test_repo = 'http://gitlab/buildbot/buildbot'

        # ignore config error if txrequests is not installed
        self.patch(config, '_errors', Mock())
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True,
                                             wantMq=True)

        yield self.master.startService()
        self._http = yield fakehttpclientservice.HTTPClientService.getService(
            self.master, self,
            HOSTED_BASE_URL, headers={'PRIVATE-TOKEN': 'XXYYZZ'},
            debug=None, verify=None)
        self.sp = GitLabStatusPushDeprecatedSend(Interpolate('XXYYZZ'))
        self.sp.sessionFactory = Mock(return_value=Mock())
        yield self.sp.setServiceParent(self.master)

    def tearDown(self):
        return self.master.stopService()

    @defer.inlineCallbacks
    def test_basic(self):
        build = yield self.insert_build_new()
        # we make sure proper calls to txrequests have been made
        self._http.expect(
            'get',
            '/api/v4/projects/buildbot%2Fbuildbot', content_json={
                "id": 1
            })
        self._http.expect(
            'post',
            '/api/v4/projects/1/statuses/d34db33fd43db33f',
            json={'state': 'running',
                  'target_url': 'http://localhost:8080/#builders/79/builds/0',
                  'ref': 'master',
                  'description': 'Build started.', 'name': 'buildbot/Builder0'})
        self._http.expect(
            'post',
            '/api/v4/projects/1/statuses/d34db33fd43db33f',
            json={'state': 'success',
                  'target_url': 'http://localhost:8080/#builders/79/builds/0',
                  'ref': 'master',
                  'description': 'Build done.', 'name': 'buildbot/Builder0'})
        self._http.expect(
            'post',
            '/api/v4/projects/1/statuses/d34db33fd43db33f',
            json={'state': 'failed',
                  'target_url': 'http://localhost:8080/#builders/79/builds/0',
                  'ref': 'master',
                  'description': 'Build done.', 'name': 'buildbot/Builder0'})

        with assertProducesWarnings(DeprecatedApiWarning,
                                    message_pattern='send\\(\\) in reporters has been deprecated'):
            yield self.sp._got_event(('builds', 20, 'new'), build)
        build['complete'] = True
        build['results'] = SUCCESS
        with assertProducesWarnings(DeprecatedApiWarning,
                                    message_pattern='send\\(\\) in reporters has been deprecated'):
            yield self.sp._got_event(('builds', 20, 'finished'), build)
        build['results'] = FAILURE
        with assertProducesWarnings(DeprecatedApiWarning,
                                    message_pattern='send\\(\\) in reporters has been deprecated'):
            yield self.sp._got_event(('builds', 20, 'finished'), build)

        self.assertEqual(self.sp.send_called_count, 3)
