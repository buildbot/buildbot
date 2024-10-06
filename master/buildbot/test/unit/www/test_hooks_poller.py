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


from twisted.trial import unittest

from buildbot import util
from buildbot.changes import base
from buildbot.changes.manager import ChangeManager
from buildbot.test.fake import fakemaster
from buildbot.test.fake.web import FakeRequest
from buildbot.test.reactor import TestReactorMixin
from buildbot.www import change_hook


class TestPollingChangeHook(TestReactorMixin, unittest.TestCase):
    class Subclass(base.ReconfigurablePollingChangeSource):
        pollInterval = None
        called = False

        def poll(self):
            self.called = True

    def setUp(self):
        self.setup_test_reactor()

    async def setUpRequest(self, args, options=True, activate=True):
        self.request = FakeRequest(args=args)
        self.request.uri = b"/change_hook/poller"
        self.request.method = b"GET"
        www = self.request.site.master.www
        self.master = master = self.request.site.master = fakemaster.make_master(
            self, wantData=True
        )
        master.www = www
        await self.master.startService()
        self.changeHook = change_hook.ChangeHookResource(
            dialects={'poller': options}, master=master
        )
        master.change_svc = ChangeManager()
        await master.change_svc.setServiceParent(master)
        self.changesrc = self.Subclass(21, name=b'example')
        await self.changesrc.setServiceParent(master.change_svc)

        self.otherpoller = self.Subclass(22, name=b"otherpoller")
        await self.otherpoller.setServiceParent(master.change_svc)

        anotherchangesrc = base.ChangeSource(name=b'notapoller')
        anotherchangesrc.setName("notapoller")
        await anotherchangesrc.setServiceParent(master.change_svc)

        await self.request.test_render(self.changeHook)
        await util.asyncSleep(0.1)

    def tearDown(self):
        return self.master.stopService()

    async def test_no_args(self):
        await self.setUpRequest({})
        self.assertEqual(self.request.written, b"no change found")
        self.assertEqual(self.changesrc.called, True)
        self.assertEqual(self.otherpoller.called, True)

    async def test_no_poller(self):
        await self.setUpRequest({b"poller": [b"nosuchpoller"]})
        expected = b"Could not find pollers: nosuchpoller"
        self.assertEqual(self.request.written, expected)
        self.request.setResponseCode.assert_called_with(400, expected)
        self.assertEqual(self.changesrc.called, False)
        self.assertEqual(self.otherpoller.called, False)

    async def test_invalid_poller(self):
        await self.setUpRequest({b"poller": [b"notapoller"]})
        expected = b"Could not find pollers: notapoller"
        self.assertEqual(self.request.written, expected)
        self.request.setResponseCode.assert_called_with(400, expected)
        self.assertEqual(self.changesrc.called, False)
        self.assertEqual(self.otherpoller.called, False)

    async def test_trigger_poll(self):
        await self.setUpRequest({b"poller": [b"example"]})
        self.assertEqual(self.request.written, b"no change found")
        self.assertEqual(self.changesrc.called, True)
        self.assertEqual(self.otherpoller.called, False)

    async def test_allowlist_deny(self):
        await self.setUpRequest({b"poller": [b"otherpoller"]}, options={b"allowed": [b"example"]})
        expected = b"Could not find pollers: otherpoller"
        self.assertEqual(self.request.written, expected)
        self.request.setResponseCode.assert_called_with(400, expected)
        self.assertEqual(self.changesrc.called, False)
        self.assertEqual(self.otherpoller.called, False)

    async def test_allowlist_allow(self):
        await self.setUpRequest({b"poller": [b"example"]}, options={b"allowed": [b"example"]})
        self.assertEqual(self.request.written, b"no change found")
        self.assertEqual(self.changesrc.called, True)
        self.assertEqual(self.otherpoller.called, False)

    async def test_allowlist_all(self):
        await self.setUpRequest({}, options={b"allowed": [b"example"]})
        self.assertEqual(self.request.written, b"no change found")
        self.assertEqual(self.changesrc.called, True)
        self.assertEqual(self.otherpoller.called, False)
