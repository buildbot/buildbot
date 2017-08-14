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

import os
from unittest import SkipTest

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process.results import SUCCESS
from buildbot.reporters.pushover import PushoverNotifier
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.fake import fakemaster
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.util import httpclientservice


class TestPushoverNotifier(ConfigErrorsMixin, unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self,
                                             wantData=True, wantDb=True, wantMq=True)

    def setupFakeHttp(self):
        return self.successResultOf(fakehttpclientservice.HTTPClientService.getFakeService(
            self.master, self, 'https://api.pushover.net'))

    @defer.inlineCallbacks
    def setupPushoverNotifier(self, user_key="1234", api_token="abcd", **kwargs):
        pn = PushoverNotifier(user_key, api_token, **kwargs)
        yield pn.setServiceParent(self.master)
        yield pn.startService()
        defer.returnValue(pn)

    @defer.inlineCallbacks
    def test_sendMessage(self):
        _http = self.setupFakeHttp()
        pn = yield self.setupPushoverNotifier(priorities={'passing': 2})
        _http.expect("post", "/1/messages.json",
                     params={'user': "1234", 'token': "abcd",
                             'message': "Test", 'title': "Tee", 'priority': 2},
                     content_json={'status': 1, 'request': '98765'})
        n = yield pn.sendMessage(body="Test", subject="Tee", results=SUCCESS)
        j = yield n.json()
        self.assertEqual(j['status'], 1)
        self.assertEqual(j['request'], '98765')

    @defer.inlineCallbacks
    def test_sendNotification(self):
        _http = self.setupFakeHttp()
        pn = yield self.setupPushoverNotifier(otherParams={'sound': "silent"})
        _http.expect("post", "/1/messages.json",
                     params={'user': "1234", 'token': "abcd",
                             'sound': "silent", 'message': "Test"},
                     content_json={'status': 1, 'request': '98765'})
        n = yield pn.sendNotification({'message': "Test"})
        j = yield n.json()
        self.assertEqual(j['status'], 1)
        self.assertEqual(j['request'], '98765')

    @defer.inlineCallbacks
    def test_sendRealNotification(self):
        creds = os.environ.get('TEST_PUSHOVER_CREDENTIALS')
        if creds is None:
            raise SkipTest("real pushover test runs only if the variable "
                           "TEST_PUSHOVER_CREDENTIALS is defined")
        user, token = creds.split(':')
        _http = yield httpclientservice.HTTPClientService.getService(
            self.master, 'https://api.pushover.net')
        yield _http.startService()
        pn = yield self.setupPushoverNotifier(user_key=user, api_token=token)
        n = yield pn.sendNotification({'message': "Buildbot Pushover test passed!"})
        j = yield n.json()
        self.assertEqual(j['status'], 1)
