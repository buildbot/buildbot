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
from twisted.internet import defer
from buildbot.changes import base
import buildbot.status.web.change_hook as change_hook
from buildbot.test.fake.web import FakeRequest

class TestPollingChangeHook(unittest.TestCase):
    class Subclass(base.PollingChangeSource):
        pollInterval = None
        called = False

        def poll(self):
            self.called = True

    def setUp(self):
        self.changeHook = change_hook.ChangeHookResource(dialects={'poller' : True})
        self.changesrc= self.Subclass()

    @defer.inlineCallbacks
    def test_no_args(self):
        self.request = FakeRequest(args={})
        self.request.uri = "/change_hook/poller"
        self.request.method = "GET"
        yield self.request.test_render(self.changeHook)

        expected = "Request missing parameter 'poller'"
        self.assertEqual(self.request.written, expected)
        self.request.setResponseCode.assert_called_with(400, expected)

    @defer.inlineCallbacks
    def test_no_poller(self):
        self.request = FakeRequest(args={"poller":["example"]})
        self.request.uri = "/change_hook/poller"
        self.request.method = "GET"
        self.request.master.change_svc.getServiceNamed.side_effect = KeyError
        yield self.request.test_render(self.changeHook)

        expected = "No such change source 'example'"
        self.assertEqual(self.request.written, expected)
        self.request.setResponseCode.assert_called_with(400, expected)

    @defer.inlineCallbacks
    def test_invalid_poller(self):
        self.request = FakeRequest(args={"poller":["example"]})
        self.request.uri = "/change_hook/poller"
        self.request.method = "GET"
        yield self.request.test_render(self.changeHook)

        expected = "No such polling change source 'example'"
        self.assertEqual(self.request.written, expected)
        self.request.setResponseCode.assert_called_with(400, expected)

    @defer.inlineCallbacks
    def test_trigger_poll(self):
        self.request = FakeRequest(args={"poller":["example"]})
        self.request.uri = "/change_hook/poller"
        self.request.method = "GET"
        self.request.master.change_svc.getServiceNamed.return_value = self.changesrc
        yield self.request.test_render(self.changeHook)
        self.assertEqual(self.changesrc.called, True)

