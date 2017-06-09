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
from buildbot.reporters.github import HOSTED_BASE_URL
from buildbot.reporters.github import GitHubCommentPush
from buildbot.reporters.github import GitHubStatusPush
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.fake import fakemaster
from buildbot.test.util.reporter import ReporterTestMixin


class TestGitHubStatusPush(unittest.TestCase, ReporterTestMixin):
    # project must be in the form <owner>/<project>
    TEST_PROJECT = u'buildbot/buildbot'

    @defer.inlineCallbacks
    def setUp(self):
        # ignore config error if txrequests is not installed
        self.patch(config, '_errors', Mock())
        self.master = fakemaster.make_master(testcase=self,
                                             wantData=True, wantDb=True, wantMq=True)

        yield self.master.startService()
        self._http = yield fakehttpclientservice.HTTPClientService.getFakeService(
            self.master, self,
            HOSTED_BASE_URL, headers={
                'Authorization': 'token XXYYZZ',
                'User-Agent': 'Buildbot'
            },
            debug=None, verify=None)
        sp = self.setService()
        sp.sessionFactory = Mock(return_value=Mock())
        yield sp.setServiceParent(self.master)

    def setService(self):
        self.sp = GitHubStatusPush('XXYYZZ')
        return self.sp

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
            'post',
            '/repos/buildbot/buildbot/statuses/d34db33fd43db33f',
            json={'state': 'pending',
                  'target_url': 'http://localhost:8080/#builders/79/builds/0',
                  'description': 'Build started.', 'context': 'buildbot/Builder0'})
        self._http.expect(
            'post',
            '/repos/buildbot/buildbot/statuses/d34db33fd43db33f',
            json={'state': 'success',
                  'target_url': 'http://localhost:8080/#builders/79/builds/0',
                  'description': 'Build done.', 'context': 'buildbot/Builder0'})
        self._http.expect(
            'post',
            '/repos/buildbot/buildbot/statuses/d34db33fd43db33f',
            json={'state': 'failure',
                  'target_url': 'http://localhost:8080/#builders/79/builds/0',
                  'description': 'Build done.', 'context': 'buildbot/Builder0'})

        build['complete'] = False
        self.sp.buildStarted(("build", 20, "started"), build)
        build['complete'] = True
        self.sp.buildFinished(("build", 20, "finished"), build)
        build['results'] = FAILURE
        self.sp.buildFinished(("build", 20, "finished"), build)

    @defer.inlineCallbacks
    def setupBuildResultsMin(self, buildResults):
        self.insertTestData([buildResults], buildResults, insertSS=False)
        build = yield self.master.data.get(("builds", 20))
        defer.returnValue(build)

    @defer.inlineCallbacks
    def test_empty(self):
        build = yield self.setupBuildResultsMin(SUCCESS)
        build['complete'] = False
        self.sp.buildStarted(("build", 20, "started"), build)
        build['complete'] = True
        self.sp.buildFinished(("build", 20, "finished"), build)
        build['results'] = FAILURE
        self.sp.buildFinished(("build", 20, "finished"), build)


class TestGitHubCommentPush(TestGitHubStatusPush):

    def setService(self):
        self.sp = GitHubCommentPush('XXYYZZ')
        return self.sp

    @defer.inlineCallbacks
    def test_basic(self):
        build = yield self.setupBuildResults(SUCCESS)
        # we make sure proper calls to txrequests have been made
        self._http.expect(
            'post',
            '/repos/buildbot/buildbot/issues/34/comments',
            json={'body': 'Build done.'})
        self._http.expect(
            'post',
            '/repos/buildbot/buildbot/issues/34/comments',
            json={'body': 'Build done.'})

        build['complete'] = False
        self.sp.buildStarted(("build", 20, "started"), build)
        build['complete'] = True
        self.sp.buildFinished(("build", 20, "finished"), build)
        build['results'] = FAILURE
        self.sp.buildFinished(("build", 20, "finished"), build)

    @defer.inlineCallbacks
    def test_empty(self):
        build = yield self.setupBuildResultsMin(SUCCESS)
        build['complete'] = False
        self.sp.buildStarted(("build", 20, "started"), build)
        build['complete'] = True
        self.sp.buildFinished(("build", 20, "finished"), build)
        build['results'] = FAILURE
        self.sp.buildFinished(("build", 20, "finished"), build)
