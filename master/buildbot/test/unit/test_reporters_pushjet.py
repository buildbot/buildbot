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
from buildbot.reporters.pushjet import PushjetNotifier
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.fake import fakemaster
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.util import httpclientservice


class TestPushjetNotifier(ConfigErrorsMixin, unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self,
                                             wantData=True, wantDb=True, wantMq=True)

    def setupFakeHttp(self, base_url='https://api.pushjet.io'):
        return self.successResultOf(fakehttpclientservice.HTTPClientService.getFakeService(
            self.master, self, base_url))

    @defer.inlineCallbacks
    def setupPushjetNotifier(self, secret="1234", **kwargs):
        pn = PushjetNotifier(secret, **kwargs)
        yield pn.setServiceParent(self.master)
        yield pn.startService()
        defer.returnValue(pn)

    @defer.inlineCallbacks
    def test_sendMessage(self):
        _http = self.setupFakeHttp()
        pn = yield self.setupPushjetNotifier(levels={'passing': 2})
        _http.expect("post", "/message",
                     data={'secret': "1234", 'level': 2,
                           'message': "Test", 'title': "Tee"},
                     content_json={'status': 'ok'})
        n = yield pn.sendMessage(body="Test", subject="Tee", results=SUCCESS)
        j = yield n.json()
        self.assertEqual(j['status'], 'ok')

    @defer.inlineCallbacks
    def test_sendNotification(self):
        _http = self.setupFakeHttp('https://tests.io')
        pn = yield self.setupPushjetNotifier(base_url='https://tests.io')
        _http.expect("post", "/message",
                     data={'secret': "1234", 'message': "Test"},
                     content_json={'status': 'ok'})
        n = yield pn.sendNotification({'message': "Test"})
        j = yield n.json()
        self.assertEqual(j['status'], 'ok')

    @defer.inlineCallbacks
    def test_sendRealNotification(self):
        secret = os.environ.get('TEST_PUSHJET_SECRET')
        if secret is None:
            raise SkipTest("real pushjet test runs only if the variable "
                           "TEST_PUSHJET_SECRET is defined")
        _http = yield httpclientservice.HTTPClientService.getService(
            self.master, 'https://api.pushjet.io')
        yield _http.startService()
        pn = yield self.setupPushjetNotifier(secret=secret)
        n = yield pn.sendNotification({'message': "Buildbot Pushjet test passed!"})
        j = yield n.json()
        self.assertEqual(j['status'], 'ok')

        # Test with:
        # TEST_PUSHJET_SECRET=edcfaf21ab1bbad7b12bd7602447e6cb
        # https://api.pushjet.io/message?uuid=b8b8b8b8-0000-b8b8-0000-b8b8b8b8b8b8
