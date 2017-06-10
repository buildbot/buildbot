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

from __future__ import absolute_import
from __future__ import print_function

from mock import Mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot import config
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.reporters.gitlab import HOSTED_BASE_URL
from buildbot.reporters.gitlab import GitLabStatusPush
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.fake import fakemaster
from buildbot.test.util import logging
from buildbot.test.util.reporter import ReporterTestMixin


class TestGitLabStatusPush(unittest.TestCase, ReporterTestMixin, logging.LoggingMixin):
    # repository must be in the form http://gitlab/<owner>/<project>
    TEST_REPO = u'http://gitlab/buildbot/buildbot'

    @defer.inlineCallbacks
    def setUp(self):
        # ignore config error if txrequests is not installed
        self.patch(config, '_errors', Mock())
        self.master = fakemaster.make_master(testcase=self,
                                             wantData=True, wantDb=True, wantMq=True)

        yield self.master.startService()
        self._http = yield fakehttpclientservice.HTTPClientService.getFakeService(
            self.master, self,
            HOSTED_BASE_URL, headers={'PRIVATE-TOKEN': 'XXYYZZ'},
            debug=None, verify=None)
        self.sp = sp = GitLabStatusPush('XXYYZZ')
        sp.sessionFactory = Mock(return_value=Mock())
        yield sp.setServiceParent(self.master)

    def tearDown(self):
        return self.master.stopService()

    @defer.inlineCallbacks
    def setupBuildResults(self, buildResults):
        self.insertTestData([buildResults], buildResults)
        build = yield self.master.data.get(("builds", 20))
        defer.returnValue(build)

    @defer.inlineCallbacks
    def test_basic(self):
        build = yield self.setupBuildResults(SUCCESS)
        # we make sure proper calls to txrequests have been made
        self._http.expect(
            'get',
            '/api/v3/projects/buildbot%2Fbuildbot', content_json={
                "id": 1
            })
        self._http.expect(
            'post',
            '/api/v3/projects/1/statuses/d34db33fd43db33f',
            json={'state': 'running',
                  'target_url': 'http://localhost:8080/#builders/79/builds/0',
                  'ref': 'master',
                  'description': 'Build started.', 'name': 'buildbot/Builder0'})
        self._http.expect(
            'post',
            '/api/v3/projects/1/statuses/d34db33fd43db33f',
            json={'state': 'success',
                  'target_url': 'http://localhost:8080/#builders/79/builds/0',
                  'ref': 'master',
                  'description': 'Build done.', 'name': 'buildbot/Builder0'})
        self._http.expect(
            'post',
            '/api/v3/projects/1/statuses/d34db33fd43db33f',
            json={'state': 'failed',
                  'target_url': 'http://localhost:8080/#builders/79/builds/0',
                  'ref': 'master',
                  'description': 'Build done.', 'name': 'buildbot/Builder0'})

        build['complete'] = False
        self.sp.buildStarted(("build", 20, "started"), build)
        build['complete'] = True
        self.sp.buildFinished(("build", 20, "finished"), build)
        build['results'] = FAILURE
        self.sp.buildFinished(("build", 20, "finished"), build)

    @defer.inlineCallbacks
    def test_sshurl(self):
        self.TEST_REPO = u'git@gitlab:buildbot/buildbot.git'
        build = yield self.setupBuildResults(SUCCESS)
        # we make sure proper calls to txrequests have been made
        self._http.expect(
            'get',
            '/api/v3/projects/buildbot%2Fbuildbot', content_json={
                "id": 1
            })
        self._http.expect(
            'post',
            '/api/v3/projects/1/statuses/d34db33fd43db33f',
            json={'state': 'running',
                  'target_url': 'http://localhost:8080/#builders/79/builds/0',
                  'ref': 'master',
                  'description': 'Build started.', 'name': 'buildbot/Builder0'})
        build['complete'] = False
        self.sp.buildStarted(("build", 20, "started"), build)

    @defer.inlineCallbacks
    def test_noproject(self):
        self.TEST_REPO = u'git@gitlab:buildbot/buildbot.git'
        self.setUpLogging()
        build = yield self.setupBuildResults(SUCCESS)
        # we make sure proper calls to txrequests have been made
        self._http.expect(
            'get',
            '/api/v3/projects/buildbot%2Fbuildbot', content_json={
                "message": 'project not found'
            }, code=404)
        build['complete'] = False
        self.sp.buildStarted(("build", 20, "started"), build)
        self.assertLogged(r"Unknown \(or hidden\) gitlab projectbuildbot%2Fbuildbot:"
                          r" project not found")

    @defer.inlineCallbacks
    def test_nourl(self):
        self.TEST_REPO = u''
        build = yield self.setupBuildResults(SUCCESS)
        build['complete'] = False
        self.sp.buildStarted(("build", 20, "started"), build)
        # implicit check that no http request is done
        # nothing is logged as well

    @defer.inlineCallbacks
    def test_senderror(self):
        self.setUpLogging()
        build = yield self.setupBuildResults(SUCCESS)
        # we make sure proper calls to txrequests have been made
        self._http.expect(
            'get',
            '/api/v3/projects/buildbot%2Fbuildbot', content_json={
                "id": 1
            })
        self._http.expect(
            'post',
            '/api/v3/projects/1/statuses/d34db33fd43db33f',
            json={'state': 'running',
                  'target_url': 'http://localhost:8080/#builders/79/builds/0',
                  'ref': 'master',
                  'description': 'Build started.', 'name': 'buildbot/Builder0'},
            content_json={'message': 'sha1 not found for branch master'},
            code=404)
        build['complete'] = False
        self.sp.buildStarted(("build", 20, "started"), build)
        self.assertLogged("Could not send status \"running\" for"
                          " http://gitlab/buildbot/buildbot at d34db33fd43db33f:"
                          " sha1 not found for branch master")

    @defer.inlineCallbacks
    def test_badchange(self):
        self.setUpLogging()
        build = yield self.setupBuildResults(SUCCESS)
        # we make sure proper calls to txrequests have been made
        self._http.expect(
            'get',
            '/api/v3/projects/buildbot%2Fbuildbot', content_json={
                "id": 1
            })
        build['complete'] = False
        self.sp.buildStarted(("build", 20, "started"), build)
        self.assertLogged("Failed to send status \"running\" for"
                          " http://gitlab/buildbot/buildbot at d34db33fd43db33f\n"
                          "Traceback")
        self.flushLoggedErrors(AssertionError)
