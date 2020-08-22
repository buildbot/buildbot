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

import io
import sys

from twisted.trial import unittest

from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.steps import subunit
from buildbot.test.fake.remotecommand import Expect
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.util import steps
from buildbot.test.util.misc import TestReactorMixin

try:
    from subunit import TestProtocolClient
except ImportError:
    TestProtocolClient = None


class FakeTest:
    def __init__(self, id):
        self._id = id

    def id(self):
        return self._id


def create_error(name):
    try:
        int('_' + name)
        return None
    except ValueError:
        # We don't want traceback lines with real paths in the logs
        exctype, value, _ = sys.exc_info()
        return (exctype, value, None)


class TestSubUnit(steps.BuildStepMixin, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        if TestProtocolClient is None:
            raise unittest.SkipTest("Need to install python-subunit to test subunit step")

        self.setUpTestReactor()
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_empty(self):
        self.setupStep(subunit.SubunitShellCommand(command='test'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command="test")
            + 0
        )
        self.expectOutcome(result=SUCCESS,
                           state_string="shell no tests run")
        return self.runStep()

    def test_empty_error(self):
        self.setupStep(subunit.SubunitShellCommand(command='test',
                                                   failureOnNoTests=True))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command="test")
            + 0
        )
        self.expectOutcome(result=FAILURE,
                           state_string="shell no tests run (failure)")
        return self.runStep()

    def test_success(self):
        stream = io.BytesIO()
        client = TestProtocolClient(stream)
        test = FakeTest(id='test1')
        client.startTest(test)
        client.stopTest(test)

        self.setupStep(subunit.SubunitShellCommand(command='test'))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command="test")
            + Expect.log('stdio', stdout=stream.getvalue())
            + 0
        )

        self.expectOutcome(result=SUCCESS, state_string="shell 1 test passed")
        return self.runStep()

    def test_error(self):
        stream = io.BytesIO()
        client = TestProtocolClient(stream)
        test = FakeTest(id='test1')
        client.startTest(test)
        client.addError(test, create_error('error1'))
        client.stopTest(test)

        self.setupStep(subunit.SubunitShellCommand(command='test'))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command="test")
            + Expect.log('stdio', stdout=stream.getvalue())
            + 0
        )

        self.expectOutcome(result=FAILURE, state_string="shell Total 1 test(s) 1 error (failure)")
        self.expectLogfile('problems', '''\
test1
testtools.testresult.real._StringException: Traceback (most recent call last):
ValueError: invalid literal for int() with base 10: '_error1'

''')
        return self.runStep()

    def test_multiple_errors(self):
        stream = io.BytesIO()
        client = TestProtocolClient(stream)
        test1 = FakeTest(id='test1')
        test2 = FakeTest(id='test2')
        client.startTest(test1)
        client.addError(test1, create_error('error1'))
        client.stopTest(test1)
        client.startTest(test2)
        client.addError(test2, create_error('error2'))
        client.stopTest(test2)

        self.setupStep(subunit.SubunitShellCommand(command='test'))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command="test")
            + Expect.log('stdio', stdout=stream.getvalue())
            + 0
        )

        self.expectOutcome(result=FAILURE, state_string="shell Total 2 test(s) 2 errors (failure)")
        self.expectLogfile('problems', '''\
test1
testtools.testresult.real._StringException: Traceback (most recent call last):
ValueError: invalid literal for int() with base 10: '_error1'

test2
testtools.testresult.real._StringException: Traceback (most recent call last):
ValueError: invalid literal for int() with base 10: '_error2'

''')
        return self.runStep()

    def test_warnings(self):
        stream = io.BytesIO()
        client = TestProtocolClient(stream)
        test1 = FakeTest(id='test1')
        test2 = FakeTest(id='test2')
        client.startTest(test1)
        client.stopTest(test1)
        client.addError(test2, create_error('error2'))
        client.stopTest(test2)

        self.setupStep(subunit.SubunitShellCommand(command='test'))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command="test")
            + Expect.log('stdio', stdout=stream.getvalue())
            + 0
        )

        self.expectOutcome(result=SUCCESS,  # N.B. not WARNINGS
                           state_string="shell 1 test passed")
        # note that the warnings list is ignored..
        self.expectLogfile('warnings', '''\
error: test2 [
Traceback (most recent call last):
ValueError: invalid literal for int() with base 10: '_error2'
]
''')
        return self.runStep()
