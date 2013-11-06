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

import buildbot.status.web.change_hook as change_hook

from buildbot.changes import base
from buildbot.changes.manager import ChangeManager
from buildbot.test.fake.web import FakeRequest
from twisted.internet import defer
from twisted.trial import unittest


class TestPollingChangeHook(unittest.TestCase):

    class Subclass(base.PollingChangeSource):
        pollInterval = None
        called = False

        def poll(self):
            self.called = True

    def setUpRequest(self, args, options=True):
        self.changeHook = change_hook.ChangeHookResource(dialects={'poller': options})

        self.request = FakeRequest(args=args)
        self.request.uri = "/change_hook/poller"
        self.request.method = "GET"

        master = self.request.site.buildbot_service.master
        master.change_svc = ChangeManager(master)

        self.changesrc = self.Subclass("example", None)
        self.changesrc.setServiceParent(master.change_svc)

        self.disabledChangesrc = self.Subclass("disabled", None)
        self.disabledChangesrc.setServiceParent(master.change_svc)

        anotherchangesrc = base.ChangeSource()
        anotherchangesrc.setName("notapoller")
        anotherchangesrc.setServiceParent(master.change_svc)

        return self.request.test_render(self.changeHook)

    @defer.inlineCallbacks
    def test_no_args(self):
        yield self.setUpRequest({})
        self.assertEqual(self.request.written, "no changes found")
        self.assertEqual(self.changesrc.called, True)
        self.assertEqual(self.disabledChangesrc.called, True)

    @defer.inlineCallbacks
    def test_no_poller(self):
        yield self.setUpRequest({"poller": ["nosuchpoller"]})
        expected = "Could not find pollers: nosuchpoller"
        self.assertEqual(self.request.written, expected)
        self.request.setResponseCode.assert_called_with(400, expected)
        self.assertEqual(self.changesrc.called, False)
        self.assertEqual(self.disabledChangesrc.called, False)

    @defer.inlineCallbacks
    def test_invalid_poller(self):
        yield self.setUpRequest({"poller": ["notapoller"]})
        expected = "Could not find pollers: notapoller"
        self.assertEqual(self.request.written, expected)
        self.request.setResponseCode.assert_called_with(400, expected)
        self.assertEqual(self.changesrc.called, False)
        self.assertEqual(self.disabledChangesrc.called, False)

    @defer.inlineCallbacks
    def test_trigger_poll(self):
        yield self.setUpRequest({"poller": ["example"]})
        self.assertEqual(self.request.written, "no changes found")
        self.assertEqual(self.changesrc.called, True)
        self.assertEqual(self.disabledChangesrc.called, False)

    @defer.inlineCallbacks
    def test_allowlist_deny(self):
        yield self.setUpRequest({"poller": ["disabled"]}, options={"allowed": ["example"]})
        expected = "Could not find pollers: disabled"
        self.assertEqual(self.request.written, expected)
        self.request.setResponseCode.assert_called_with(400, expected)
        self.assertEqual(self.changesrc.called, False)
        self.assertEqual(self.disabledChangesrc.called, False)

    @defer.inlineCallbacks
    def test_allowlist_allow(self):
        yield self.setUpRequest({"poller": ["example"]}, options={"allowed": ["example"]})
        self.assertEqual(self.request.written, "no changes found")
        self.assertEqual(self.changesrc.called, True)
        self.assertEqual(self.disabledChangesrc.called, False)

    @defer.inlineCallbacks
    def test_allowlist_all(self):
        yield self.setUpRequest({}, options={"allowed": ["example"]})
        self.assertEqual(self.request.written, "no changes found")
        self.assertEqual(self.changesrc.called, True)
        self.assertEqual(self.disabledChangesrc.called, False)
