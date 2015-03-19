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
from buildbot.process.properties import Property



class Trial(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_run_env(self):
        self.setupStep(
                python_twisted.Trial(workdir='build',
                                     tests = 'testname',
                                     testpath = None,
                                     env = {'PYTHONPATH': 'somepath'}))
        self.expectCommands(
            ExpectShell(workdir='build',
                        command=['trial', '--reporter=bwverbose', 'testname'],
                        usePTY="slave-config",
                        logfiles={'test.log': '_trial_temp/test.log'},
                        env=dict(PYTHONPATH='somepath'))
            + ExpectShell.log('stdio', stdout="Ran 0 tests\n")
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
        self.expectCommands(
            ExpectShell(workdir='build',
                        command=['trial', '--reporter=bwverbose', 'testname'],
                        usePTY="slave-config",
                        logfiles={'test.log': '_trial_temp/test.log'},
                        env=dict(PYTHONPATH=['path1', 'path2', 'path3']))
            + ExpectShell.log('stdio', stdout="Ran 0 tests\n")
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=['no tests', 'run'])
        return self.runStep()

    def test_run_env_nodupe(self):
        self.setupStep(
                python_twisted.Trial(workdir='build',
                                     tests = 'testname',
                                     testpath = 'path2',
                                     env = {'PYTHONPATH': ['path1','path2']}))
        self.expectCommands(
            ExpectShell(workdir='build',
                        command=['trial', '--reporter=bwverbose', 'testname'],
                        usePTY="slave-config",
                        logfiles={'test.log': '_trial_temp/test.log'},
                        env=dict(PYTHONPATH=['path1','path2']))
            + ExpectShell.log('stdio', stdout="Ran 0 tests\n")
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=['no tests', 'run'])
        return self.runStep()

    def test_run_singular(self):
        self.setupStep(
                python_twisted.Trial(workdir='build',
                                     tests = 'testname',
                                     testpath=None))
        self.expectCommands(
            ExpectShell(workdir='build',
                        command=['trial', '--reporter=bwverbose', 'testname'],
                        usePTY="slave-config",
                        logfiles={'test.log': '_trial_temp/test.log'})
            + ExpectShell.log('stdio', stdout="Ran 1 tests\n")
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=['1 test', 'passed'])
        return self.runStep()

    def test_run_plural(self):
        self.setupStep(
                python_twisted.Trial(workdir='build',
                                     tests = 'testname',
                                     testpath=None))
        self.expectCommands(
            ExpectShell(workdir='build',
                        command=['trial', '--reporter=bwverbose', 'testname'],
                        usePTY="slave-config",
                        logfiles={'test.log': '_trial_temp/test.log'})
            + ExpectShell.log('stdio', stdout="Ran 2 tests\n")
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=['2 tests', 'passed'])
        return self.runStep()
        
    def testProperties(self):
        self.setupStep(python_twisted.Trial(workdir='build',
                                     tests = Property('test_list'),
                                     testpath=None))
        self.properties.setProperty('test_list',['testname'], 'Test')

        self.expectCommands(
            ExpectShell(workdir='build',
                        command=['trial', '--reporter=bwverbose', 'testname'],
                        usePTY="slave-config",
                        logfiles={'test.log': '_trial_temp/test.log'})
            + ExpectShell.log('stdio', stdout="Ran 2 tests\n")
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=['2 tests', 'passed'])
        return self.runStep()

    def test_run_jobs(self):
        """
        The C{jobs} kwarg should correspond to trial's -j option (
        included since Twisted 12.3.0), and make corresponding changes to
        logfiles.
        """
        self.setupStep(python_twisted.Trial(workdir='build',
                                    tests = 'testname',
                                    testpath = None,
                                    jobs=2))

        self.expectCommands(
            ExpectShell(workdir='build',
                        command=['trial', '--reporter=bwverbose', '--jobs=2',
                                 'testname'],
                        usePTY="slave-config",
                        logfiles={
                            'test.0.log': '_trial_temp/0/test.log',
                            'err.0.log': '_trial_temp/0/err.log',
                            'out.0.log': '_trial_temp/0/out.log',
                            'test.1.log': '_trial_temp/1/test.log',
                            'err.1.log': '_trial_temp/1/err.log',
                            'out.1.log': '_trial_temp/1/out.log',
                        })
            + ExpectShell.log('stdio', stdout="Ran 1 tests\n")
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=['1 test', 'passed'])
        return self.runStep()

    def test_run_jobsProperties(self):
        """
        C{jobs} should accept Properties
        """
        self.setupStep(python_twisted.Trial(workdir='build',
                                     tests = 'testname',
                                     jobs=Property('jobs_count'),
                                     testpath=None))
        self.properties.setProperty('jobs_count', '2', 'Test')

        self.expectCommands(
            ExpectShell(workdir='build',
                        command=['trial', '--reporter=bwverbose', '--jobs=2',
                                 'testname'],
                        usePTY="slave-config",
                        logfiles={
                            'test.0.log': '_trial_temp/0/test.log',
                            'err.0.log': '_trial_temp/0/err.log',
                            'out.0.log': '_trial_temp/0/out.log',
                            'test.1.log': '_trial_temp/1/test.log',
                            'err.1.log': '_trial_temp/1/err.log',
                            'out.1.log': '_trial_temp/1/out.log',
                        })
            + ExpectShell.log('stdio', stdout="Ran 1 tests\n")
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=['1 test', 'passed'])
        return self.runStep()

