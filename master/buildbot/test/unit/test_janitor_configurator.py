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

from __future__ import absolute_import
from __future__ import print_function

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
from buildbot.test.util.warnings import assertProducesWarning
from buildbot.util import datetime2epoch
from buildbot.worker.local import LocalWorker
from buildbot.worker_transition import DeprecatedWorkerNameWarning


class JanitorConfiguratorTests(configurators.ConfiguratorMixin, unittest.SynchronousTestCase):
    ConfiguratorClass = JanitorConfigurator

    def test_nothing(self):
        self.setupConfigurator()
        self.assertEqual(self.config_dict, {
        })

    def test_basic(self):
        self.setupConfigurator(logHorizon=timedelta(weeks=1))
        self.expectWorker(JANITOR_NAME, LocalWorker)
        self.expectScheduler(JANITOR_NAME, Nightly)
        self.expectScheduler(JANITOR_NAME + "_force", ForceScheduler)
        self.expectBuilderHasSteps(JANITOR_NAME, [LogChunksJanitor])
        self.expectNoConfigError()

    def test_worker_vs_slaves(self):
        """The base configurator uses the slaves config if it exists already"""
        self.config_dict['slaves'] = []
        self.setupConfigurator(logHorizon=timedelta(weeks=1))
        self.expectWorker(JANITOR_NAME, LocalWorker)
        self.expectScheduler(JANITOR_NAME, Nightly)
        self.expectBuilderHasSteps(JANITOR_NAME, [LogChunksJanitor])
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern=r"c\['slaves'\] key is deprecated, "
                                r"use c\['workers'\] instead"):
                self.expectNoConfigError()


class LogChunksJanitorTests(steps.BuildStepMixin, unittest.TestCase, configmixin.ConfigErrorsMixin):

    @defer.inlineCallbacks
    def setUp(self):
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
                           state_string=u"deleted 3 logchunks")
        yield self.runStep()
        expected_timestamp = datetime2epoch(datetime.datetime(year=2016, month=12, day=25))
        self.master.db.logs.deleteOldLogChunks.assert_called_with(expected_timestamp)
