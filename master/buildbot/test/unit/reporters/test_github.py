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
from buildbot.reporters.github import HOSTED_BASE_URL
from buildbot.reporters.github import GitHubCommentPush
from buildbot.reporters.github import GitHubStatusPush
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.util.misc import TestReactorMixin
from buildbot.test.util.reporter import ReporterTestMixin


class TestGitHubStatusPush(TestReactorMixin, unittest.TestCase,
                           ReporterTestMixin):
    # project must be in the form <owner>/<project>
    TEST_PROJECT = 'buildbot/buildbot'

    @defer.inlineCallbacks
    def setUp(self):
        self.setUpTestReactor()
        # ignore config error if txrequests is not installed
        self.patch(config, '_errors', Mock())
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True,
                                             wantMq=True)

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
        self.sp = GitHubStatusPush(Interpolate('XXYYZZ'))
        return self.sp

    def tearDown(self):
        return self.master.stopService()

    @defer.inlineCallbacks
    def setupBuildResults(self, buildResults):
        self.insertTestData([buildResults], buildResults)
        build = yield self.master.data.get(("builds", 20))
        return build

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
        return build

    @defer.inlineCallbacks
    def test_empty(self):
        build = yield self.setupBuildResultsMin(SUCCESS)
        build['complete'] = False
        self.sp.buildStarted(("build", 20, "started"), build)
        build['complete'] = True
        self.sp.buildFinished(("build", 20, "finished"), build)
        build['results'] = FAILURE
        self.sp.buildFinished(("build", 20, "finished"), build)

    @defer.inlineCallbacks
    def test_source_stamp_no_props_nightly_scheduler(self):
        # no status updates are expected

        self.master.db.insertTestData([
            fakedb.Master(id=92),
            fakedb.Worker(id=13, name='wrk'),
            fakedb.Builder(id=79, name='Builder0'),
            fakedb.Buildset(id=98, results=SUCCESS, reason="test_reason1"),
            fakedb.BuildsetSourceStamp(buildsetid=98, sourcestampid=234),
            fakedb.SourceStamp(id=234, project=None, branch=None, revision=None,
                               repository=None, codebase=None),
            fakedb.BuildRequest(id=11, buildsetid=98, builderid=79),
            fakedb.Build(id=20, number=0, builderid=79, buildrequestid=11,
                         workerid=13, masterid=92, results=SUCCESS, state_string="build_text"),
            fakedb.BuildProperty(buildid=20, name="workername", value="wrk"),
            fakedb.BuildProperty(buildid=20, name="reason", value="because"),
            fakedb.BuildProperty(buildid=20, name="buildername", value="Builder0"),
            fakedb.BuildProperty(buildid=20, name="branch", value=None),
            fakedb.BuildProperty(buildid=20, name="codebase", value=""),
            fakedb.BuildProperty(buildid=20, name="project", value=""),
            fakedb.BuildProperty(buildid=20, name="repository", value=""),
            fakedb.BuildProperty(buildid=20, name="revision", value=None),
        ])

        build = yield self.master.data.get(("builds", 20))

        build['complete'] = False
        self.sp.buildStarted(("build", 20, "started"), build)
        build['complete'] = True
        self.sp.buildFinished(("build", 20, "finished"), build)
        build['results'] = SUCCESS
        self.sp.buildFinished(("build", 20, "finished"), build)

    @defer.inlineCallbacks
    def test_multiple_source_stamps_no_props(self):
        repository = 'http://test_repo'
        project = 'test_user/test_project'
        codebase1 = 'test_codebase1'
        codebase2 = 'test_codebase2'
        codebase3 = 'test_codebase3'

        self._http.expect(
            'post',
            '/repos/test_user/test_project/statuses/rev1',
            json={'state': 'pending',
                  'target_url': 'http://localhost:8080/#builders/79/builds/0',
                  'description': 'Build started.', 'context': 'buildbot/Builder0'})
        self._http.expect(
            'post',
            '/repos/test_user/test_project/statuses/rev3',
            json={'state': 'pending',
                  'target_url': 'http://localhost:8080/#builders/79/builds/0',
                  'description': 'Build started.', 'context': 'buildbot/Builder0'})
        self._http.expect(
            'post',
            '/repos/test_user/test_project/statuses/rev1',
            json={'state': 'success',
                  'target_url': 'http://localhost:8080/#builders/79/builds/0',
                  'description': 'Build done.', 'context': 'buildbot/Builder0'})
        self._http.expect(
            'post',
            '/repos/test_user/test_project/statuses/rev3',
            json={'state': 'success',
                  'target_url': 'http://localhost:8080/#builders/79/builds/0',
                  'description': 'Build done.', 'context': 'buildbot/Builder0'})
        self._http.expect(
            'post',
            '/repos/test_user/test_project/statuses/rev1',
            json={'state': 'success',
                  'target_url': 'http://localhost:8080/#builders/79/builds/0',
                  'description': 'Build done.', 'context': 'buildbot/Builder0'})
        self._http.expect(
            'post',
            '/repos/test_user/test_project/statuses/rev3',
            json={'state': 'success',
                  'target_url': 'http://localhost:8080/#builders/79/builds/0',
                  'description': 'Build done.', 'context': 'buildbot/Builder0'})

        # note that the first sourcestamp only has revision, second only branch and only the third
        # has both
        self.master.db.insertTestData([
            fakedb.Master(id=92),
            fakedb.Worker(id=13, name='wrk'),
            fakedb.Builder(id=79, name='Builder0'),
            fakedb.Buildset(id=98, results=SUCCESS, reason="test_reason1"),
            fakedb.BuildsetSourceStamp(buildsetid=98, sourcestampid=234),
            fakedb.BuildsetSourceStamp(buildsetid=98, sourcestampid=235),
            fakedb.BuildsetSourceStamp(buildsetid=98, sourcestampid=236),
            fakedb.SourceStamp(id=234, project=project, branch=None, revision='rev1',
                               repository=repository, codebase=codebase1),
            fakedb.SourceStamp(id=235, project=project, branch='branch2', revision=None,
                               repository=repository, codebase=codebase2),
            fakedb.SourceStamp(id=236, project=project, branch='branch3', revision='rev3',
                               repository=repository, codebase=codebase3),
            fakedb.BuildRequest(id=11, buildsetid=98, builderid=79),
            fakedb.Build(id=20, number=0, builderid=79, buildrequestid=11,
                         workerid=13, masterid=92, results=SUCCESS, state_string="build_text"),
            fakedb.BuildProperty(buildid=20, name="buildername", value="Builder0"),
        ])

        build = yield self.master.data.get(("builds", 20))

        build['complete'] = False
        self.sp.buildStarted(("build", 20, "started"), build)
        build['complete'] = True
        self.sp.buildFinished(("build", 20, "finished"), build)
        build['results'] = SUCCESS
        self.sp.buildFinished(("build", 20, "finished"), build)


class TestGitHubStatusPushURL(TestReactorMixin, unittest.TestCase,
                              ReporterTestMixin):
    # project must be in the form <owner>/<project>
    TEST_PROJECT = 'buildbot'
    TEST_REPO = 'https://github.com/buildbot1/buildbot1.git'

    @defer.inlineCallbacks
    def setUp(self):
        self.setUpTestReactor()

        # ignore config error if txrequests is not installed
        self.patch(config, '_errors', Mock())
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True,
                                             wantMq=True)

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
        return build

    @defer.inlineCallbacks
    def test_ssh(self):
        self.TEST_REPO = 'git@github.com:buildbot2/buildbot2.git'

        build = yield self.setupBuildResults(SUCCESS)
        # we make sure proper calls to txrequests have been made
        self._http.expect(
            'post',
            '/repos/buildbot2/buildbot2/statuses/d34db33fd43db33f',
            json={'state': 'pending',
                  'target_url': 'http://localhost:8080/#builders/79/builds/0',
                  'description': 'Build started.', 'context': 'buildbot/Builder0'})
        self._http.expect(
            'post',
            '/repos/buildbot2/buildbot2/statuses/d34db33fd43db33f',
            json={'state': 'success',
                  'target_url': 'http://localhost:8080/#builders/79/builds/0',
                  'description': 'Build done.', 'context': 'buildbot/Builder0'})
        self._http.expect(
            'post',
            '/repos/buildbot2/buildbot2/statuses/d34db33fd43db33f',
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
    def test_https(self):
        build = yield self.setupBuildResults(SUCCESS)
        # we make sure proper calls to txrequests have been made
        self._http.expect(
            'post',
            '/repos/buildbot1/buildbot1/statuses/d34db33fd43db33f',
            json={'state': 'pending',
                  'target_url': 'http://localhost:8080/#builders/79/builds/0',
                  'description': 'Build started.', 'context': 'buildbot/Builder0'})
        self._http.expect(
            'post',
            '/repos/buildbot1/buildbot1/statuses/d34db33fd43db33f',
            json={'state': 'success',
                  'target_url': 'http://localhost:8080/#builders/79/builds/0',
                  'description': 'Build done.', 'context': 'buildbot/Builder0'})
        self._http.expect(
            'post',
            '/repos/buildbot1/buildbot1/statuses/d34db33fd43db33f',
            json={'state': 'failure',
                  'target_url': 'http://localhost:8080/#builders/79/builds/0',
                  'description': 'Build done.', 'context': 'buildbot/Builder0'})

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

    @defer.inlineCallbacks
    def test_multiple_source_stamps_no_props(self):
        repository = 'http://test_repo'
        project = 'test_user/test_project'
        codebase1 = 'test_codebase1'
        codebase2 = 'test_codebase2'
        codebase3 = 'test_codebase3'
        branch2 = 'refs/pull/4192/merge'
        branch3 = 'refs/pull/4193/merge'

        self._http.expect(
            'post',
            '/repos/test_user/test_project/issues/4192/comments',
            json={'body': 'Build done.'})
        self._http.expect(
            'post',
            '/repos/test_user/test_project/issues/4192/comments',
            json={'body': 'Build done.'})
        self._http.expect(
            'post',
            '/repos/test_user/test_project/issues/4192/comments',
            json={'body': 'Build done.'})
        self._http.expect(
            'post',
            '/repos/test_user/test_project/issues/4192/comments',
            json={'body': 'Build done.'})

        # note that the first sourcestamp only has revision, second only branch and only the third
        # has both
        self.master.db.insertTestData([
            fakedb.Master(id=92),
            fakedb.Worker(id=13, name='wrk'),
            fakedb.Builder(id=79, name='Builder0'),
            fakedb.Buildset(id=98, results=SUCCESS, reason="test_reason1"),
            fakedb.BuildsetSourceStamp(buildsetid=98, sourcestampid=234),
            fakedb.BuildsetSourceStamp(buildsetid=98, sourcestampid=235),
            fakedb.BuildsetSourceStamp(buildsetid=98, sourcestampid=236),
            fakedb.SourceStamp(id=234, project=project, branch=None, revision='rev1',
                               repository=repository, codebase=codebase1),
            fakedb.SourceStamp(id=235, project=project, branch=branch2, revision=None,
                               repository=repository, codebase=codebase2),
            fakedb.SourceStamp(id=236, project=project, branch=branch3, revision='rev3',
                               repository=repository, codebase=codebase3),
            fakedb.BuildRequest(id=11, buildsetid=98, builderid=79),
            fakedb.Build(id=20, number=0, builderid=79, buildrequestid=11,
                         workerid=13, masterid=92, results=SUCCESS, state_string="build_text"),
            fakedb.BuildProperty(buildid=20, name="buildername", value="Builder0"),
            fakedb.BuildProperty(buildid=20, name="branch", value=branch2),
        ])

        build = yield self.master.data.get(("builds", 20))

        build['complete'] = False
        self.sp.buildStarted(("build", 20, "started"), build)
        build['complete'] = True
        self.sp.buildFinished(("build", 20, "finished"), build)
        build['results'] = SUCCESS
        self.sp.buildFinished(("build", 20, "finished"), build)
