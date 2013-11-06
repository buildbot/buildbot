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

from buildbot import config
from buildbot.status.results import FAILURE
from buildbot.status.results import SUCCESS
from buildbot.steps import maxq
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.util import steps
from twisted.trial import unittest


class TestShellCommandExecution(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_testdir_required(self):
        self.assertRaises(config.ConfigErrors, lambda: maxq.MaxQ())

    def test_success(self):
        self.setupStep(
            maxq.MaxQ(testdir='x'))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command="run_maxq.py x")
            + ExpectShell.log('stdio', stdout='no failures\n')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=['maxq', 'tests'])
        return self.runStep()

    def test_nonzero_rc_no_failures(self):
        self.setupStep(
            maxq.MaxQ(testdir='x'))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command="run_maxq.py x")
            + ExpectShell.log('stdio', stdout='no failures\n')
            + 2
        )
        self.expectOutcome(result=FAILURE,
                           status_text=['1', 'maxq', 'failures'])
        return self.runStep()

    def test_failures(self):
        self.setupStep(
            maxq.MaxQ(testdir='x'))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command="run_maxq.py x")
            + ExpectShell.log('stdio', stdout='\nTEST FAILURE: foo\n' * 10)
            + 2
        )
        self.expectOutcome(result=FAILURE,
                           status_text=['10', 'maxq', 'failures'])
        return self.runStep()
