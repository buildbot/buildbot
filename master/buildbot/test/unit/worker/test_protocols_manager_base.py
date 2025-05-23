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
"""
Test clean shutdown functionality of the master
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from unittest import mock

from twisted.internet import defer
from twisted.trial import unittest
from typing_extensions import Self

from buildbot.worker.protocols.manager.base import BaseDispatcher
from buildbot.worker.protocols.manager.base import BaseManager

if TYPE_CHECKING:
    from unittest.mock import Mock

    from buildbot.util.twisted import InlineCallbacksType


class FakeMaster:
    initLock = defer.DeferredLock()

    def addService(self, svc: TestManagerClass) -> None:
        pass

    @property
    def master(self) -> Self:
        return self


class TestDispatcher(BaseDispatcher):
    def __init__(self, config_port: str | int) -> None:
        super().__init__(config_port=config_port)
        self.start_listening_count = 0
        self.stop_listening_count = 0

    def start_listening_port(self) -> Mock:
        def stopListening() -> None:
            self.stop_listening_count += 1

        self.start_listening_count += 1
        port = mock.Mock()
        port.stopListening = stopListening
        return port


class TestManagerClass(BaseManager):
    dispatcher_class = TestDispatcher


class TestBaseManager(unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.manager = TestManagerClass('test_base_manager')
        yield self.manager.setServiceParent(FakeMaster())

    def assert_equal_registration(
        self,
        result: dict[str, BaseDispatcher],
        expected: dict[str, dict[str, tuple[str, Any]]],
    ) -> None:
        result_users = {key: result[key].users for key in result}
        self.assertEqual(result_users, expected)

    def assert_start_stop_listening_counts(
        self,
        disp: BaseDispatcher,
        start_count: int,
        stop_count: int,
    ) -> None:
        assert isinstance(disp, TestDispatcher)
        self.assertEqual(disp.start_listening_count, start_count)
        self.assertEqual(disp.stop_listening_count, stop_count)

    @defer.inlineCallbacks
    def test_repr(self) -> InlineCallbacksType[None]:
        reg = yield self.manager.register('tcp:port', 'x', 'y', mock.Mock())
        self.assertEqual(
            repr(self.manager.dispatchers['tcp:port']), '<base.BaseDispatcher for x on tcp:port>'
        )
        self.assertEqual(repr(reg), '<base.Registration for x on tcp:port>')

    @defer.inlineCallbacks
    def test_register_before_start_service(self) -> InlineCallbacksType[None]:
        pf = mock.Mock()
        yield self.manager.register('tcp:port', 'user', 'pass', pf)

        self.assert_equal_registration(
            self.manager.dispatchers,
            {'tcp:port': {'user': ('pass', pf)}},
        )

        disp = self.manager.dispatchers['tcp:port']
        self.assert_start_stop_listening_counts(disp, 0, 0)
        self.assertEqual(len(self.manager.services), 1)

        yield self.manager.startService()
        self.assert_start_stop_listening_counts(disp, 1, 0)

        yield self.manager.stopService()
        self.assert_start_stop_listening_counts(disp, 1, 1)

    @defer.inlineCallbacks
    def test_same_registration_two_times(self) -> InlineCallbacksType[None]:
        yield self.manager.startService()
        pfactory = mock.Mock()
        yield self.manager.register('tcp:port', 'user', 'pass', pfactory)

        # one registration is ok
        self.assert_equal_registration(
            self.manager.dispatchers,
            {'tcp:port': {'user': ('pass', pfactory)}},
        )
        self.assertEqual(len(self.manager.services), 1)

        disp = self.manager.dispatchers['tcp:port']
        self.assert_start_stop_listening_counts(disp, 1, 0)

        # same user is not allowed to register
        with self.assertRaises(KeyError):
            yield self.manager.register('tcp:port', 'user', 'pass', pfactory)

        yield self.manager.stopService()
        self.assert_start_stop_listening_counts(disp, 1, 1)

    @defer.inlineCallbacks
    def test_register_unregister_register(self) -> InlineCallbacksType[None]:
        yield self.manager.startService()
        pfactory = mock.Mock()
        reg = yield self.manager.register('tcp:port', 'user', 'pass', pfactory)
        self.assert_equal_registration(
            self.manager.dispatchers, {'tcp:port': {'user': ('pass', pfactory)}}
        )

        disp = self.manager.dispatchers['tcp:port']
        self.assert_start_stop_listening_counts(disp, 1, 0)

        reg.unregister()
        self.assert_equal_registration(self.manager.dispatchers, {})

        # allow registering same user again
        pf = mock.Mock()
        yield self.manager.register('tcp:port', 'user', 'pass', pf)

        self.assert_equal_registration(
            self.manager.dispatchers, {'tcp:port': {'user': ('pass', pf)}}
        )

        yield self.manager.stopService()
        self.assert_start_stop_listening_counts(disp, 1, 1)

    @defer.inlineCallbacks
    def test_register_unregister_empty_disp_users(self) -> InlineCallbacksType[None]:
        yield self.manager.startService()
        pf = mock.Mock()
        reg = yield self.manager.register('tcp:port', 'user', 'pass', pf)
        self.assertEqual(len(self.manager.services), 1)

        expected = {'tcp:port': {'user': ('pass', pf)}}
        self.assert_equal_registration(self.manager.dispatchers, expected)

        disp = self.manager.dispatchers['tcp:port']

        reg.unregister()
        self.assert_equal_registration(self.manager.dispatchers, {})
        self.assertEqual(reg.username, None)
        self.assertEqual(len(self.manager.services), 0)

        yield self.manager.stopService()
        self.assert_start_stop_listening_counts(disp, 1, 1)

    @defer.inlineCallbacks
    def test_different_ports_same_users(self) -> InlineCallbacksType[None]:
        yield self.manager.startService()
        # same registrations on different ports is ok
        pf = mock.Mock()
        reg1 = yield self.manager.register('tcp:port1', "user", "pass", pf)
        reg2 = yield self.manager.register('tcp:port2', "user", "pass", pf)
        reg3 = yield self.manager.register('tcp:port3', "user", "pass", pf)

        disp1 = self.manager.dispatchers['tcp:port1']
        self.assert_start_stop_listening_counts(disp1, 1, 0)

        disp2 = self.manager.dispatchers['tcp:port2']
        self.assert_start_stop_listening_counts(disp2, 1, 0)

        disp3 = self.manager.dispatchers['tcp:port3']
        self.assert_start_stop_listening_counts(disp3, 1, 0)

        self.assert_equal_registration(
            self.manager.dispatchers,
            {
                'tcp:port1': {'user': ('pass', pf)},
                'tcp:port2': {'user': ('pass', pf)},
                'tcp:port3': {'user': ('pass', pf)},
            },
        )
        self.assertEqual(len(self.manager.services), 3)

        yield reg1.unregister()
        self.assert_equal_registration(
            self.manager.dispatchers,
            {'tcp:port2': {'user': ('pass', pf)}, 'tcp:port3': {'user': ('pass', pf)}},
        )
        self.assertEqual(reg1.username, None)
        self.assertEqual(len(self.manager.services), 2)
        self.assert_start_stop_listening_counts(disp1, 1, 1)

        yield reg2.unregister()
        self.assert_equal_registration(
            self.manager.dispatchers,
            {'tcp:port3': {'user': ('pass', pf)}},
        )
        self.assertEqual(reg2.username, None)
        self.assertEqual(len(self.manager.services), 1)
        self.assert_start_stop_listening_counts(disp2, 1, 1)

        yield reg3.unregister()
        self.assert_equal_registration(self.manager.dispatchers, {})
        self.assertEqual(reg3.username, None)
        self.assertEqual(len(self.manager.services), 0)
        self.assert_start_stop_listening_counts(disp3, 1, 1)

        yield self.manager.stopService()
        self.assert_start_stop_listening_counts(disp1, 1, 1)
        self.assert_start_stop_listening_counts(disp2, 1, 1)
        self.assert_start_stop_listening_counts(disp3, 1, 1)

    @defer.inlineCallbacks
    def test_same_port_different_users(self) -> InlineCallbacksType[None]:
        yield self.manager.startService()
        pf1, pf2, pf3 = (mock.Mock(), mock.Mock(), mock.Mock())
        reg1 = yield self.manager.register('tcp:port', 'user1', 'pass1', pf1)
        reg2 = yield self.manager.register('tcp:port', 'user2', 'pass2', pf2)
        reg3 = yield self.manager.register('tcp:port', 'user3', 'pass3', pf3)
        disp = self.manager.dispatchers['tcp:port']

        self.assertEqual(len(self.manager.services), 1)
        self.assert_equal_registration(
            self.manager.dispatchers,
            {
                'tcp:port': {
                    'user1': ('pass1', pf1),
                    'user2': ('pass2', pf2),
                    'user3': ('pass3', pf3),
                }
            },
        )
        self.assertEqual(len(self.manager.services), 1)

        yield reg1.unregister()
        self.assert_equal_registration(
            self.manager.dispatchers,
            {'tcp:port': {'user2': ('pass2', pf2), 'user3': ('pass3', pf3)}},
        )
        self.assertEqual(reg1.username, None)
        self.assertEqual(len(self.manager.services), 1)

        yield reg2.unregister()
        self.assert_equal_registration(
            self.manager.dispatchers, {'tcp:port': {'user3': ('pass3', pf3)}}
        )
        self.assertEqual(reg2.username, None)
        self.assertEqual(len(self.manager.services), 1)

        yield reg3.unregister()
        self.assert_equal_registration(self.manager.dispatchers, {})
        self.assertEqual(reg3.username, None)
        self.assertEqual(len(self.manager.services), 0)

        yield self.manager.stopService()
        self.assert_start_stop_listening_counts(disp, 1, 1)
