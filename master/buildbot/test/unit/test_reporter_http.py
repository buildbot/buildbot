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

from buildbot import config
from buildbot.process.results import SUCCESS
from buildbot.reporters.http import HttpStatusPush
from buildbot.test.fake import fakemaster
from buildbot.test.util.reporter import ReporterTestMixin

from mock import Mock
from mock import call
from twisted.internet import defer
from twisted.trial import unittest


class BuildLookAlike(object):

    """ a class that compare to any build dict that this reporter is supposed to send out"""

    def __eq__(self, b):
        return b.keys() == ['buildrequestid', 'complete', 'buildid', 'workerid', 'number', 'results',
                            'masterid', 'buildrequest', 'buildset', 'started_at', 'properties',
                            'complete_at', 'builderid', 'builder', 'state_string']

    def __repr__(self):
        return "{ any build }"


class TestHttpStatusPush(unittest.TestCase, ReporterTestMixin):

    @defer.inlineCallbacks
    def setUp(self):
        # ignore config error if txrequests is not installed
        config._errors = Mock()
        self.master = fakemaster.make_master(testcase=self,
                                             wantData=True, wantDb=True, wantMq=True)

        self.sp = sp = HttpStatusPush("serv", "username", "passwd")
        sp.sessionFactory = Mock(return_value=Mock())
        yield sp.setServiceParent(self.master)
        yield sp.startService()

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.sp.stopService()
        self.assertEqual(self.sp.session.close.call_count, 1)

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
        # we make sure proper calls to txrequests have been made
        #
        self.assertEqual(
            self.sp.session.post.mock_calls,
            [call(u'serv',
                  {'url': 'http://localhost:8080/#builders/79/builds/0',
                   'build': BuildLookAlike()}, auth=('username', 'passwd')),
             call(u'serv',
                  {'url': 'http://localhost:8080/#builders/79/builds/0',
                   'build': BuildLookAlike()}, auth=('username', 'passwd'))])
