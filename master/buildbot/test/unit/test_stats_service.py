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

from buildbot.statistics.storage_backends import StatsStorageBase
from buildbot.statistics.storage_backends import InfluxStorageService
from buildbot.test.fake import fakemaster
from buildbot.test.fake import fakestats


class TestStatsServicesBase(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master()
        self.master.stats_service.startService()

    def tearDown(self):
        self.master.stats_service.stopService()


class TestStatsServicesConfiguration(TestStatsServicesBase):

    @defer.inlineCallbacks
    def test_reconfigure_without_conf(self):
        yield self.master.stats_service.reconfigServiceWithBuildbotConfig(self.master.config)
        self.checkEqual(self.master.config)

    @defer.inlineCallbacks
    def test_reconfigure_with_fake_service(self):
        # First, configure with an empty service
        yield self.master.stats_service.reconfigServiceWithBuildbotConfig(self.master.config)
        self.checkEqual(self.master.config)

        # Now, reconfigure with a FakeStatsStorageService.
        self.master.config.statsServices = [fakestats.FakeStatsStorageService()]
        yield self.master.stats_service.reconfigServiceWithBuildbotConfig(self.master.config)
        self.checkEqual(self.master.config)

        # unset it, see it stop
        self.master.config.statsServices = []
        yield self.master.stats_service.reconfigServiceWithBuildbotConfig(self.master.config)
        self.checkEqual(self.master.config)

    @defer.inlineCallbacks
    def test_bad_configuration(self):
        # First, configure with an empty service
        yield self.master.stats_service.reconfigServiceWithBuildbotConfig(self.master.config)
        self.checkEqual(self.master.config)

        # Now, reconfigure with a bad configuration.
        self.master.config.statsServices = [mock.Mock()]
        yield self.assertRaises(TypeError,
                                self.master.stats_service.reconfigServiceWithBuildbotConfig,
                                self.master.config)

    def checkEqual(self, new_config):
        # Check whether the new_config was set in reconfigServiceWithBuildbotConfig
        newMetricsStorageServices = [s for s in new_config.statsServices
                                     if isinstance(s, StatsStorageBase)]
        registeredStorageServices = \
        [s for s in self.master.stats_service.registeredStorageServices
         if isinstance(s, StatsStorageBase)]
        for s in newMetricsStorageServices:
            if s not in registeredStorageServices:
                raise AssertionError("reconfigServiceWithBuildbotConfig failed."
                                     "Not all storage services registered.")
