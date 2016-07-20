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
from mock import call

from twisted.internet import defer
from twisted.trial import unittest

from buildbot import config
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.reporters.bitbucket import BitbucketStatusPush
from buildbot.test.fake import fakemaster
from buildbot.test.util.reporter import ReporterTestMixin


class TestBitbucketStatusPush(unittest.TestCase, ReporterTestMixin):
    TEST_REPO = u'https://example.org/user/repo'

    @defer.inlineCallbacks
    def setUp(self):
        # ignore config error if txrequests is not installed
        config._errors = Mock()
        self.master = fakemaster.make_master(testcase=self,
                                             wantData=True, wantDb=True, wantMq=True)

        self.bsp = bsp = BitbucketStatusPush('key', 'secret')
        bsp.sessionFactory = Mock(return_value=Mock())
        yield bsp.setServiceParent(self.master)
        yield bsp.startService()

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.bsp.stopService()
        self.assertEqual(self.bsp.session.close.call_count, 1)
        config._errors = None

    @defer.inlineCallbacks
    def setupBuildResults(self, buildResults):
        self.insertTestData([buildResults], buildResults)
        build = yield self.master.data.get(('builds', 20))
        defer.returnValue(build)

    @defer.inlineCallbacks
    def test_basic(self):
        build = yield self.setupBuildResults(SUCCESS)

        build['complete'] = False
        self.bsp.buildStarted(('build', 20, 'started'), build)

        build['complete'] = True
        self.bsp.buildFinished(('build', 20, 'finished'), build)

        build['results'] = FAILURE
        self.bsp.buildFinished(('build', 20, 'finished'), build)

        # we make sure proper calls to txrequests have been made
        self.assertEqual(
            self.bsp.session.post.mock_calls, [
                call('https://bitbucket.org/site/oauth2/access_token',
                     auth=('key', 'secret'),
                     data={'grant_type': 'client_credentials'}),
                call(u'https://api.bitbucket.org/2.0/repositories/user/repo/commit/d34db33fd43db33f/statuses/build',
                     json={
                         'url': 'http://localhost:8080/#builders/79/builds/0',
                         'state': 'INPROGRESS',
                         'key': u'Builder0',
                         'name': u'Builder0'}),
                call('https://bitbucket.org/site/oauth2/access_token',
                     auth=('key', 'secret'),
                     data={'grant_type': 'client_credentials'}),
                call(u'https://api.bitbucket.org/2.0/repositories/user/repo/commit/d34db33fd43db33f/statuses/build',
                     json={
                         'url': 'http://localhost:8080/#builders/79/builds/0',
                         'state': 'SUCCESSFUL',
                         'key': u'Builder0',
                         'name': u'Builder0'}),
                call('https://bitbucket.org/site/oauth2/access_token',
                     auth=('key', 'secret'),
                     data={'grant_type': 'client_credentials'}),
                call(u'https://api.bitbucket.org/2.0/repositories/user/repo/commit/d34db33fd43db33f/statuses/build',
                     json={
                         'url': 'http://localhost:8080/#builders/79/builds/0',
                         'state': 'FAILED',
                         'key': u'Builder0',
                         'name': u'Builder0'})
            ])
