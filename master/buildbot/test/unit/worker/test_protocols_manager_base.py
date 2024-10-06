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

from unittest import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.worker.protocols.manager.base import BaseDispatcher
from buildbot.worker.protocols.manager.base import BaseManager


class FakeMaster:
    initLock = defer.DeferredLock()

    def addService(self, svc):
        pass

    @property
    def master(self):
        return self


class TestDispatcher(BaseDispatcher):
    def __init__(self, config_portstr, portstr):
        super().__init__(portstr)
        self.start_listening_count = 0
        self.stop_listening_count = 0

    def start_listening_port(self):
        def stopListening():
            self.stop_listening_count += 1

        self.start_listening_count += 1
        port = mock.Mock()
        port.stopListening = stopListening
        return port


class TestPort:
    def __init__(self, test):
        self.test = test

    def stopListening(self):
        self.test.stop_listening_count += 1


class TestManagerClass(BaseManager):
    dispatcher_class = TestDispatcher


class TestBaseManager(unittest.TestCase):
    async def setUp(self):
        self.manager = TestManagerClass('test_base_manager')
        await self.manager.setServiceParent(FakeMaster())

    def assert_equal_registration(self, result, expected):
        result_users = {key: result[key].users for key in result}
        self.assertEqual(result_users, expected)

    def assert_start_stop_listening_counts(self, disp, start_count, stop_count):
        self.assertEqual(disp.start_listening_count, start_count)
        self.assertEqual(disp.stop_listening_count, stop_count)

    async def test_repr(self):
        reg = await self.manager.register('tcp:port', 'x', 'y', 'pf')
        self.assertEqual(
            repr(self.manager.dispatchers['tcp:port']), '<base.BaseDispatcher for x on tcp:port>'
        )
        self.assertEqual(repr(reg), '<base.Registration for x on tcp:port>')

    async def test_register_before_start_service(self):
        await self.manager.register('tcp:port', 'user', 'pass', 'pf')

        self.assert_equal_registration(
            self.manager.dispatchers, {'tcp:port': {'user': ('pass', 'pf')}}
        )

        disp = self.manager.dispatchers['tcp:port']
        self.assert_start_stop_listening_counts(disp, 0, 0)
        self.assertEqual(len(self.manager.services), 1)

        await self.manager.startService()
        self.assert_start_stop_listening_counts(disp, 1, 0)

        await self.manager.stopService()
        self.assert_start_stop_listening_counts(disp, 1, 1)

    async def test_same_registration_two_times(self):
        await self.manager.startService()
        await self.manager.register('tcp:port', 'user', 'pass', 'pf')

        # one registration is ok
        self.assert_equal_registration(
            self.manager.dispatchers, {'tcp:port': {'user': ('pass', 'pf')}}
        )
        self.assertEqual(len(self.manager.services), 1)

        disp = self.manager.dispatchers['tcp:port']
        self.assert_start_stop_listening_counts(disp, 1, 0)

        # same user is not allowed to register
        with self.assertRaises(KeyError):
            await self.manager.register('tcp:port', 'user', 'pass', 'pf')

        await self.manager.stopService()
        self.assert_start_stop_listening_counts(disp, 1, 1)

    async def test_register_unregister_register(self):
        await self.manager.startService()
        reg = await self.manager.register('tcp:port', 'user', 'pass', 'pf')
        self.assert_equal_registration(
            self.manager.dispatchers, {'tcp:port': {'user': ('pass', 'pf')}}
        )

        disp = self.manager.dispatchers['tcp:port']
        self.assert_start_stop_listening_counts(disp, 1, 0)

        reg.unregister()
        self.assert_equal_registration(self.manager.dispatchers, {})

        # allow registering same user again
        await self.manager.register('tcp:port', 'user', 'pass', 'pf')

        self.assert_equal_registration(
            self.manager.dispatchers, {'tcp:port': {'user': ('pass', 'pf')}}
        )

        await self.manager.stopService()
        self.assert_start_stop_listening_counts(disp, 1, 1)

    async def test_register_unregister_empty_disp_users(self):
        await self.manager.startService()
        reg = await self.manager.register('tcp:port', 'user', 'pass', 'pf')
        self.assertEqual(len(self.manager.services), 1)

        expected = {'tcp:port': {'user': ('pass', 'pf')}}
        self.assert_equal_registration(self.manager.dispatchers, expected)

        disp = self.manager.dispatchers['tcp:port']

        reg.unregister()
        self.assert_equal_registration(self.manager.dispatchers, {})
        self.assertEqual(reg.username, None)
        self.assertEqual(len(self.manager.services), 0)

        await self.manager.stopService()
        self.assert_start_stop_listening_counts(disp, 1, 1)

    async def test_different_ports_same_users(self):
        await self.manager.startService()
        # same registrations on different ports is ok
        reg1 = await self.manager.register('tcp:port1', "user", "pass", 'pf')
        reg2 = await self.manager.register('tcp:port2', "user", "pass", 'pf')
        reg3 = await self.manager.register('tcp:port3', "user", "pass", 'pf')

        disp1 = self.manager.dispatchers['tcp:port1']
        self.assert_start_stop_listening_counts(disp1, 1, 0)

        disp2 = self.manager.dispatchers['tcp:port2']
        self.assert_start_stop_listening_counts(disp2, 1, 0)

        disp3 = self.manager.dispatchers['tcp:port3']
        self.assert_start_stop_listening_counts(disp3, 1, 0)

        self.assert_equal_registration(
            self.manager.dispatchers,
            {
                'tcp:port1': {'user': ('pass', 'pf')},
                'tcp:port2': {'user': ('pass', 'pf')},
                'tcp:port3': {'user': ('pass', 'pf')},
            },
        )
        self.assertEqual(len(self.manager.services), 3)

        await reg1.unregister()
        self.assert_equal_registration(
            self.manager.dispatchers,
            {'tcp:port2': {'user': ('pass', 'pf')}, 'tcp:port3': {'user': ('pass', 'pf')}},
        )
        self.assertEqual(reg1.username, None)
        self.assertEqual(len(self.manager.services), 2)
        self.assert_start_stop_listening_counts(disp1, 1, 1)

        await reg2.unregister()
        self.assert_equal_registration(
            self.manager.dispatchers, {'tcp:port3': {'user': ('pass', 'pf')}}
        )
        self.assertEqual(reg2.username, None)
        self.assertEqual(len(self.manager.services), 1)
        self.assert_start_stop_listening_counts(disp2, 1, 1)

        await reg3.unregister()
        expected = {}
        self.assert_equal_registration(self.manager.dispatchers, expected)
        self.assertEqual(reg3.username, None)
        self.assertEqual(len(self.manager.services), 0)
        self.assert_start_stop_listening_counts(disp3, 1, 1)

        await self.manager.stopService()
        self.assert_start_stop_listening_counts(disp1, 1, 1)
        self.assert_start_stop_listening_counts(disp2, 1, 1)
        self.assert_start_stop_listening_counts(disp3, 1, 1)

    async def test_same_port_different_users(self):
        await self.manager.startService()
        reg1 = await self.manager.register('tcp:port', 'user1', 'pass1', 'pf1')
        reg2 = await self.manager.register('tcp:port', 'user2', 'pass2', 'pf2')
        reg3 = await self.manager.register('tcp:port', 'user3', 'pass3', 'pf3')
        disp = self.manager.dispatchers['tcp:port']

        self.assertEqual(len(self.manager.services), 1)
        self.assert_equal_registration(
            self.manager.dispatchers,
            {
                'tcp:port': {
                    'user1': ('pass1', 'pf1'),
                    'user2': ('pass2', 'pf2'),
                    'user3': ('pass3', 'pf3'),
                }
            },
        )
        self.assertEqual(len(self.manager.services), 1)

        await reg1.unregister()
        self.assert_equal_registration(
            self.manager.dispatchers,
            {'tcp:port': {'user2': ('pass2', 'pf2'), 'user3': ('pass3', 'pf3')}},
        )
        self.assertEqual(reg1.username, None)
        self.assertEqual(len(self.manager.services), 1)

        await reg2.unregister()
        self.assert_equal_registration(
            self.manager.dispatchers, {'tcp:port': {'user3': ('pass3', 'pf3')}}
        )
        self.assertEqual(reg2.username, None)
        self.assertEqual(len(self.manager.services), 1)

        await reg3.unregister()
        expected = {}
        self.assert_equal_registration(self.manager.dispatchers, expected)
        self.assertEqual(reg3.username, None)
        self.assertEqual(len(self.manager.services), 0)

        await self.manager.stopService()
        self.assert_start_stop_listening_counts(disp, 1, 1)
