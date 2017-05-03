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
from future.builtins import range

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.process.results import Results
from buildbot.steps import mswin
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.util import steps


class TestRobocopySimple(steps.BuildStepMixin, unittest.TestCase):

    """
    Test L{Robocopy} command building.
    """

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def _run_simple_test(self, source, destination, expected_args=None, expected_code=0, expected_res=SUCCESS, **kwargs):
        s = mswin.Robocopy(source, destination, **kwargs)
        self.setupStep(s)
        s.rendered = True

        command = ['robocopy', source, destination]
        if expected_args:
            command += expected_args
        command += ['/TEE', '/NP']
        self.expectCommands(
            ExpectShell(
                workdir='wkdir',
                command=command,
            ) +
            expected_code
        )
        state_string = "'robocopy %s ...'" % source
        if expected_res != SUCCESS:
            state_string += ' (%s)' % (Results[expected_res])
        self.expectOutcome(result=expected_res, state_string=state_string)
        return self.runStep()

    def test_copy(self):
        return self._run_simple_test(r'D:\source', r'E:\dest')

    def test_copy_files(self):
        return self._run_simple_test(
            r'D:\source', r'E:\dest', files=['a.txt', 'b.txt', '*.log'],
            expected_args=['a.txt', 'b.txt', '*.log']
        )

    def test_copy_recursive(self):
        return self._run_simple_test(
            r'D:\source', r'E:\dest', recursive=True,
            expected_args=['/E']
        )

    def test_mirror_files(self):
        return self._run_simple_test(
            r'D:\source', r'E:\dest', files=['*.foo'], mirror=True,
            expected_args=['*.foo', '/MIR']
        )

    def test_move_files(self):
        return self._run_simple_test(
            r'D:\source', r'E:\dest', files=['*.foo'], move=True,
            expected_args=['*.foo', '/MOVE']
        )

    def test_exclude(self):
        return self._run_simple_test(
            r'D:\source', r'E:\dest',
            files=['blah*'], exclude=['*.foo', '*.bar'],
            expected_args=['blah*', '/XF', '*.foo', '*.bar']
        )

    def test_exclude_files(self):
        return self._run_simple_test(
            r'D:\source', r'E:\dest', files=['blah*'],
            exclude_files=['*.foo', '*.bar'],
            expected_args=['blah*', '/XF', '*.foo', '*.bar']
        )

    def test_exclude_dirs(self):
        return self._run_simple_test(
            r'D:\source', r'E:\dest', files=['blah*'],
            exclude_dirs=['foo', 'bar'],
            expected_args=['blah*', '/XD', 'foo', 'bar']
        )

    def test_custom_opts(self):
        return self._run_simple_test(
            r'D:\source', r'E:\dest', files=['*.foo'], custom_opts=['/R:10', '/W:60'],
            expected_args=['*.foo', '/R:10', '/W:60']
        )

    def test_verbose_output(self):
        return self._run_simple_test(
            r'D:\source', r'E:\dest', files=['*.foo'], verbose=True,
            expected_args=['*.foo', '/V', '/TS', '/FP']
        )

    @defer.inlineCallbacks
    def test_codes(self):
        # Codes that mean uneventful copies (including no copy at all).
        for i in [0, 1]:
            yield self._run_simple_test(
                r'D:\source', r'E:\dest', expected_code=i,
                expected_res=SUCCESS
            )

        # Codes that mean some mismatched or extra files were found.
        for i in range(2, 8):
            yield self._run_simple_test(
                r'D:\source', r'E:\dest', expected_code=i,
                expected_res=WARNINGS
            )
        # Codes that mean errors have been encountered.
        for i in range(8, 32):
            yield self._run_simple_test(
                r'D:\source', r'E:\dest', expected_code=i,
                expected_res=FAILURE
            )

        # bit 32 is meaningless
        yield self._run_simple_test(
            r'D:\source', r'E:\dest', expected_code=32,
            expected_res=EXCEPTION
        )
