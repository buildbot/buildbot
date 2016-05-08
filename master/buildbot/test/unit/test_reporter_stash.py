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
from buildbot.reporters.stash import StashStatusPush
from buildbot.test.fake import fakemaster
from buildbot.test.util.reporter import ReporterTestMixin


class TestStashStatusPush(unittest.TestCase, ReporterTestMixin):

    @defer.inlineCallbacks
    def setUp(self):
        # ignore config error if txrequests is not installed
        config._errors = Mock()
        self.master = fakemaster.make_master(testcase=self,
                                             wantData=True, wantDb=True, wantMq=True)

        self.sp = sp = StashStatusPush("serv", "username", "passwd")
        sp.sessionFactory = Mock(return_value=Mock())
        yield sp.setServiceParent(self.master)
        yield sp.startService()

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.sp.stopService()
        self.assertEqual(self.sp.session.close.call_count, 1)
        config._errors = None

    @defer.inlineCallbacks
    def setupBuildResults(self, buildResults):
        self.insertTestData([buildResults], buildResults)
        build = yield self.master.data.get(("builds", 20))
        defer.returnValue(build)

    @defer.inlineCallbacks
    def test_basic(self):
        build = yield self.setupBuildResults(SUCCESS)
        build['complete'] = False
        self.sp.buildStarted(("build", 20, "started"), build)
        build['complete'] = True
        self.sp.buildFinished(("build", 20, "finished"), build)
        build['results'] = FAILURE
        self.sp.buildFinished(("build", 20, "finished"), build)
        # we make sure proper calls to txrequests have been made
        self.assertEqual(
            self.sp.session.post.mock_calls,
            [call(u'serv/rest/build-status/1.0/commits/d34db33fd43db33f',
                  {'url': 'http://localhost:8080/#builders/79/builds/0',
                   'state': 'INPROGRESS', 'key': u'Builder0'}, auth=('username', 'passwd')),
             call(u'serv/rest/build-status/1.0/commits/d34db33fd43db33f',
                  {'url': 'http://localhost:8080/#builders/79/builds/0',
                   'state': 'SUCCESSFUL', 'key': u'Builder0'}, auth=('username', 'passwd')),
             call(u'serv/rest/build-status/1.0/commits/d34db33fd43db33f',
                  {'url': 'http://localhost:8080/#builders/79/builds/0',
                   'state': 'FAILED', 'key': u'Builder0'}, auth=('username', 'passwd'))])
