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
from buildbot.process.results import SUCCESS
from buildbot.reporters.http import HttpStatusPush
from buildbot.test.fake import fakemaster
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.util.misc import TestReactorMixin
from buildbot.test.util.reporter import ReporterTestMixin


class BuildLookAlike:

    """ a class whose instances compares to any build dict that this reporter is supposed to send
    out"""

    def __init__(self, keys=None, **assertions):
        self.keys = [
            'builder', 'builderid', 'buildid', 'buildrequest', 'buildrequestid',
            'buildset', 'complete', 'complete_at', 'masterid', 'number',
            'properties', 'results', 'started_at', 'state_string', 'url', 'workerid']
        if keys:
            self.keys.extend(keys)
            self.keys.sort()
        self.assertions = assertions

    def __eq__(self, b):
        if sorted(b.keys()) != self.keys:
            return False
        for k, v in self.assertions.items():
            if b[k] != v:
                return False
        return True

    def __ne__(self, b):
        return not (self == b)

    def __repr__(self):
        return "{ any build }"


class TestHttpStatusPush(TestReactorMixin, unittest.TestCase, ReporterTestMixin):

    @defer.inlineCallbacks
    def setUp(self):
        self.setUpTestReactor()
        # ignore config error if txrequests is not installed
        config._errors = Mock()
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True,
                                             wantMq=True)
        yield self.master.startService()

    @defer.inlineCallbacks
    def createReporter(self, auth=("username", "passwd"), **kwargs):
        self._http = yield fakehttpclientservice.HTTPClientService.getService(
            self.master,
            "serv", auth=auth,
            debug=None, verify=None)

        interpolated_auth = None
        if auth is not None:
            username, passwd = auth
            passwd = Interpolate(passwd)
            interpolated_auth = (username, passwd)

        self.sp = sp = HttpStatusPush("serv", auth=interpolated_auth, **kwargs)
        yield sp.setServiceParent(self.master)

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.master.stopService()
        config._errors = None

    @defer.inlineCallbacks
    def setupBuildResults(self, buildResults):
        self.insertTestData([buildResults], buildResults)
        build = yield self.master.data.get(("builds", 20))
        return build

    @defer.inlineCallbacks
    def test_basic(self):
        yield self.createReporter()
        self._http.expect("post", "", json=BuildLookAlike(complete=False))
        self._http.expect("post", "", json=BuildLookAlike(complete=True))
        build = yield self.setupBuildResults(SUCCESS)
        build['complete'] = False
        self.sp.buildStarted(("build", 20, "new"), build)
        build['complete'] = True
        self.sp.buildFinished(("build", 20, "finished"), build)

    @defer.inlineCallbacks
    def test_basic_noauth(self):
        yield self.createReporter(auth=None)
        self._http.expect("post", "", json=BuildLookAlike(complete=False))
        self._http.expect("post", "", json=BuildLookAlike(complete=True))
        build = yield self.setupBuildResults(SUCCESS)
        build['complete'] = False
        self.sp.buildStarted(("build", 20, "new"), build)
        build['complete'] = True
        self.sp.buildFinished(("build", 20, "finished"), build)

    @defer.inlineCallbacks
    def test_filtering(self):
        yield self.createReporter(builders=['foo'])
        build = yield self.setupBuildResults(SUCCESS)
        self.sp.buildFinished(("build", 20, "finished"), build)

    @defer.inlineCallbacks
    def test_filteringPass(self):
        yield self.createReporter(builders=['Builder0'])
        self._http.expect("post", "", json=BuildLookAlike())
        build = yield self.setupBuildResults(SUCCESS)
        self.sp.buildFinished(("build", 20, "finished"), build)

    @defer.inlineCallbacks
    def test_builderTypeCheck(self):
        yield self.createReporter(builders='Builder0')
        config._errors.addError.assert_any_call(
            "builders must be a list or None")

    @defer.inlineCallbacks
    def test_wantKwargsCheck(self):
        yield self.createReporter(builders='Builder0', wantProperties=True, wantSteps=True,
                                  wantPreviousBuild=True, wantLogs=True)
        self._http.expect("post", "", json=BuildLookAlike(
            keys=['steps', 'prev_build']))
        build = yield self.setupBuildResults(SUCCESS)
        build['complete'] = True
        self.sp.buildFinished(("build", 20, "finished"), build)

    @defer.inlineCallbacks
    def http2XX(self, code, content):
        yield self.createReporter()
        self._http.expect('post', '', code=code, content=content,
                          json=BuildLookAlike())
        build = yield self.setupBuildResults(SUCCESS)
        self.sp.buildStarted(('build', 20, 'finished'), build)

    @defer.inlineCallbacks
    def test_http200(self):
        yield self.http2XX(code=200, content="OK")

    @defer.inlineCallbacks
    def test_http201(self):  # e.g. GitHub returns 201
        yield self.http2XX(code=201, content="Created")

    @defer.inlineCallbacks
    def test_http202(self):
        yield self.http2XX(code=202, content="Accepted")
