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


import os
from typing import Optional
from unittest import SkipTest

from twisted.trial import unittest

from buildbot.process.properties import Interpolate
from buildbot.process.results import SUCCESS
from buildbot.reporters.pushover import PushoverNotifier
from buildbot.test.fake import fakemaster
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.util import httpclientservice


class TestPushoverNotifier(ConfigErrorsMixin, TestReactorMixin, unittest.TestCase):
    def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True, wantMq=True)

    # returns a Deferred
    def setupFakeHttp(self):
        return fakehttpclientservice.HTTPClientService.getService(
            self.master, self, 'https://api.pushover.net'
        )

    async def setupPushoverNotifier(
        self, user_key="1234", api_token: Optional[Interpolate] = None, **kwargs
    ):
        if api_token is None:
            api_token = Interpolate("abcd")
        pn = PushoverNotifier(user_key, api_token, **kwargs)
        await pn.setServiceParent(self.master)
        await pn.startService()
        return pn

    async def test_sendMessage(self):
        _http = await self.setupFakeHttp()
        pn = await self.setupPushoverNotifier(priorities={'passing': 2})
        _http.expect(
            "post",
            "/1/messages.json",
            params={
                'user': "1234",
                'token': "abcd",
                'message': "Test",
                'title': "Tee",
                'priority': 2,
            },
            content_json={'status': 1, 'request': '98765'},
        )

        n = await pn.sendMessage([{"body": "Test", "subject": "Tee", "results": SUCCESS}])

        j = await n.json()
        self.assertEqual(j['status'], 1)
        self.assertEqual(j['request'], '98765')

    async def test_sendNotification(self):
        _http = await self.setupFakeHttp()
        pn = await self.setupPushoverNotifier(otherParams={'sound': "silent"})
        _http.expect(
            "post",
            "/1/messages.json",
            params={'user': "1234", 'token': "abcd", 'sound': "silent", 'message': "Test"},
            content_json={'status': 1, 'request': '98765'},
        )
        n = await pn.sendNotification({'message': "Test"})
        j = await n.json()
        self.assertEqual(j['status'], 1)
        self.assertEqual(j['request'], '98765')

    async def test_sendRealNotification(self):
        creds = os.environ.get('TEST_PUSHOVER_CREDENTIALS')
        if creds is None:
            raise SkipTest(
                "real pushover test runs only if the variable "
                "TEST_PUSHOVER_CREDENTIALS is defined"
            )
        user, token = creds.split(':')
        _http = httpclientservice.HTTPSession(self.master.httpservice, 'https://api.pushover.net')
        pn = await self.setupPushoverNotifier(user_key=user, api_token=token)
        n = await pn.sendNotification({'message': "Buildbot Pushover test passed!"})
        j = await n.json()
        self.assertEqual(j['status'], 1)
