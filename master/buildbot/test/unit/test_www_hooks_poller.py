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

from twisted.internet import defer
from twisted.trial import unittest

import buildbot.www.change_hook as change_hook
from buildbot import util
from buildbot.changes import base
from buildbot.changes.manager import ChangeManager
from buildbot.test.fake.web import FakeRequest


class TestPollingChangeHook(unittest.TestCase):

    class Subclass(base.PollingChangeSource):
        pollInterval = None
        called = False

        def poll(self):
            self.called = True

    @defer.inlineCallbacks
    def setUpRequest(self, args, options=True, activate=True):
        self.request = FakeRequest(args=args)
        self.request.uri = "/change_hook/poller"
        self.request.method = "GET"
        master = self.request.site.master

        self.changeHook = change_hook.ChangeHookResource(
            dialects={'poller': options}, master=master)
        master.change_svc = ChangeManager()
        master.change_svc.setServiceParent(master)
        self.changesrc = self.Subclass("example", 21)
        self.changesrc.setServiceParent(master.change_svc)
        if activate:
            self.changesrc.activate()

        self.otherpoller = self.Subclass("otherpoller", 22)
        self.otherpoller.setServiceParent(master.change_svc)
        if activate:
            self.otherpoller.activate()

        anotherchangesrc = base.ChangeSource(name='notapoller')
        anotherchangesrc.setName("notapoller")
        anotherchangesrc.setServiceParent(master.change_svc)

        yield self.request.test_render(self.changeHook)
        yield util.asyncSleep(0.1)

    def tearDown(self):
        return defer.gatherResults([
            self.changesrc.deactivate(),
            self.otherpoller.deactivate(),
        ])

    @defer.inlineCallbacks
    def test_no_args(self):
        yield self.setUpRequest({})
        self.assertEqual(self.request.written, "no changes found")
        self.assertEqual(self.changesrc.called, True)
        self.assertEqual(self.otherpoller.called, True)

    @defer.inlineCallbacks
    def test_not_active(self):
        yield self.setUpRequest({}, activate=False)
        self.assertEqual(self.request.written, "no changes found")
        self.assertEqual(self.changesrc.called, False)
        self.assertEqual(self.otherpoller.called, False)

    @defer.inlineCallbacks
    def test_no_poller(self):
        yield self.setUpRequest({"poller": ["nosuchpoller"]})
        expected = "Could not find pollers: nosuchpoller"
        self.assertEqual(self.request.written, expected)
        self.request.setResponseCode.assert_called_with(400, expected)
        self.assertEqual(self.changesrc.called, False)
        self.assertEqual(self.otherpoller.called, False)

    @defer.inlineCallbacks
    def test_invalid_poller(self):
        yield self.setUpRequest({"poller": ["notapoller"]})
        expected = "Could not find pollers: notapoller"
        self.assertEqual(self.request.written, expected)
        self.request.setResponseCode.assert_called_with(400, expected)
        self.assertEqual(self.changesrc.called, False)
        self.assertEqual(self.otherpoller.called, False)

    @defer.inlineCallbacks
    def test_trigger_poll(self):
        yield self.setUpRequest({"poller": ["example"]})
        self.assertEqual(self.request.written, "no changes found")
        self.assertEqual(self.changesrc.called, True)
        self.assertEqual(self.otherpoller.called, False)

    @defer.inlineCallbacks
    def test_allowlist_deny(self):
        yield self.setUpRequest({"poller": ["otherpoller"]}, options={"allowed": ["example"]})
        expected = "Could not find pollers: otherpoller"
        self.assertEqual(self.request.written, expected)
        self.request.setResponseCode.assert_called_with(400, expected)
        self.assertEqual(self.changesrc.called, False)
        self.assertEqual(self.otherpoller.called, False)

    @defer.inlineCallbacks
    def test_allowlist_allow(self):
        yield self.setUpRequest({"poller": ["example"]}, options={"allowed": ["example"]})
        self.assertEqual(self.request.written, "no changes found")
        self.assertEqual(self.changesrc.called, True)
        self.assertEqual(self.otherpoller.called, False)

    @defer.inlineCallbacks
    def test_allowlist_all(self):
        yield self.setUpRequest({}, options={"allowed": ["example"]})
        self.assertEqual(self.request.written, "no changes found")
        self.assertEqual(self.changesrc.called, True)
        self.assertEqual(self.otherpoller.called, False)
