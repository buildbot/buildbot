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
from buildbot.process.results import SUCCESS
from buildbot.reporters.hipchat import HOSTED_BASE_URL
from buildbot.reporters.hipchat import HipChatStatusPush
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.fake import fakemaster
from buildbot.test.util.logging import LoggingMixin
from buildbot.test.util.reporter import ReporterTestMixin


class TestHipchatStatusPush(unittest.TestCase, ReporterTestMixin, LoggingMixin):

    def setUp(self):
        # ignore config error if txrequests is not installed
        self.patch(config, '_errors', Mock())
        self.master = fakemaster.make_master(
            testcase=self, wantData=True, wantDb=True, wantMq=True)

    @defer.inlineCallbacks
    def tearDown(self):
        if self.master.running:
            yield self.master.stopService()

    @defer.inlineCallbacks
    def createReporter(self, **kwargs):
        kwargs['auth_token'] = kwargs.get('auth_token', 'abc')
        self.sp = HipChatStatusPush(**kwargs)
        self._http = yield fakehttpclientservice.HTTPClientService.getFakeService(
            self.master, self,
            kwargs.get('endpoint', HOSTED_BASE_URL),
            debug=None, verify=None)
        yield self.sp.setServiceParent(self.master)
        yield self.master.startService()

    @defer.inlineCallbacks
    def setupBuildResults(self):
        self.insertTestData([SUCCESS], SUCCESS)
        build = yield self.master.data.get(("builds", 20))
        defer.returnValue(build)

    @defer.inlineCallbacks
    def test_authtokenTypeCheck(self):
        yield self.createReporter(auth_token=2)
        config._errors.addError.assert_any_call('auth_token must be a string')

    def test_endpointTypeCheck(self):
        HipChatStatusPush(auth_token="2", endpoint=2)
        config._errors.addError.assert_any_call('endpoint must be a string')

    @defer.inlineCallbacks
    def test_builderRoomMapTypeCheck(self):
        yield self.createReporter(builder_room_map=2)
        config._errors.addError.assert_any_call(
            'builder_room_map must be a dict')

    @defer.inlineCallbacks
    def test_builderUserMapTypeCheck(self):
        yield self.createReporter(builder_user_map=2)
        config._errors.addError.assert_any_call(
            'builder_user_map must be a dict')

    @defer.inlineCallbacks
    def test_build_started(self):
        yield self.createReporter(builder_user_map={'Builder0': '123'})
        build = yield self.setupBuildResults()
        self._http.expect(
            'post',
            '/v2/user/123/message',
            params=dict(auth_token='abc'),
            json={'message':
                  'Buildbot started build Builder0 here: http://localhost:8080/#builders/79/builds/0'})
        self.sp.buildStarted(('build', 20, 'new'), build)

    @defer.inlineCallbacks
    def test_build_finished(self):
        yield self.createReporter(builder_room_map={'Builder0': '123'})
        build = yield self.setupBuildResults()
        self._http.expect(
            'post',
            '/v2/room/123/notification',
            params=dict(auth_token='abc'),
            json={'message':
                  'Buildbot finished build Builder0 with result success '
                  'here: http://localhost:8080/#builders/79/builds/0'})
        self.sp.buildFinished(('build', 20, 'finished'), build)

    @defer.inlineCallbacks
    def test_inject_extra_params(self):
        yield self.createReporter(builder_room_map={'Builder0': '123'})
        self.sp.getExtraParams = Mock()
        self.sp.getExtraParams.return_value = {'format': 'html'}
        build = yield self.setupBuildResults()
        self._http.expect(
            'post',
            '/v2/room/123/notification',
            params=dict(auth_token='abc'),
            json={'message': 'Buildbot finished build Builder0 with result success '
                  'here: http://localhost:8080/#builders/79/builds/0',
                  'format': 'html'})

        self.sp.buildFinished(('build', 20, 'finished'), build)

    @defer.inlineCallbacks
    def test_no_message_sent_empty_message(self):
        yield self.createReporter()
        build = yield self.setupBuildResults()
        self.sp.send(build, 'unknown')

    @defer.inlineCallbacks
    def test_no_message_sent_without_id(self):
        yield self.createReporter()
        build = yield self.setupBuildResults()
        self.sp.send(build, 'new')

    @defer.inlineCallbacks
    def test_private_message_sent_with_user_id(self):
        token = 'tok'
        endpoint = 'example.com'
        yield self.createReporter(auth_token=token, endpoint=endpoint)
        self.sp.getBuildDetailsAndSendMessage = Mock()
        message = {'message': 'hi'}
        postData = dict(message)
        postData.update({'id_or_email': '123'})
        self.sp.getBuildDetailsAndSendMessage.return_value = postData
        self._http.expect(
            'post',
            '/v2/user/123/message',
            params=dict(auth_token=token),
            json=message)
        self.sp.send({}, 'test')

    @defer.inlineCallbacks
    def test_room_message_sent_with_room_id(self):
        token = 'tok'
        endpoint = 'example.com'
        yield self.createReporter(auth_token=token, endpoint=endpoint)
        self.sp.getBuildDetailsAndSendMessage = Mock()
        message = {'message': 'hi'}
        postData = dict(message)
        postData.update({'room_id_or_name': '123'})
        self.sp.getBuildDetailsAndSendMessage.return_value = postData
        self._http.expect(
            'post',
            '/v2/room/123/notification',
            params=dict(auth_token=token),
            json=message)
        self.sp.send({}, 'test')

    @defer.inlineCallbacks
    def test_private_and_room_message_sent_with_both_ids(self):
        token = 'tok'
        endpoint = 'example.com'
        yield self.createReporter(auth_token=token, endpoint=endpoint)
        self.sp.getBuildDetailsAndSendMessage = Mock()
        message = {'message': 'hi'}
        postData = dict(message)
        postData.update({'room_id_or_name': '123', 'id_or_email': '456'})
        self.sp.getBuildDetailsAndSendMessage.return_value = postData
        self._http.expect(
            'post',
            '/v2/user/456/message',
            params=dict(auth_token=token),
            json=message)
        self._http.expect(
            'post',
            '/v2/room/123/notification',
            params=dict(auth_token=token),
            json=message)
        self.sp.send({}, 'test')

    @defer.inlineCallbacks
    def test_postData_values_passed_through(self):
        token = 'tok'
        endpoint = 'example.com'
        yield self.createReporter(auth_token=token, endpoint=endpoint)
        self.sp.getBuildDetailsAndSendMessage = Mock()
        message = {'message': 'hi', 'notify': True, 'message_format': 'html'}
        postData = dict(message)
        postData.update({'id_or_email': '123'})
        self.sp.getBuildDetailsAndSendMessage.return_value = postData
        self._http.expect(
            'post',
            '/v2/user/123/message',
            params=dict(auth_token=token),
            json=message)
        self.sp.send({}, 'test')

    @defer.inlineCallbacks
    def test_postData_error(self):
        token = 'tok'
        endpoint = 'example.com'
        yield self.createReporter(auth_token=token, endpoint=endpoint)
        self.sp.getBuildDetailsAndSendMessage = Mock()
        message = {'message': 'hi', 'notify': True, 'message_format': 'html'}
        postData = dict(message)
        postData.update({'id_or_email': '123'})
        self.sp.getBuildDetailsAndSendMessage.return_value = postData
        self._http.expect(
            'post',
            '/v2/user/123/message',
            params=dict(auth_token=token),
            json=message, code=404,
            content_json={
                "error_description": "This user is unknown to us",
                "error": "invalid_user"})
        self.setUpLogging()
        self.sp.send({}, 'test')
        self.assertLogged('404: unable to upload status')
