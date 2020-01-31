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

from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.steps.ctest import CTest
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.util.misc import TestReactorMixin
from buildbot.test.util.steps import BuildStepMixin


class TestCTest(BuildStepMixin, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_default_command(self):
        # nothing too exciting here, but at least make sure the class is
        # present
        step = CTest()
        self.assertEqual(step.command, ['ctest', '--output-on-failure'])

    def test_success(self):
        step = CTest()
        self.setupStep(step)
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=[
                'ctest', '--output-on-failure']) +
            ExpectShell.log('stdio', stdout='        Start 53: python_test_docstrings\n'
                                            '53/53 Test #53: python_test_docstrings'
                                            ' .....................................   Passed    0.16 sec\n'
                                            '100% tests passed, 0 tests failed out of 53\n'
                                            'Total Test time (real) =   8.23 sec\n') +
            0)
        self.expectOutcome(result=SUCCESS, state_string="53 tests 53 passed")
        return self.runStep()

    def test_failure(self):
        step = CTest()
        self.setupStep(step)
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=[
                'ctest', '--output-on-failure']) +
            ExpectShell.log('stdio', stdout='        Start 53: python_test_docstrings\n'
                                            '53/53 Test #53: python_test_docstrings'
                                            ' .....................................   Passed    0.16 sec\n'
                                            '98% tests passed, 1 tests failed out of 53\n'
                                            'Total Test time (real) =  10.48 sec\n'
                                            'The following tests FAILED:\n'
                                            '      9 - entities_unit_test_model (SEGFAULT)\n',
                            stderr='Errors while running CTest\n') +
            0)
        self.expectOutcome(result=FAILURE, state_string="53 tests 52 passed 1 failed (failure)")
        return self.runStep()

    def test_not_ctest_output(self):
        step = CTest()
        self.setupStep(step)
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=[
                'ctest', '--output-on-failure']) +
            ExpectShell.log('stdio', stdout='Output not from CTest.') +
            0)
        self.expectOutcome(result=FAILURE, state_string="unit test (failure)")
        return self.runStep()
