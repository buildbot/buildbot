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

import textwrap

from twisted.trial import unittest

from buildbot.process.properties import Property
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.steps import python_twisted
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.util import steps


failureLog = '''\
buildbot.test.unit.test_steps_python_twisted.Trial.testProperties ... [FAILURE]
buildbot.test.unit.test_steps_python_twisted.Trial.test_run_env ... [FAILURE]
buildbot.test.unit.test_steps_python_twisted.Trial.test_run_env_nodupe ... [FAILURE]/home/dustin/code/buildbot/t/buildbot/master/buildbot/test/fake/logfile.py:92: UserWarning: step uses removed LogFile method `getText`
buildbot.test.unit.test_steps_python_twisted.Trial.test_run_env_supplement ... [FAILURE]/home/dustin/code/buildbot/t/buildbot/master/buildbot/test/fake/logfile.py:92: UserWarning: step uses removed LogFile method `getText`
buildbot.test.unit.test_steps_python_twisted.Trial.test_run_jobs ... [FAILURE]/home/dustin/code/buildbot/t/buildbot/master/buildbot/test/fake/logfile.py:92: UserWarning: step uses removed LogFile method `getText`
buildbot.test.unit.test_steps_python_twisted.Trial.test_run_jobsProperties ... [FAILURE]
buildbot.test.unit.test_steps_python_twisted.Trial.test_run_plural ... [FAILURE]
buildbot.test.unit.test_steps_python_twisted.Trial.test_run_singular ... [FAILURE]

===============================================================================
[FAIL]
Traceback (most recent call last):
  File "/home/dustin/code/buildbot/t/buildbot/master/buildbot/test/util/steps.py", line 244, in check
    "expected step outcome")
  File "/home/dustin/code/buildbot/t/buildbot/sandbox/lib/python2.7/site-packages/twisted/trial/_synctest.py", line 356, in assertEqual
    % (msg, pformat(first), pformat(second)))
twisted.trial.unittest.FailTest: expected step outcome
not equal:
a = {'result': 3, 'status_text': ['2 tests', 'passed']}
b = {'result': 0, 'status_text': ['2 tests', 'passed']}


buildbot.test.unit.test_steps_python_twisted.Trial.testProperties
buildbot.test.unit.test_steps_python_twisted.Trial.test_run_plural
===============================================================================
[FAIL]
Traceback (most recent call last):
  File "/home/dustin/code/buildbot/t/buildbot/master/buildbot/test/util/steps.py", line 244, in check
    "expected step outcome")
  File "/home/dustin/code/buildbot/t/buildbot/sandbox/lib/python2.7/site-packages/twisted/trial/_synctest.py", line 356, in assertEqual
    % (msg, pformat(first), pformat(second)))
twisted.trial.unittest.FailTest: expected step outcome
not equal:
a = {'result': 3, 'status_text': ['no tests', 'run']}
b = {'result': 0, 'status_text': ['no tests', 'run']}


buildbot.test.unit.test_steps_python_twisted.Trial.test_run_env
buildbot.test.unit.test_steps_python_twisted.Trial.test_run_env_nodupe
buildbot.test.unit.test_steps_python_twisted.Trial.test_run_env_supplement
===============================================================================
[FAIL]
Traceback (most recent call last):
  File "/home/dustin/code/buildbot/t/buildbot/master/buildbot/test/util/steps.py", line 244, in check
    "expected step outcome")
  File "/home/dustin/code/buildbot/t/buildbot/sandbox/lib/python2.7/site-packages/twisted/trial/_synctest.py", line 356, in assertEqual
    % (msg, pformat(first), pformat(second)))
twisted.trial.unittest.FailTest: expected step outcome
not equal:
a = {'result': 3, 'status_text': ['1 test', 'passed']}
b = {'result': 0, 'status_text': ['1 test', 'passed']}


buildbot.test.unit.test_steps_python_twisted.Trial.test_run_jobs
buildbot.test.unit.test_steps_python_twisted.Trial.test_run_jobsProperties
buildbot.test.unit.test_steps_python_twisted.Trial.test_run_singular
-------------------------------------------------------------------------------
Ran 8 tests in 0.101s

FAILED (failures=8)
'''


class Trial(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_run_env(self):
        self.setupStep(
            python_twisted.Trial(workdir='build',
                                 tests='testname',
                                 testpath=None,
                                 env={'PYTHONPATH': 'somepath'}))
        self.expectCommands(
            ExpectShell(workdir='build',
                        command=['trial', '--reporter=bwverbose', 'testname'],
                        logfiles={'test.log': '_trial_temp/test.log'},
                        env=dict(PYTHONPATH='somepath'))
            + ExpectShell.log('stdio', stdout="Ran 0 tests\n")
            + 0
        )
        self.expectOutcome(result=SUCCESS, state_string='no tests run')
        return self.runStep()

    def test_run_env_supplement(self):
        self.setupStep(
            python_twisted.Trial(workdir='build',
                                 tests='testname',
                                 testpath='path1',
                                 env={'PYTHONPATH': ['path2', 'path3']}))
        self.expectCommands(
            ExpectShell(workdir='build',
                        command=['trial', '--reporter=bwverbose', 'testname'],
                        logfiles={'test.log': '_trial_temp/test.log'},
                        env=dict(PYTHONPATH=['path1', 'path2', 'path3']))
            + ExpectShell.log('stdio', stdout="Ran 0 tests\n")
            + 0
        )
        self.expectOutcome(result=SUCCESS, state_string='no tests run')
        return self.runStep()

    def test_run_env_nodupe(self):
        self.setupStep(
            python_twisted.Trial(workdir='build',
                                 tests='testname',
                                 testpath='path2',
                                 env={'PYTHONPATH': ['path1', 'path2']}))
        self.expectCommands(
            ExpectShell(workdir='build',
                        command=['trial', '--reporter=bwverbose', 'testname'],
                        logfiles={'test.log': '_trial_temp/test.log'},
                        env=dict(PYTHONPATH=['path1', 'path2']))
            + ExpectShell.log('stdio', stdout="Ran 0 tests\n")
            + 0
        )
        self.expectOutcome(result=SUCCESS, state_string='no tests run')
        return self.runStep()

    def test_run_singular(self):
        self.setupStep(
            python_twisted.Trial(workdir='build',
                                 tests='testname',
                                 testpath=None))
        self.expectCommands(
            ExpectShell(workdir='build',
                        command=['trial', '--reporter=bwverbose', 'testname'],
                        logfiles={'test.log': '_trial_temp/test.log'})
            + ExpectShell.log('stdio', stdout="Ran 1 tests\n")
            + 0
        )
        self.expectOutcome(result=SUCCESS, state_string='1 test passed')
        return self.runStep()

    def test_run_plural(self):
        self.setupStep(
            python_twisted.Trial(workdir='build',
                                 tests='testname',
                                 testpath=None))
        self.expectCommands(
            ExpectShell(workdir='build',
                        command=['trial', '--reporter=bwverbose', 'testname'],
                        logfiles={'test.log': '_trial_temp/test.log'})
            + ExpectShell.log('stdio', stdout="Ran 2 tests\n")
            + 0
        )
        self.expectOutcome(result=SUCCESS, state_string='2 tests passed')
        return self.runStep()

    def test_run_failure(self):
        self.setupStep(
            python_twisted.Trial(workdir='build',
                                 tests='testname',
                                 testpath=None))
        self.expectCommands(
            ExpectShell(workdir='build',
                        command=['trial', '--reporter=bwverbose', 'testname'],
                        logfiles={'test.log': '_trial_temp/test.log'})
            + ExpectShell.log('stdio', stdout=failureLog)
            + 1
        )
        self.expectOutcome(
            result=FAILURE, state_string='tests 8 failures (failure)')
        self.expectLogfile('problems', failureLog.split('\n\n', 1)[1][:-1])
        self.expectLogfile('warnings', textwrap.dedent('''\
                buildbot.test.unit.test_steps_python_twisted.Trial.test_run_env_nodupe ... [FAILURE]/home/dustin/code/buildbot/t/buildbot/master/buildbot/test/fake/logfile.py:92: UserWarning: step uses removed LogFile method `getText`
                buildbot.test.unit.test_steps_python_twisted.Trial.test_run_env_supplement ... [FAILURE]/home/dustin/code/buildbot/t/buildbot/master/buildbot/test/fake/logfile.py:92: UserWarning: step uses removed LogFile method `getText`
                buildbot.test.unit.test_steps_python_twisted.Trial.test_run_jobs ... [FAILURE]/home/dustin/code/buildbot/t/buildbot/master/buildbot/test/fake/logfile.py:92: UserWarning: step uses removed LogFile method `getText`
                buildbot.test.unit.test_steps_python_twisted.Trial.test_run_jobsProperties ... [FAILURE]
                '''))
        return self.runStep()

    def testProperties(self):
        self.setupStep(python_twisted.Trial(workdir='build',
                                            tests=Property('test_list'),
                                            testpath=None))
        self.properties.setProperty('test_list', ['testname'], 'Test')

        self.expectCommands(
            ExpectShell(workdir='build',
                        command=['trial', '--reporter=bwverbose', 'testname'],
                        logfiles={'test.log': '_trial_temp/test.log'})
            + ExpectShell.log('stdio', stdout="Ran 2 tests\n")
            + 0
        )
        self.expectOutcome(result=SUCCESS, state_string='2 tests passed')
        return self.runStep()

    def test_run_jobs(self):
        """
        The C{jobs} kwarg should correspond to trial's -j option (
        included since Twisted 12.3.0), and make corresponding changes to
        logfiles.
        """
        self.setupStep(python_twisted.Trial(workdir='build',
                                            tests='testname',
                                            testpath=None,
                                            jobs=2))

        self.expectCommands(
            ExpectShell(workdir='build',
                        command=['trial', '--reporter=bwverbose', '--jobs=2',
                                 'testname'],
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
        self.expectOutcome(result=SUCCESS, state_string='1 test passed')
        return self.runStep()

    def test_run_jobsProperties(self):
        """
        C{jobs} should accept Properties
        """
        self.setupStep(python_twisted.Trial(workdir='build',
                                            tests='testname',
                                            jobs=Property('jobs_count'),
                                            testpath=None))
        self.properties.setProperty('jobs_count', '2', 'Test')

        self.expectCommands(
            ExpectShell(workdir='build',
                        command=['trial', '--reporter=bwverbose', '--jobs=2',
                                 'testname'],
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
        self.expectOutcome(result=SUCCESS, state_string='1 test passed')
        return self.runStep()


class HLint(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_run_ok(self):
        self.setupStep(python_twisted.HLint(workdir='build'),
                       buildFiles=['foo.xhtml'])
        self.expectCommands(
            ExpectShell(workdir='build',
                        command=[
                            'bin/lore', '-p', '--output', 'lint', 'foo.xhtml'],)
            +
            ExpectShell.log(
                'stdio', stdout="dunno what hlint output looks like..\n")
            + 0
        )
        self.expectLogfile('files', 'foo.xhtml\n')
        self.expectOutcome(result=SUCCESS, state_string='hlint')
        return self.runStep()

    def test_run_warnings(self):
        self.setupStep(python_twisted.HLint(workdir='build'),
                       buildFiles=['foo.xhtml'])
        self.expectCommands(
            ExpectShell(workdir='build',
                        command=[
                            'bin/lore', '-p', '--output', 'lint', 'foo.xhtml'])
            + ExpectShell.log('stdio', stdout="colon: meaning warning\n")
            + 0
        )
        self.expectLogfile('warnings', 'colon: meaning warning')
        self.expectOutcome(result=WARNINGS, state_string='hlint (warnings)')
        return self.runStep()
