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
from buildbot.reporters.bitbucket import _BASE_URL
from buildbot.reporters.bitbucket import _OAUTH_URL
from buildbot.reporters.bitbucket import BitbucketStatusPush
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.fake import fakemaster
from buildbot.test.util.logging import LoggingMixin
from buildbot.test.util.reporter import ReporterTestMixin


class TestBitbucketStatusPush(unittest.TestCase, ReporterTestMixin, LoggingMixin):
    TEST_REPO = u'https://example.org/user/repo'

    @defer.inlineCallbacks
    def setUp(self):
        # ignore config error if txrequests is not installed
        self.patch(config, '_errors', Mock())
        self.master = fakemaster.make_master(testcase=self,
                                             wantData=True, wantDb=True, wantMq=True)

        self._http = yield fakehttpclientservice.HTTPClientService.getFakeService(
            self.master, self,
            _BASE_URL,
            debug=None, verify=None)
        self.oauthhttp = yield fakehttpclientservice.HTTPClientService.getFakeService(
            self.master, self,
            _OAUTH_URL, auth=('key', 'secret'),
            debug=None, verify=None)
        self.bsp = bsp = BitbucketStatusPush('key', 'secret')
        yield bsp.setServiceParent(self.master)
        yield bsp.startService()

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.bsp.stopService()

    @defer.inlineCallbacks
    def setupBuildResults(self, buildResults):
        self.insertTestData([buildResults], buildResults)
        build = yield self.master.data.get(('builds', 20))
        defer.returnValue(build)

    @defer.inlineCallbacks
    def test_basic(self):
        build = yield self.setupBuildResults(SUCCESS)

        self.oauthhttp.expect('post', '', data={'grant_type': 'client_credentials'},
                              content_json={'access_token': 'foo'})
        # we make sure proper calls to txrequests have been made
        self._http.expect(
            'post',
            u'/user/repo/commit/d34db33fd43db33f/statuses/build',
            json={
                'url': 'http://localhost:8080/#builders/79/builds/0',
                'state': 'INPROGRESS',
                'key': u'Builder0',
                'name': u'Builder0'},
            code=201),
        self.oauthhttp.expect('post', '', data={'grant_type': 'client_credentials'},
                              content_json={'access_token': 'foo'})
        self._http.expect(
            'post',
            u'/user/repo/commit/d34db33fd43db33f/statuses/build',
            json={
                'url': 'http://localhost:8080/#builders/79/builds/0',
                'state': 'SUCCESSFUL',
                'key': u'Builder0',
                'name': u'Builder0'},
            code=201),
        self.oauthhttp.expect('post', '', data={'grant_type': 'client_credentials'},
                              content_json={'access_token': 'foo'})
        self._http.expect(
            'post',
            u'/user/repo/commit/d34db33fd43db33f/statuses/build',
            json={
                'url': 'http://localhost:8080/#builders/79/builds/0',
                'state': 'FAILED',
                'key': u'Builder0',
                'name': u'Builder0'},
            code=201)

        build['complete'] = False
        self.bsp.buildStarted(('build', 20, 'started'), build)

        build['complete'] = True
        self.bsp.buildFinished(('build', 20, 'finished'), build)

        build['results'] = FAILURE
        self.bsp.buildFinished(('build', 20, 'finished'), build)

    @defer.inlineCallbacks
    def test_unable_to_authenticate(self):
        build = yield self.setupBuildResults(SUCCESS)

        self.oauthhttp.expect('post', '', data={'grant_type': 'client_credentials'}, code=400,
                              content_json={
                                  "error_description": "Unsupported grant type: None",
                                  "error": "invalid_grant"})
        self.setUpLogging()
        self.bsp.buildStarted(('build', 20, 'started'), build)
        self.assertLogged('400: unable to authenticate to Bitbucket')

    @defer.inlineCallbacks
    def test_unable_to_send_status(self):
        build = yield self.setupBuildResults(SUCCESS)

        self.oauthhttp.expect('post', '', data={'grant_type': 'client_credentials'},
                              content_json={'access_token': 'foo'})
        # we make sure proper calls to txrequests have been made
        self._http.expect(
            'post',
            u'/user/repo/commit/d34db33fd43db33f/statuses/build',
            json={
                'url': 'http://localhost:8080/#builders/79/builds/0',
                'state': 'INPROGRESS',
                'key': u'Builder0',
                'name': u'Builder0'},
            code=404,
            content_json={
                "error_description": "This commit is unknown to us",
                "error": "invalid_commit"}),
        self.setUpLogging()
        self.bsp.buildStarted(('build', 20, 'started'), build)
        self.assertLogged('404: unable to upload Bitbucket status')
        self.assertLogged('This commit is unknown to us')
        self.assertLogged('invalid_commit')


class TestBitbucketStatusPushRepoParsing(unittest.TestCase):

    def parse(self, repourl):
        return tuple(BitbucketStatusPush.get_owner_and_repo(repourl))

    def test_parse_no_scheme(self):
        self.assertEqual(
            ('user', 'repo'), self.parse('git@bitbucket.com:user/repo.git'))
        self.assertEqual(
            ('user', 'repo'), self.parse('git@bitbucket.com:user/repo'))

    def test_parse_with_scheme(self):
        self.assertEqual(('user', 'repo'), self.parse(
            'https://bitbucket.com/user/repo.git'))
        self.assertEqual(
            ('user', 'repo'), self.parse('https://bitbucket.com/user/repo'))

        self.assertEqual(('user', 'repo'), self.parse(
            'ssh://git@bitbucket.com/user/repo.git'))
        self.assertEqual(
            ('user', 'repo'), self.parse('ssh://git@bitbucket.com/user/repo'))
