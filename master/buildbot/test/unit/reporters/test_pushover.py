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

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from typing import Any
from unittest import SkipTest

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process.properties import Interpolate
from buildbot.process.results import SUCCESS
from buildbot.reporters.pushover import PushoverNotifier
from buildbot.test.fake import fakemaster
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.util import httpclientservice

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class TestPushoverNotifier(ConfigErrorsMixin, TestReactorMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantData=True, wantDb=True, wantMq=True)

    # returns a Deferred
    def setupFakeHttp(self) -> Any:
        return fakehttpclientservice.HTTPClientService.getService(
            self.master, self, 'https://api.pushover.net'
        )

    @defer.inlineCallbacks
    def setupPushoverNotifier(
        self, user_key: str = "1234", api_token: Interpolate | None = None, **kwargs: Any
    ) -> InlineCallbacksType[PushoverNotifier]:
        if api_token is None:
            api_token = Interpolate("abcd")
        pn = PushoverNotifier(user_key, api_token, **kwargs)
        yield pn.setServiceParent(self.master)
        yield pn.startService()
        return pn

    @defer.inlineCallbacks
    def test_sendMessage(self) -> InlineCallbacksType[None]:
        _http = yield self.setupFakeHttp()
        pn = yield self.setupPushoverNotifier(priorities={'passing': 2})
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

        n = yield pn.sendMessage([{"body": "Test", "subject": "Tee", "results": SUCCESS}])

        j = yield n.json()
        self.assertEqual(j['status'], 1)
        self.assertEqual(j['request'], '98765')

    @defer.inlineCallbacks
    def test_sendNotification(self) -> InlineCallbacksType[None]:
        _http = yield self.setupFakeHttp()
        pn = yield self.setupPushoverNotifier(otherParams={'sound': "silent"})
        _http.expect(
            "post",
            "/1/messages.json",
            params={'user': "1234", 'token': "abcd", 'sound': "silent", 'message': "Test"},
            content_json={'status': 1, 'request': '98765'},
        )
        n = yield pn.sendNotification({'message': "Test"})
        j = yield n.json()
        self.assertEqual(j['status'], 1)
        self.assertEqual(j['request'], '98765')

    @defer.inlineCallbacks
    def test_sendRealNotification(self) -> InlineCallbacksType[None]:
        creds = os.environ.get('TEST_PUSHOVER_CREDENTIALS')
        if creds is None:
            raise SkipTest(
                "real pushover test runs only if the variable TEST_PUSHOVER_CREDENTIALS is defined"
            )
        user, token = creds.split(':')
        _http = httpclientservice.HTTPSession(self.master.httpservice, 'https://api.pushover.net')
        pn = yield self.setupPushoverNotifier(user_key=user, api_token=token)  # type: ignore[arg-type]
        n = yield pn.sendNotification({'message': "Buildbot Pushover test passed!"})
        j = yield n.json()
        self.assertEqual(j['status'], 1)
