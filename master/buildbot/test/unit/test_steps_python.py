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

from buildbot.status.results import FAILURE, SUCCESS
from buildbot.steps import python
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.util import steps


class PyLint(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_success(self):
        self.setupStep(python.PyLint(command=['pylint']))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['pylint'],
                        usePTY='slave-config')
            + ExpectShell.log('stdio',
                              stdout='Your code has been rated at 10/10')
            + python.PyLint.RC_OK)
        self.expectOutcome(result=SUCCESS, status_text=['pylint'])
        return self.runStep()

    def test_error(self):
        self.setupStep(python.PyLint(command=['pylint']))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['pylint'],
                        usePTY='slave-config')
            + ExpectShell.log(
                'stdio',
                stdout=('W: 11: Bad indentation. Found 6 spaces, expected 4\n'
                        'E: 12: Undefined variable \'foo\'\n'))
            + (python.PyLint.RC_WARNING|python.PyLint.RC_ERROR))
        self.expectOutcome(result=FAILURE,
                           status_text=['pylint', 'error=1', 'warning=1',
                                        'failed'])
        self.expectProperty('pylint-warning', 1)
        self.expectProperty('pylint-error', 1)
        return self.runStep()

    def test_failure(self):
        self.setupStep(python.PyLint(command=['pylint']))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['pylint'],
                        usePTY='slave-config')
            + ExpectShell.log(
                'stdio',
                stdout=('W: 11: Bad indentation. Found 6 spaces, expected 4\n'
                        'F: 13: something really strange happened\n'))
            + (python.PyLint.RC_WARNING|python.PyLint.RC_FATAL))
        self.expectOutcome(result=FAILURE,
                           status_text=['pylint', 'fatal=1', 'warning=1',
                                        'failed'])
        self.expectProperty('pylint-warning', 1)
        self.expectProperty('pylint-fatal', 1)
        return self.runStep()

    def test_failure_zero_returncode(self):
        # Make sure that errors result in a failed step when pylint's
        # return code is 0, e.g. when run through a wrapper script.
        self.setupStep(python.PyLint(command=['pylint']))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['pylint'],
                        usePTY='slave-config')
            + ExpectShell.log(
                'stdio',
                stdout=('W: 11: Bad indentation. Found 6 spaces, expected 4\n'
                        'E: 12: Undefined variable \'foo\'\n'))
            + 0)
        self.expectOutcome(result=FAILURE,
                           status_text=['pylint', 'error=1', 'warning=1',
                                        'failed'])
        self.expectProperty('pylint-warning', 1)
        self.expectProperty('pylint-error', 1)
        return self.runStep()

