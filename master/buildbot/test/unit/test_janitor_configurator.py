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


import datetime
from datetime import timedelta

from parameterized import parameterized

import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.configurators import janitor
from buildbot.configurators.janitor import JANITOR_NAME
from buildbot.configurators.janitor import BuildDataJanitor
from buildbot.configurators.janitor import JanitorConfigurator
from buildbot.configurators.janitor import LogChunksJanitor
from buildbot.process.results import SUCCESS
from buildbot.schedulers.forcesched import ForceScheduler
from buildbot.schedulers.timed import Nightly
from buildbot.test.util import config as configmixin
from buildbot.test.util import configurators
from buildbot.test.util import steps
from buildbot.test.util.misc import TestReactorMixin
from buildbot.util import datetime2epoch
from buildbot.worker.local import LocalWorker


class JanitorConfiguratorTests(configurators.ConfiguratorMixin, unittest.SynchronousTestCase):
    ConfiguratorClass = JanitorConfigurator

    def test_nothing(self):
        self.setupConfigurator()
        self.assertEqual(self.config_dict, {
        })

    @parameterized.expand([
        ('logs', {'logHorizon': timedelta(weeks=1)}, [LogChunksJanitor]),
        ('build_data', {'build_data_horizon': timedelta(weeks=1)}, [BuildDataJanitor]),
        ('logs_build_data', {'build_data_horizon': timedelta(weeks=1),
                             'logHorizon': timedelta(weeks=1)},
         [LogChunksJanitor, BuildDataJanitor]),
    ])
    def test_steps(self, name, configuration, exp_steps):
        self.setupConfigurator(**configuration)
        self.expectWorker(JANITOR_NAME, LocalWorker)
        self.expectScheduler(JANITOR_NAME, Nightly)
        self.expectScheduler(JANITOR_NAME + "_force", ForceScheduler)
        self.expectBuilderHasSteps(JANITOR_NAME, exp_steps)
        self.expectNoConfigError()


class LogChunksJanitorTests(steps.BuildStepMixin,
                            configmixin.ConfigErrorsMixin,
                            TestReactorMixin,
                            unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self.setUpTestReactor()
        yield self.setUpBuildStep()
        self.patch(janitor, "now", lambda: datetime.datetime(year=2017, month=1, day=1))

    def tearDown(self):
        return self.tearDownBuildStep()

    @defer.inlineCallbacks
    def test_basic(self):
        self.setupStep(
            LogChunksJanitor(logHorizon=timedelta(weeks=1)))
        self.master.db.logs.deleteOldLogChunks = mock.Mock(return_value=3)
        self.expectOutcome(result=SUCCESS,
                           state_string="deleted 3 logchunks")
        yield self.runStep()
        expected_timestamp = datetime2epoch(datetime.datetime(year=2016, month=12, day=25))
        self.master.db.logs.deleteOldLogChunks.assert_called_with(expected_timestamp)

    @defer.inlineCallbacks
    def test_build_data(self):
        self.setupStep(BuildDataJanitor(build_data_horizon=timedelta(weeks=1)))
        self.master.db.build_data.deleteOldBuildData = mock.Mock(return_value=4)
        self.expectOutcome(result=SUCCESS, state_string="deleted 4 build data key-value pairs")
        yield self.runStep()
        expected_timestamp = datetime2epoch(datetime.datetime(year=2016, month=12, day=25))
        self.master.db.build_data.deleteOldBuildData.assert_called_with(expected_timestamp)
