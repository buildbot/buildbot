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
from buildbot.reporters.pushjet import PushjetNotifier
from buildbot.test.fake import fakemaster
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.util import httpclientservice


class TestPushjetNotifier(ConfigErrorsMixin, TestReactorMixin, unittest.TestCase):
    def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True, wantMq=True)

    # returns a Deferred
    def setupFakeHttp(self, base_url='https://api.pushjet.io'):
        return fakehttpclientservice.HTTPClientService.getService(self.master, self, base_url)

    async def setupPushjetNotifier(self, secret: Optional[Interpolate] = None, **kwargs):
        if secret is None:
            secret = Interpolate("1234")
        pn = PushjetNotifier(secret, **kwargs)
        await pn.setServiceParent(self.master)
        await pn.startService()
        return pn

    async def test_sendMessage(self):
        _http = await self.setupFakeHttp()
        pn = await self.setupPushjetNotifier(levels={'passing': 2})
        _http.expect(
            "post",
            "/message",
            data={'secret': "1234", 'level': 2, 'message': "Test", 'title': "Tee"},
            content_json={'status': 'ok'},
        )

        n = await pn.sendMessage([{"body": "Test", "subject": "Tee", "results": SUCCESS}])

        j = await n.json()
        self.assertEqual(j['status'], 'ok')

    async def test_sendNotification(self):
        _http = await self.setupFakeHttp('https://tests.io')
        pn = await self.setupPushjetNotifier(base_url='https://tests.io')
        _http.expect(
            "post",
            "/message",
            data={'secret': "1234", 'message': "Test"},
            content_json={'status': 'ok'},
        )
        n = await pn.sendNotification({'message': "Test"})
        j = await n.json()
        self.assertEqual(j['status'], 'ok')

    async def test_sendRealNotification(self):
        secret = os.environ.get('TEST_PUSHJET_SECRET')
        if secret is None:
            raise SkipTest(
                "real pushjet test runs only if the variable TEST_PUSHJET_SECRET is defined"
            )
        _http = await httpclientservice.HTTPClientService.getService(
            self.master, 'https://api.pushjet.io'
        )
        await _http.startService()
        pn = await self.setupPushjetNotifier(secret=secret)
        n = await pn.sendNotification({'message': "Buildbot Pushjet test passed!"})
        j = await n.json()
        self.assertEqual(j['status'], 'ok')

        # Test with:
        # TEST_PUSHJET_SECRET=edcfaf21ab1bbad7b12bd7602447e6cb
        # https://api.pushjet.io/message?uuid=b8b8b8b8-0000-b8b8-0000-b8b8b8b8b8b8
