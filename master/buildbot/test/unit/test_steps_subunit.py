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

import StringIO
import mock

from buildbot import interfaces
from buildbot.process import subunitlogobserver
from buildbot.status.results import FAILURE
from buildbot.status.results import SUCCESS
from buildbot.steps import subunit
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.util import steps
from twisted.trial import unittest
from zope.interface import implements


class StubLogObserver(mock.Mock):
    implements(interfaces.ILogObserver)


class TestSetPropertiesFromEnv(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        self.logobserver = StubLogObserver()
        self.logobserver.failures = []
        self.logobserver.errors = []
        self.logobserver.skips = []
        self.logobserver.testsRun = 0
        self.logobserver.warningio = StringIO.StringIO()
        self.patch(subunitlogobserver, 'SubunitLogObserver',
                   lambda: self.logobserver)
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_empty(self):
        self.setupStep(subunit.SubunitShellCommand(command='test'))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command="test")
            + 0
        )
        self.expectOutcome(result=SUCCESS,
                           status_text=["shell", "no tests", "run"])
        return self.runStep()

    def test_empty_error(self):
        self.setupStep(subunit.SubunitShellCommand(command='test',
                                                   failureOnNoTests=True))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command="test")
            + 0
        )
        self.expectOutcome(result=FAILURE,
                           status_text=["shell", "no tests", "run"])
        return self.runStep()

    def test_warnings(self):
        self.setupStep(subunit.SubunitShellCommand(command='test'))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command="test")
            + 0
        )
        self.logobserver.warnings.append('not quite up to snuff (list)')
        self.logobserver.warningio.write('not quite up to snuff (io)\n')
        self.logobserver.testsRun = 3
        self.expectOutcome(result=SUCCESS,  # N.B. not WARNINGS
                           status_text=["shell", "3 tests", "passed"])
        # note that the warnings list is ignored..
        self.expectLogfile('warnings', 'not quite up to snuff (io)\n')
        return self.runStep()

    # TODO: test text2 generation?
    # TODO: tests are represented as objects?!
