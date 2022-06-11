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


import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.changes import base
from buildbot.changes import manager
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util.warnings import assertProducesWarnings
from buildbot.warnings import DeprecatedApiWarning


class TestChangeManager(unittest.TestCase, TestReactorMixin):

    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self, wantData=True)
        self.cm = manager.ChangeManager()
        self.master.startService()
        yield self.cm.setServiceParent(self.master)
        self.new_config = mock.Mock()

    def tearDown(self):
        return self.master.stopService()

    def make_sources(self, n, klass=base.ChangeSource, **kwargs):
        for i in range(n):
            src = klass(name=f'ChangeSource {i}', **kwargs)
            yield src

    @defer.inlineCallbacks
    def test_reconfigService_add(self):
        src1, src2 = self.make_sources(2)
        yield src1.setServiceParent(self.cm)
        self.new_config.change_sources = [src1, src2]

        yield self.cm.reconfigServiceWithBuildbotConfig(self.new_config)

        self.assertIdentical(src2.parent, self.cm)
        self.assertIdentical(src2.master, self.master)

    @defer.inlineCallbacks
    def test_reconfigService_remove(self):
        src1, = self.make_sources(1)
        yield src1.setServiceParent(self.cm)
        self.new_config.change_sources = []

        self.assertTrue(src1.running)
        yield self.cm.reconfigServiceWithBuildbotConfig(self.new_config)

        self.assertFalse(src1.running)

    @defer.inlineCallbacks
    def test_reconfigService_change_reconfigurable(self):
        src1, = self.make_sources(1, base.ReconfigurablePollingChangeSource, pollInterval=1)
        yield src1.setServiceParent(self.cm)

        src2, = self.make_sources(1, base.ReconfigurablePollingChangeSource, pollInterval=2)

        self.new_config.change_sources = [src2]

        self.assertTrue(src1.running)
        self.assertEqual(src1.pollInterval, 1)
        yield self.cm.reconfigServiceWithBuildbotConfig(self.new_config)

        self.assertTrue(src1.running)
        self.assertFalse(src2.running)
        self.assertEqual(src1.pollInterval, 2)

    @defer.inlineCallbacks
    def test_reconfigService_change_legacy(self):
        with assertProducesWarnings(DeprecatedApiWarning,
                                    message_pattern="use ReconfigurablePollingChangeSource"):
            src1, = self.make_sources(1, base.PollingChangeSource, pollInterval=1)
        yield src1.setServiceParent(self.cm)

        with assertProducesWarnings(DeprecatedApiWarning,
                                    message_pattern="use ReconfigurablePollingChangeSource"):
            src2, = self.make_sources(1, base.PollingChangeSource, pollInterval=2)

        self.new_config.change_sources = [src2]

        self.assertTrue(src1.running)
        self.assertEqual(src1.pollInterval, 1)
        yield self.cm.reconfigServiceWithBuildbotConfig(self.new_config)

        self.assertFalse(src1.running)
        self.assertTrue(src2.running)
        self.assertEqual(src2.pollInterval, 2)
