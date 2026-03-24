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

from typing import TYPE_CHECKING
from typing import Any
from typing import Callable
from unittest import mock

from parameterized import parameterized
from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.util import service
from buildbot.wamp import connector

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class FakeConfig:
    def __init__(self, mq_dict: dict) -> None:
        self.mq = mq_dict


class FakeService(service.AsyncMultiService):
    name: str | None = "fakeWampService"  # type: ignore[assignment]
    # Fake wamp service
    # just call the maker on demand by the test

    def __init__(
        self,
        url: str,
        realm: str,
        make: Callable[..., Any],
        extra: object = None,
        debug: bool = False,
        debug_wamp: bool = False,
        debug_app: bool = False,
    ) -> None:
        super().__init__()
        self.make = make
        self.extra = extra

    def gotConnection(self) -> None:
        self.make(None)
        r = self.make(self)
        r.publish = mock.Mock(spec=r.publish)
        r.register = mock.Mock(spec=r.register)
        r.subscribe = mock.Mock(spec=r.subscribe)
        r.onJoin(None)


class TestedWampConnector(connector.WampConnector):
    serviceClass = FakeService  # type: ignore[assignment]


class WampConnector(TestReactorMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        master = yield fakemaster.make_master(self)
        self.connector = TestedWampConnector()

        config = FakeConfig({'type': 'wamp', 'router_url': "wss://foo", 'realm': "bb"})

        yield self.connector.setServiceParent(master)
        yield master.startService()
        yield self.connector.reconfigServiceWithBuildbotConfig(config)

    @defer.inlineCallbacks
    def test_reconfig_same_config(self) -> InlineCallbacksType[None]:
        config = FakeConfig({'type': 'wamp', 'router_url': "wss://foo", 'realm': "bb"})
        yield self.connector.reconfigServiceWithBuildbotConfig(config)

    @parameterized.expand([
        ('type', 'simple'),
        ('router_url', 'wss://other-foo'),
        ('realm', 'bb-other'),
        ('wamp_debug_level', 'info'),
    ])
    @defer.inlineCallbacks
    def test_reconfig_does_not_allow_config_change(
        self, attr_name: str, attr_value: str
    ) -> InlineCallbacksType[None]:
        mq_dict = {'type': 'wamp', 'router_url': "wss://foo", 'realm': "bb"}
        mq_dict[attr_name] = attr_value
        with self.assertRaises(
            ValueError, msg="Cannot use different wamp settings when reconfiguring"
        ):
            yield self.connector.reconfigServiceWithBuildbotConfig(FakeConfig(mq_dict))

    @defer.inlineCallbacks
    def test_startup(self) -> InlineCallbacksType[None]:
        d = self.connector.getService()
        self.connector.app.gotConnection()  # type: ignore[union-attr]
        yield d
        # 824 is the hardcoded masterid of fakemaster
        self.connector.service.publish.assert_called_with("org.buildbot.824.connected")  # type: ignore[union-attr]

    @defer.inlineCallbacks
    def test_subscribe(self) -> InlineCallbacksType[None]:
        d = self.connector.subscribe('callback', 'topic', 'options')
        self.connector.app.gotConnection()  # type: ignore[union-attr]
        yield d
        self.connector.service.subscribe.assert_called_with('callback', 'topic', 'options')  # type: ignore[union-attr]

    @defer.inlineCallbacks
    def test_publish(self) -> InlineCallbacksType[None]:
        d = self.connector.publish('topic', 'data', 'options')
        self.connector.app.gotConnection()  # type: ignore[union-attr]
        yield d
        self.connector.service.publish.assert_called_with('topic', 'data', options='options')  # type: ignore[union-attr]

    @defer.inlineCallbacks
    def test_OnLeave(self) -> InlineCallbacksType[None]:
        d = self.connector.getService()
        self.connector.app.gotConnection()  # type: ignore[union-attr]
        yield d
        self.assertTrue(self.connector.master.running)
        self.connector.service.onLeave(None)  # type: ignore[union-attr, arg-type]
        self.assertFalse(self.connector.master.running)
