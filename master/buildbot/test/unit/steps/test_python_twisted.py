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

import textwrap

from twisted.trial import unittest

from buildbot.process.properties import Property
from buildbot.process.results import FAILURE
from buildbot.process.results import SKIPPED
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.steps import python_twisted
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import ExpectShell
from buildbot.test.steps import TestBuildStepMixin

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
'''  # noqa pylint: disable=line-too-long


class Trial(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_run_env(self):
        self.setup_step(
            python_twisted.Trial(workdir='build',
                                 tests='testname',
                                 testpath=None,
                                 env={'PYTHONPATH': 'somepath'}))
        self.expect_commands(
            ExpectShell(workdir='build',
                        command=['trial', '--reporter=bwverbose', 'testname'],
                        logfiles={'test.log': '_trial_temp/test.log'},
                        env=dict(PYTHONPATH='somepath'))
            .stdout("Ran 0 tests\n")
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string='no tests run')
        return self.run_step()

    def test_run_env_supplement(self):
        self.setup_step(
            python_twisted.Trial(workdir='build',
                                 tests='testname',
                                 testpath='path1',
                                 env={'PYTHONPATH': ['path2', 'path3']}))
        self.expect_commands(
            ExpectShell(workdir='build',
                        command=['trial', '--reporter=bwverbose', 'testname'],
                        logfiles={'test.log': '_trial_temp/test.log'},
                        env=dict(PYTHONPATH=['path1', 'path2', 'path3']))
            .stdout("Ran 0 tests\n")
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string='no tests run')
        return self.run_step()

    def test_run_env_nodupe(self):
        self.setup_step(
            python_twisted.Trial(workdir='build',
                                 tests='testname',
                                 testpath='path2',
                                 env={'PYTHONPATH': ['path1', 'path2']}))
        self.expect_commands(
            ExpectShell(workdir='build',
                        command=['trial', '--reporter=bwverbose', 'testname'],
                        logfiles={'test.log': '_trial_temp/test.log'},
                        env=dict(PYTHONPATH=['path1', 'path2']))
            .stdout("Ran 0 tests\n")
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string='no tests run')
        return self.run_step()

    def test_run_singular(self):
        self.setup_step(
            python_twisted.Trial(workdir='build',
                                 tests='testname',
                                 testpath=None))
        self.expect_commands(
            ExpectShell(workdir='build',
                        command=['trial', '--reporter=bwverbose', 'testname'],
                        logfiles={'test.log': '_trial_temp/test.log'})
            .stdout("Ran 1 tests\n")
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string='1 test passed')
        return self.run_step()

    def test_run_plural(self):
        self.setup_step(
            python_twisted.Trial(workdir='build',
                                 tests='testname',
                                 testpath=None))
        self.expect_commands(
            ExpectShell(workdir='build',
                        command=['trial', '--reporter=bwverbose', 'testname'],
                        logfiles={'test.log': '_trial_temp/test.log'})
            .stdout("Ran 2 tests\n")
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string='2 tests passed')
        return self.run_step()

    def test_run_failure(self):
        self.setup_step(
            python_twisted.Trial(workdir='build',
                                 tests='testname',
                                 testpath=None))
        self.expect_commands(
            ExpectShell(workdir='build',
                        command=['trial', '--reporter=bwverbose', 'testname'],
                        logfiles={'test.log': '_trial_temp/test.log'})
            .stdout(failureLog)
            .exit(1)
        )
        self.expect_outcome(
            result=FAILURE, state_string='tests 8 failures (failure)')
        self.expect_log_file('problems', failureLog.split('\n\n', 1)[1][:-1] +
                             '\nprogram finished with exit code 1')
        self.expect_log_file('warnings', textwrap.dedent('''\
                buildbot.test.unit.test_steps_python_twisted.Trial.test_run_env_nodupe ... [FAILURE]/home/dustin/code/buildbot/t/buildbot/master/buildbot/test/fake/logfile.py:92: UserWarning: step uses removed LogFile method `getText`
                buildbot.test.unit.test_steps_python_twisted.Trial.test_run_env_supplement ... [FAILURE]/home/dustin/code/buildbot/t/buildbot/master/buildbot/test/fake/logfile.py:92: UserWarning: step uses removed LogFile method `getText`
                buildbot.test.unit.test_steps_python_twisted.Trial.test_run_jobs ... [FAILURE]/home/dustin/code/buildbot/t/buildbot/master/buildbot/test/fake/logfile.py:92: UserWarning: step uses removed LogFile method `getText`
                buildbot.test.unit.test_steps_python_twisted.Trial.test_run_jobsProperties ... [FAILURE]
                '''))  # noqa pylint: disable=line-too-long
        return self.run_step()

    def test_renderable_properties(self):
        self.setup_step(python_twisted.Trial(workdir='build',
                                            tests=Property('test_list'),
                                            testpath=None))
        self.properties.setProperty('test_list', ['testname'], 'Test')

        self.expect_commands(
            ExpectShell(workdir='build',
                        command=['trial', '--reporter=bwverbose', 'testname'],
                        logfiles={'test.log': '_trial_temp/test.log'})
            .stdout("Ran 2 tests\n")
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string='2 tests passed')
        return self.run_step()

    def test_build_changed_files(self):
        self.setup_step(python_twisted.Trial(workdir='build', testChanges=True, testpath=None),
                        build_files=['my/test/file.py', 'my/test/file2.py'])

        self.expect_commands(
            ExpectShell(workdir='build',
                        command=['trial', '--reporter=bwverbose', '--testmodule=my/test/file.py',
                                 '--testmodule=my/test/file2.py'],
                        logfiles={'test.log': '_trial_temp/test.log'})
            .stdout("Ran 2 tests\n")
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string='2 tests passed')
        return self.run_step()

    def test_test_path_env_python_path(self):
        self.setup_step(python_twisted.Trial(workdir='build', tests='testname',
                                            testpath='custom/test/path',
                                            env={'PYTHONPATH': '/existing/pypath'}))

        self.expect_commands(
            ExpectShell(workdir='build',
                        command=['trial', '--reporter=bwverbose', 'testname'],
                        logfiles={'test.log': '_trial_temp/test.log'},
                        env={'PYTHONPATH': ['custom/test/path', '/existing/pypath']})
            .stdout("Ran 2 tests\n")
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string='2 tests passed')
        return self.run_step()

    def test_custom_reactor(self):
        self.setup_step(python_twisted.Trial(workdir='build', reactor='customreactor',
                                            tests='testname', testpath=None))

        self.expect_commands(
            ExpectShell(workdir='build',
                        command=['trial', '--reporter=bwverbose', '--reactor=customreactor',
                                 'testname'],
                        logfiles={'test.log': '_trial_temp/test.log'})
            .stdout("Ran 2 tests\n")
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string='2 tests passed (custom)')
        return self.run_step()

    def test_custom_python(self):
        self.setup_step(python_twisted.Trial(workdir='build', tests='testname',
                                            python='/bin/mypython', testpath=None))

        self.expect_commands(
            ExpectShell(workdir='build',
                        command=['/bin/mypython', 'trial', '--reporter=bwverbose', 'testname'],
                        logfiles={'test.log': '_trial_temp/test.log'})
            .stdout("Ran 2 tests\n")
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string='2 tests passed')
        return self.run_step()

    def test_randomly(self):
        self.setup_step(python_twisted.Trial(workdir='build',
                                            randomly=True,
                                            tests='testname',
                                            testpath=None))

        self.expect_commands(
            ExpectShell(workdir='build',
                        command=['trial', '--reporter=bwverbose', '--random=0', 'testname'],
                        logfiles={'test.log': '_trial_temp/test.log'})
            .stdout("Ran 2 tests\n")
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string='2 tests passed')
        return self.run_step()

    def test_run_jobs(self):
        """
        The C{jobs} kwarg should correspond to trial's -j option (
        included since Twisted 12.3.0), and make corresponding changes to
        logfiles.
        """
        self.setup_step(python_twisted.Trial(workdir='build',
                                            tests='testname',
                                            testpath=None,
                                            jobs=2))

        self.expect_commands(
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
            .stdout("Ran 1 tests\n")
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string='1 test passed')
        return self.run_step()

    def test_run_jobsProperties(self):
        """
        C{jobs} should accept Properties
        """
        self.setup_step(python_twisted.Trial(workdir='build',
                                            tests='testname',
                                            jobs=Property('jobs_count'),
                                            testpath=None))
        self.properties.setProperty('jobs_count', '2', 'Test')

        self.expect_commands(
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
            .stdout("Ran 1 tests\n")
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string='1 test passed')
        return self.run_step()


class HLint(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_run_ok(self):
        self.setup_step(python_twisted.HLint(workdir='build'),
                        build_files=['foo.xhtml'])
        self.expect_commands(
            ExpectShell(workdir='build',
                        command=[
                            'bin/lore', '-p', '--output', 'lint', 'foo.xhtml'],)
            .stdout("dunno what hlint output looks like..\n")
            .exit(0)
        )
        self.expect_log_file('files', 'foo.xhtml\n')
        self.expect_outcome(result=SUCCESS, state_string='0 hlints')
        return self.run_step()

    def test_custom_python(self):
        self.setup_step(python_twisted.HLint(workdir='build', python='/bin/mypython'),
                        build_files=['foo.xhtml'])
        self.expect_commands(
            ExpectShell(workdir='build',
                        command=['/bin/mypython', 'bin/lore', '-p', '--output', 'lint',
                                 'foo.xhtml'])
            .exit(0)
        )
        self.expect_log_file('files', 'foo.xhtml\n')
        self.expect_outcome(result=SUCCESS, state_string='0 hlints')
        return self.run_step()

    def test_command_failure(self):
        self.setup_step(python_twisted.HLint(workdir='build'),
                        build_files=['foo.xhtml'])
        self.expect_commands(
            ExpectShell(workdir='build',
                        command=['bin/lore', '-p', '--output', 'lint', 'foo.xhtml'],)
            .exit(1)
        )
        self.expect_log_file('files', 'foo.xhtml\n')
        self.expect_outcome(result=FAILURE, state_string='hlint (failure)')
        return self.run_step()

    def test_no_build_files(self):
        self.setup_step(python_twisted.HLint(workdir='build'))
        self.expect_outcome(result=SKIPPED, state_string='hlint (skipped)')
        return self.run_step()

    def test_run_warnings(self):
        self.setup_step(python_twisted.HLint(workdir='build'),
                        build_files=['foo.xhtml'])
        self.expect_commands(
            ExpectShell(workdir='build',
                        command=[
                            'bin/lore', '-p', '--output', 'lint', 'foo.xhtml'])
            .stdout("colon: meaning warning\n")
            .exit(0)
        )
        self.expect_log_file('warnings', 'colon: meaning warning')
        self.expect_outcome(result=WARNINGS, state_string='1 hlint (warnings)')
        return self.run_step()


class RemovePYCs(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_run_ok(self):
        self.setup_step(python_twisted.RemovePYCs())
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['find', '.', '-name', '\'*.pyc\'', '-exec', 'rm', '{}', ';'])
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string='remove .pycs')
        return self.run_step()
