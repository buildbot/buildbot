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
from buildbot.process.results import SUCCESS
from buildbot.reporters.http import HttpStatusPush
from buildbot.test.fake import fakemaster
from buildbot.test.util.reporter import ReporterTestMixin


class BuildLookAlike(object):

    """ a class whose instances compares to any build dict that this reporter is supposed to send out"""

    def __init__(self, keys=None):
        self.keys = [
            'builder', 'builderid', 'buildid', 'buildrequest', 'buildrequestid',
            'buildset', 'complete', 'complete_at', 'masterid', 'number',
            'properties', 'results', 'started_at', 'state_string', 'url', 'workerid']
        if keys:
            self.keys.extend(keys)
            self.keys.sort()

    def __eq__(self, b):
        return sorted(b.keys()) == self.keys

    def __repr__(self):
        return "{ any build }"


class TestHttpStatusPush(unittest.TestCase, ReporterTestMixin):

    def setUp(self):
        # ignore config error if txrequests is not installed
        config._errors = Mock()
        self.master = fakemaster.make_master(testcase=self,
                                             wantData=True, wantDb=True, wantMq=True)

    @defer.inlineCallbacks
    def createReporter(self, **kwargs):
        self.sp = sp = HttpStatusPush("serv", "username", "passwd", **kwargs)
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
        yield self.createReporter()
        build = yield self.setupBuildResults(SUCCESS)
        build['complete'] = False
        self.sp.buildStarted(("build", 20, "started"), build)
        build['complete'] = True
        self.sp.buildFinished(("build", 20, "finished"), build)
        # we make sure proper calls to txrequests have been made
        #
        self.assertEqual(
            self.sp.session.post.mock_calls,
            [call(u'serv',
                  BuildLookAlike(), auth=('username', 'passwd')),
             call(u'serv',
                  BuildLookAlike(), auth=('username', 'passwd'))])

    @defer.inlineCallbacks
    def test_filtering(self):
        yield self.createReporter(builders=['foo'])
        build = yield self.setupBuildResults(SUCCESS)
        self.sp.buildFinished(("build", 20, "finished"), build)
        self.assertEqual(
            self.sp.session.post.mock_calls, [])

    @defer.inlineCallbacks
    def test_filteringPass(self):
        yield self.createReporter(builders=['Builder0'])
        build = yield self.setupBuildResults(SUCCESS)
        self.sp.buildFinished(("build", 20, "finished"), build)
        self.assertEqual(
            self.sp.session.post.mock_calls,
            [call(u'serv',
                  BuildLookAlike(), auth=('username', 'passwd'))])

    @defer.inlineCallbacks
    def test_builderTypeCheck(self):
        yield self.createReporter(builders='Builder0')
        config._errors.addError.assert_any_call(
            "builders must be a list or None")

    @defer.inlineCallbacks
    def test_wantKwargsCheck(self):
        yield self.createReporter(builders='Builder0', wantProperties=True, wantSteps=True,
                                  wantPreviousBuild=True, wantLogs=True)
        build = yield self.setupBuildResults(SUCCESS)
        build['complete'] = True
        self.sp.buildFinished(("build", 20, "finished"), build)
        self.assertEqual(
            self.sp.session.post.mock_calls,
            [call(u'serv',
                  BuildLookAlike(['prev_build', 'steps']), auth=('username', 'passwd'))])
