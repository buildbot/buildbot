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

from buildbot.process import results
from buildbot.steps import gitdiffinfo
from buildbot.test.fake.remotecommand import Expect
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.util import steps
from buildbot.test.util.misc import TestReactorMixin


class TestDiffInfo(steps.BuildStepMixin, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_merge_base_failure(self):
        self.setupStep(gitdiffinfo.GitDiffInfo())
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['git', 'merge-base', 'HEAD', 'master'])
            + Expect.log('stdio-merge-base', stderr='fatal: Not a valid object name')
            + 128)
        self.expect_log_file_stderr('stdio-merge-base', 'fatal: Not a valid object name')
        self.expectOutcome(result=results.FAILURE, state_string="GitDiffInfo (failure)")
        return self.runStep()

    def test_diff_failure(self):
        self.setupStep(gitdiffinfo.GitDiffInfo())
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['git', 'merge-base', 'HEAD', 'master'])
            + Expect.log('stdio-merge-base', stdout='1234123412341234')
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'diff', '--no-prefix', '-U0', '1234123412341234', 'HEAD'])
            + Expect.log('stdio-diff', stderr='fatal: ambiguous argument')
            + 1,
            )
        self.expectLogfile('stdio-merge-base', '1234123412341234')
        self.expect_log_file_stderr('stdio-diff', 'fatal: ambiguous argument')
        self.expectOutcome(result=results.FAILURE, state_string="GitDiffInfo (failure)")
        return self.runStep()

    def test_empty_diff(self):
        self.setupStep(gitdiffinfo.GitDiffInfo())
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['git', 'merge-base', 'HEAD', 'master'])
            + Expect.log('stdio-merge-base', stdout='1234123412341234')
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'diff', '--no-prefix', '-U0', '1234123412341234', 'HEAD'])
            + Expect.log('stdio-diff', stdout='')
            + 0,
            )
        self.expectLogfile('stdio-merge-base', '1234123412341234')
        self.expect_log_file_stderr('stdio-diff', '')
        self.expectOutcome(result=results.SUCCESS, state_string="GitDiffInfo")
        self.expect_build_data('diffinfo-master', b'[]', 'GitDiffInfo')
        return self.runStep()

    def test_complex_diff(self):
        self.setupStep(gitdiffinfo.GitDiffInfo())
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['git', 'merge-base', 'HEAD', 'master'])
            + Expect.log('stdio-merge-base', stdout='1234123412341234')
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'diff', '--no-prefix', '-U0', '1234123412341234', 'HEAD'])
            + Expect.log('stdio-diff', stdout='''\
diff --git file1 file1
deleted file mode 100644
index 42f90fd..0000000
--- file1
+++ /dev/null
@@ -1,3 +0,0 @@
-line11
-line12
-line13
diff --git file2 file2
index c337bf1..1cb02b9 100644
--- file2
+++ file2
@@ -4,0 +5,3 @@ line24
+line24n
+line24n2
+line24n3
@@ -15,0 +19,3 @@ line215
+line215n
+line215n2
+line215n3
diff --git file3 file3
new file mode 100644
index 0000000..632e269
--- /dev/null
+++ file3
@@ -0,0 +1,3 @@
+line31
+line32
+line33
''')
            + 0,
            )
        self.expectLogfile('stdio-merge-base', '1234123412341234')
        self.expectOutcome(result=results.SUCCESS, state_string="GitDiffInfo")

        diff_info = (
            b'[{"source_file": "file1", "target_file": "/dev/null", ' +
            b'"is_binary": false, "is_rename": false, ' +
            b'"hunks": [{"ss": 1, "sl": 3, "ts": 0, "tl": 0}]}, ' +
            b'{"source_file": "file2", "target_file": "file2", ' +
            b'"is_binary": false, "is_rename": false, ' +
            b'"hunks": [{"ss": 4, "sl": 0, "ts": 5, "tl": 3}, ' +
            b'{"ss": 15, "sl": 0, "ts": 19, "tl": 3}]}, ' +
            b'{"source_file": "/dev/null", "target_file": "file3", ' +
            b'"is_binary": false, "is_rename": false, ' +
            b'"hunks": [{"ss": 0, "sl": 0, "ts": 1, "tl": 3}]}]')
        self.expect_build_data('diffinfo-master', diff_info, 'GitDiffInfo')
        return self.runStep()
