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
from buildbot.data import testhooks
from buildbot.test.util import endpoint
from buildbot.data import exceptions
class DummyScenario(testhooks.TestHooksScenario):
    """buildbot.test.unit.test_data_testhooks.DummyScenario"""
    def dummy(self):
        pass

class TestHooksEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = testhooks.TestHooksEndpoint
    resourceTypeClass = testhooks.TestHooks

    def setUp(self):
        self.setUpEndpoint()


    def tearDown(self):
        self.tearDownEndpoint()

    def test_play_scenario(self):
        called = {}
        def playTestScenario(scenario):
            called["scenario"] = scenario
            return defer.succeed(None)
        self.master.data.updates.playTestScenario = playTestScenario
        d = self.callControl("playScenario",dict(
                scenario="dummy"), {})
        @d.addCallback
        def check(res):
            self.assertEqual(called["scenario"], "dummy")
        return d

    def test_play_scenario_bad(self):
        try:
            d = self.callControl("playScenario", {},{})
        except exceptions.InvalidOptionException,e:
            self.assertEqual( str(e), "need 'scenario' param")
            return
        @d.addCallback
        def check(res):
            self.fail("should errback")
        return d
