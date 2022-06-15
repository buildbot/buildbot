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
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import ExpectShell
from buildbot.test.steps import TestBuildStepMixin

try:
    import unidiff
except ImportError:
    unidiff = None


class TestDiffInfo(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):
    if not unidiff:
        skip = 'unidiff is required for GitDiffInfo tests'

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_merge_base_failure(self):
        self.setup_step(gitdiffinfo.GitDiffInfo())
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['git', 'merge-base', 'HEAD', 'master'])
            .log('stdio-merge-base', stderr='fatal: Not a valid object name')
            .exit(128))
        self.expect_log_file_stderr('stdio-merge-base', 'fatal: Not a valid object name\n')
        self.expect_outcome(result=results.FAILURE, state_string="GitDiffInfo (failure)")
        return self.run_step()

    def test_diff_failure(self):
        self.setup_step(gitdiffinfo.GitDiffInfo())
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['git', 'merge-base', 'HEAD', 'master'])
            .log('stdio-merge-base', stdout='1234123412341234')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'diff', '--no-prefix', '-U0', '1234123412341234', 'HEAD'])
            .log('stdio-diff', stderr='fatal: ambiguous argument')
            .exit(1),
            )
        self.expect_log_file('stdio-merge-base', '1234123412341234')
        self.expect_log_file_stderr('stdio-diff', 'fatal: ambiguous argument\n')
        self.expect_outcome(result=results.FAILURE, state_string="GitDiffInfo (failure)")
        return self.run_step()

    def test_empty_diff(self):
        self.setup_step(gitdiffinfo.GitDiffInfo())
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['git', 'merge-base', 'HEAD', 'master'])
            .log('stdio-merge-base', stdout='1234123412341234')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'diff', '--no-prefix', '-U0', '1234123412341234', 'HEAD'])
            .log('stdio-diff', stdout='')
            .exit(0),
            )
        self.expect_log_file('stdio-merge-base', '1234123412341234')
        self.expect_log_file_stderr('stdio-diff', '')
        self.expect_outcome(result=results.SUCCESS, state_string="GitDiffInfo")
        self.expect_build_data('diffinfo-master', b'[]', 'GitDiffInfo')
        return self.run_step()

    def test_complex_diff(self):
        self.setup_step(gitdiffinfo.GitDiffInfo())
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['git', 'merge-base', 'HEAD', 'master'])
            .log('stdio-merge-base', stdout='1234123412341234')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'diff', '--no-prefix', '-U0', '1234123412341234', 'HEAD'])
            .log('stdio-diff', stdout='''\
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
            .exit(0)
            )
        self.expect_log_file('stdio-merge-base', '1234123412341234')
        self.expect_outcome(result=results.SUCCESS, state_string="GitDiffInfo")

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
        return self.run_step()
