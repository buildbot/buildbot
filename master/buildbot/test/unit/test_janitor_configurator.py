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

import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.configurators import janitor
from buildbot.configurators.janitor import JANITOR_NAME
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

    def test_basic(self):
        self.setupConfigurator(logHorizon=timedelta(weeks=1),
                               buildersLogHorizon={"Builder1":timedelta(days=6),
                                                   "Builder2":timedelta(weeks=3)})
        self.expectWorker(JANITOR_NAME, LocalWorker)
        self.expectScheduler(JANITOR_NAME, Nightly)
        self.expectScheduler(JANITOR_NAME + "_force", ForceScheduler)
        self.expectBuilderHasSteps(JANITOR_NAME, [LogChunksJanitor])
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
        self.master.db.logs.deleteOldLogChunks.assert_called_with(expected_timestamp, filtering=None)
        
    @defer.inlineCallbacks
    def test_deleting_specific_logs(self):
        self.setupStep(
            LogChunksJanitor(buildersLogHorizon={"Builder1":timedelta(days=6),
                                                 "Builder2":timedelta(weeks=3)}))
        self.master.db.logs.deleteBuilderLog = mock.Mock(return_value={"Builder1":2, "Builder2":4})
        self.expectOutcome(result=SUCCESS,
                           state_string="deleted 2 logchunks from Builder1 \n deleted 4 logchunks from Builder2")
        yield self.runStep()
        expected_builder_timestamps = {"Builder1":datetime2epoch(datetime.datetime(year=2016, month=12, day=26)),
                                       "Builder2":datetime2epoch(datetime.datetime(year=2016, month=12, day=11))}
        self.master.db.logs.deleteBuilderLog.assert_called_with(expected_builder_timestamps)
        
