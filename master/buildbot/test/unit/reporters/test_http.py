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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process.properties import Interpolate
from buildbot.process.results import SUCCESS
from buildbot.reporters.http import HttpStatusPush
from buildbot.reporters.http import HttpStatusPushBase
from buildbot.test.fake import fakemaster
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.test.util.misc import BuildDictLookAlike
from buildbot.test.util.misc import TestReactorMixin
from buildbot.test.util.reporter import ReporterTestMixin
from buildbot.test.util.warnings import assertProducesWarnings
from buildbot.warnings import DeprecatedApiWarning


class TestHttpStatusPush(TestReactorMixin, unittest.TestCase, ReporterTestMixin, ConfigErrorsMixin):

    @defer.inlineCallbacks
    def setUp(self):
        self.setUpTestReactor()
        self.setup_reporter_test()
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True,
                                             wantMq=True)
        yield self.master.startService()

    @defer.inlineCallbacks
    def createReporter(self, auth=("username", "passwd"), headers=None, **kwargs):
        self._http = yield fakehttpclientservice.HTTPClientService.getService(
            self.master, self,
            "serv", auth=auth, headers=headers,
            debug=None, verify=None)

        interpolated_auth = None
        if auth is not None:
            username, passwd = auth
            passwd = Interpolate(passwd)
            interpolated_auth = (username, passwd)

        self.sp = HttpStatusPush("serv", auth=interpolated_auth, headers=headers, **kwargs)
        yield self.sp.setServiceParent(self.master)

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.master.stopService()

    @defer.inlineCallbacks
    def test_basic(self):
        yield self.createReporter()
        self._http.expect("post", "", json=BuildDictLookAlike(complete=False))
        self._http.expect("post", "", json=BuildDictLookAlike(complete=True))
        build = yield self.insert_build_new()
        yield self.sp._got_event(('builds', 20, 'new'), build)
        build['complete'] = True
        build['results'] = SUCCESS
        yield self.sp._got_event(('builds', 20, 'finished'), build)

    @defer.inlineCallbacks
    def test_basic_noauth(self):
        yield self.createReporter(auth=None)
        self._http.expect("post", "", json=BuildDictLookAlike(complete=False))
        self._http.expect("post", "", json=BuildDictLookAlike(complete=True))
        build = yield self.insert_build_new()
        yield self.sp._got_event(('builds', 20, 'new'), build)
        build['complete'] = True
        build['results'] = SUCCESS
        yield self.sp._got_event(('builds', 20, 'finished'), build)

    @defer.inlineCallbacks
    def test_header(self):
        yield self.createReporter(headers={'Custom header': 'On'})
        self._http.expect("post", "", json=BuildDictLookAlike())
        build = yield self.insert_build_finished(SUCCESS)
        yield self.sp._got_event(('builds', 20, 'finished'), build)

    @defer.inlineCallbacks
    def test_filtering(self):
        with assertProducesWarnings(DeprecatedApiWarning, message_pattern='Use generators instead'):
            yield self.createReporter(builders=['foo'])
        build = yield self.insert_build_finished(SUCCESS)
        yield self.sp._got_event(('builds', 20, 'finished'), build)

    @defer.inlineCallbacks
    def test_filteringPass(self):
        with assertProducesWarnings(DeprecatedApiWarning, message_pattern='Use generators instead'):
            yield self.createReporter(builders=['Builder0'])
        self._http.expect("post", "", json=BuildDictLookAlike())
        build = yield self.insert_build_finished(SUCCESS)
        yield self.sp._got_event(('builds', 20, 'finished'), build)

    @defer.inlineCallbacks
    def test_builderTypeCheck(self):
        with assertProducesWarnings(DeprecatedApiWarning, message_pattern='Use generators instead'):
            with self.assertRaisesConfigError("builders must be a list or None"):
                yield self.createReporter(builders='Builder0')

    @defer.inlineCallbacks
    def test_wantKwargsCheck(self):
        with assertProducesWarnings(DeprecatedApiWarning, message_pattern='Use generators instead'):
            yield self.createReporter(builders=['Builder0'], wantProperties=True, wantSteps=True,
                                      wantPreviousBuild=True, wantLogs=True)
        self._http.expect("post", "", json=BuildDictLookAlike(extra_keys=['steps', 'prev_build']))
        build = yield self.insert_build_finished(SUCCESS)
        yield self.sp._got_event(('builds', 20, 'finished'), build)

    @defer.inlineCallbacks
    def http2XX(self, code, content):
        yield self.createReporter()
        self._http.expect('post', '', code=code, content=content,
                          json=BuildDictLookAlike())
        build = yield self.insert_build_finished(SUCCESS)
        yield self.sp._got_event(('builds', 20, 'finished'), build)

    @defer.inlineCallbacks
    def test_http200(self):
        yield self.http2XX(code=200, content="OK")

    @defer.inlineCallbacks
    def test_http201(self):  # e.g. GitHub returns 201
        yield self.http2XX(code=201, content="Created")

    @defer.inlineCallbacks
    def test_http202(self):
        yield self.http2XX(code=202, content="Accepted")


class HttpStatusPushOverrideSend(HttpStatusPush):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.send_called_count = 0

    @defer.inlineCallbacks
    def send(self, build):
        self.send_called_count += 1
        yield super().send(build)


class TestHttpStatusPushDeprecatedSend(TestReactorMixin, unittest.TestCase, ReporterTestMixin):

    @defer.inlineCallbacks
    def setUp(self):
        self.setUpTestReactor()
        self.setup_reporter_test()
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True,
                                             wantMq=True)
        yield self.master.startService()

    @defer.inlineCallbacks
    def createReporter(self, auth=("username", "passwd"), **kwargs):
        self._http = yield fakehttpclientservice.HTTPClientService.getService(
            self.master, self,
            "serv", auth=auth, headers=None,
            debug=None, verify=None)

        interpolated_auth = None
        if auth is not None:
            username, passwd = auth
            passwd = Interpolate(passwd)
            interpolated_auth = (username, passwd)

        self.sp = HttpStatusPushOverrideSend("serv", auth=interpolated_auth, **kwargs)
        yield self.sp.setServiceParent(self.master)

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.master.stopService()

    @defer.inlineCallbacks
    def test_basic(self):
        yield self.createReporter()
        self._http.expect("post", "", json=BuildDictLookAlike(complete=False))
        self._http.expect("post", "", json=BuildDictLookAlike(complete=True))

        build = yield self.insert_build_new()
        with assertProducesWarnings(DeprecatedApiWarning,
                                    message_pattern='send\\(\\) in reporters has been deprecated'):
            yield self.sp._got_event(('builds', 20, 'new'), build)

        build['complete'] = True
        build['results'] = SUCCESS

        with assertProducesWarnings(DeprecatedApiWarning,
                                    message_pattern='send\\(\\) in reporters has been deprecated'):
            yield self.sp._got_event(('builds', 20, 'finished'), build)
        self.assertEqual(self.sp.send_called_count, 2)


class HttpStatusPushBaseOverrideSend(HttpStatusPushBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.send_called_count = 0

    def send(self, build):
        self.send_called_count += 1


class TestHttpStatusPushBaseDeprecatedSend(TestReactorMixin, unittest.TestCase, ReporterTestMixin):

    @defer.inlineCallbacks
    def setUp(self):
        self.setUpTestReactor()
        self.setup_reporter_test()
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True,
                                             wantMq=True)
        yield self.master.startService()

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.master.stopService()

    @defer.inlineCallbacks
    def test_old_args(self):
        with assertProducesWarnings(DeprecatedApiWarning,
                                    message_pattern='have been deprecated'):
            self.sp = HttpStatusPushBaseOverrideSend(wantSteps=True)
        yield self.sp.setServiceParent(self.master)

        build = yield self.insert_build_new()
        with assertProducesWarnings(DeprecatedApiWarning,
                                    message_pattern='send\\(\\) in reporters has been deprecated'):
            yield self.sp._got_event(('builds', 20, 'new'), build)

    @defer.inlineCallbacks
    def test_override_send(self):
        self.sp = HttpStatusPushBaseOverrideSend()
        yield self.sp.setServiceParent(self.master)

        build = yield self.insert_build_new()
        with assertProducesWarnings(DeprecatedApiWarning,
                                    message_pattern='send\\(\\) in reporters has been deprecated'):
            yield self.sp._got_event(('builds', 20, 'new'), build)

        build['complete'] = True
        build['results'] = SUCCESS

        with assertProducesWarnings(DeprecatedApiWarning,
                                    message_pattern='send\\(\\) in reporters has been deprecated'):
            yield self.sp._got_event(('builds', 20, 'finished'), build)
        self.assertEqual(self.sp.send_called_count, 2)
