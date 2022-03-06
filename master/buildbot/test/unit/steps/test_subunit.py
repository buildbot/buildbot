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
import re
import sys

from twisted.trial import unittest

from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.steps import subunit
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import ExpectShell
from buildbot.test.steps import TestBuildStepMixin

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


class TestSubUnit(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        if TestProtocolClient is None:
            raise unittest.SkipTest("Need to install python-subunit to test subunit step")

        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_empty(self):
        self.setup_step(subunit.SubunitShellCommand(command='test'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command="test")
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS,
                           state_string="shell no tests run")
        return self.run_step()

    def test_empty_error(self):
        self.setup_step(subunit.SubunitShellCommand(command='test',
                                                   failureOnNoTests=True))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command="test")
            .exit(0)
        )
        self.expect_outcome(result=FAILURE,
                           state_string="shell no tests run (failure)")
        return self.run_step()

    def test_success(self):
        stream = io.BytesIO()
        client = TestProtocolClient(stream)
        test = FakeTest(id='test1')
        client.startTest(test)
        client.stopTest(test)

        self.setup_step(subunit.SubunitShellCommand(command='test'))
        self.expect_commands(
            ExpectShell(workdir='wkdir', command="test")
            .stdout(stream.getvalue())
            .exit(0)
        )

        self.expect_outcome(result=SUCCESS, state_string="shell 1 test passed")
        return self.run_step()

    def test_error(self):
        stream = io.BytesIO()
        client = TestProtocolClient(stream)
        test = FakeTest(id='test1')
        client.startTest(test)
        client.addError(test, create_error('error1'))
        client.stopTest(test)

        self.setup_step(subunit.SubunitShellCommand(command='test'))
        self.expect_commands(
            ExpectShell(workdir='wkdir', command="test")
            .stdout(stream.getvalue())
            .exit(0)
        )

        self.expect_outcome(result=FAILURE, state_string="shell Total 1 test(s) 1 error (failure)")
        self.expect_log_file('problems', re.compile(r'''test1
testtools.testresult.real._StringException:.*ValueError: invalid literal for int\(\) with base 10: '_error1'
.*''', re.MULTILINE | re.DOTALL))  # noqa pylint: disable=line-too-long
        return self.run_step()

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

        self.setup_step(subunit.SubunitShellCommand(command='test'))
        self.expect_commands(
            ExpectShell(workdir='wkdir', command="test")
            .stdout(stream.getvalue())
            .exit(0)
        )

        self.expect_outcome(result=FAILURE, state_string="shell Total 2 test(s) 2 errors (failure)")
        self.expect_log_file('problems', re.compile(r'''test1
testtools.testresult.real._StringException:.*ValueError: invalid literal for int\(\) with base 10: '_error1'

test2
testtools.testresult.real._StringException:.*ValueError: invalid literal for int\(\) with base 10: '_error2'
.*''', re.MULTILINE | re.DOTALL))  # noqa pylint: disable=line-too-long
        return self.run_step()

    def test_warnings(self):
        stream = io.BytesIO()
        client = TestProtocolClient(stream)
        test1 = FakeTest(id='test1')
        test2 = FakeTest(id='test2')
        client.startTest(test1)
        client.stopTest(test1)
        client.addError(test2, create_error('error2'))
        client.stopTest(test2)

        self.setup_step(subunit.SubunitShellCommand(command='test'))
        self.expect_commands(
            ExpectShell(workdir='wkdir', command="test")
            .stdout(stream.getvalue())
            .exit(0)
        )

        self.expect_outcome(result=SUCCESS,  # N.B. not WARNINGS
                           state_string="shell 1 test passed")
        # note that the warnings list is ignored..
        self.expect_log_file('warnings', re.compile(r'''error: test2 \[.*
ValueError: invalid literal for int\(\) with base 10: '_error2'
\]
''', re.MULTILINE | re.DOTALL))  # noqa pylint: disable=line-too-long
        return self.run_step()
