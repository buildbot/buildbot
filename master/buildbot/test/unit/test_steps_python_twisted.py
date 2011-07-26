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
from buildbot.steps import python_twisted
from buildbot.status.results import SUCCESS
from buildbot.test.util import steps
from buildbot.test.fake.remotecommand import ExpectShell


class TestTrialExeceution(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_run_env(self):
        step = self.setupStep(
                python_twisted.Trial(workdir='build',
                                     tests = 'testname',
                                     testpath = None,
                                     env = {'PYTHONPATH': 'somepath'}))
        def firstInWins(name):
            if name not in self.step_status.logs:
                self.step.backupAddLog(name)
            return self.step_status.logs[name]
        self.step.backupAddLog = self.step.addLog
        self.step.addLog = firstInWins
        self.step.addLog("stdio").addStdout("Ran 0 tests\n")
        self.expectCommands(
            ExpectShell(workdir='build', command=['trial', '--reporter=bwverbose', 'testname'],
                        usePTY="slave-config",
                        logfiles={'test.log': '_trial_temp/test.log'},
                        env=dict(PYTHONPATH='somepath'))
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=['no tests', 'run'])
        return self.runStep()

    def test_run_env_supplement(self):
        self.setupStep(
                python_twisted.Trial(workdir='build',
                                     tests = 'testname',
                                     testpath = 'path1',
                                     env = {'PYTHONPATH': ['path2','path3']}))
        def firstInWins(name):
            if name not in self.step_status.logs:
                self.step.backupAddLog(name)
            return self.step_status.logs[name]
        self.step.backupAddLog = self.step.addLog
        self.step.addLog = firstInWins
        self.step.addLog("stdio").addStdout("Ran 0 tests\n")
        self.expectCommands(
            ExpectShell(workdir='build', command=['trial', '--reporter=bwverbose', 'testname'],
                        usePTY="slave-config",
                        logfiles={'test.log': '_trial_temp/test.log'},
                        env=dict(PYTHONPATH=['path2','path3','path1']))
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=['no tests', 'run'])
        return self.runStep()
