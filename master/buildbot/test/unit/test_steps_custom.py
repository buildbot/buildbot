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
from buildbot.process.buildstep import BuildStepFailed, LoggingBuildStep
from buildbot.status.results import FAILURE
from buildbot.test.util import steps


class FailingCustomStep(LoggingBuildStep):

    def __init__(self, exception=BuildStepFailed, *args, **kwargs):
        LoggingBuildStep.__init__(self, *args, **kwargs)
        self.exception = exception

    @defer.inlineCallbacks
    def start(self):
        yield defer.succeed(None)
        raise self.exception()


class TestCustomStepExecution(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_step_raining_buildstepfailed_in_start(self):
        self.setupStep(FailingCustomStep())
        self.expectOutcome(result=FAILURE, status_text=["generic"])
        return self.runStep()

    def test_step_raising_exception_in_start(self):
        self.setupStep(FailingCustomStep(exception=ValueError))
        self.expectOutcome(result=FAILURE, status_text=["generic"])
        return self.runStep()

