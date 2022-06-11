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

from buildbot.test.steps import ExpectMasterShell
from buildbot.test.steps import _check_env_is_expected
from buildbot.util import runprocess


class MasterRunProcessMixin:
    long_message = True

    def setup_master_run_process(self):
        self._master_run_process_patched = False
        self._expected_master_commands = []
        self._master_run_process_expect_env = {}

    def assert_all_commands_ran(self):
        self.assertEqual(self._expected_master_commands, [],
                         "assert all expected commands were run")

    def patched_run_process(self, reactor, command, workdir=None, env=None,
                            collect_stdout=True, collect_stderr=True, stderr_is_error=False,
                            io_timeout=300, runtime_timeout=3600, sigterm_timeout=5,
                            initial_stdin=None, use_pty=False):

        _check_env_is_expected(self, self._master_run_process_expect_env, env)

        if not self._expected_master_commands:
            self.fail(f"got command {command} when no further commands were expected")

        expect = self._expected_master_commands.pop(0)

        rc, stdout, stderr = expect._check(self, command, workdir, env)

        if not collect_stderr and stderr_is_error and stderr:
            rc = -1

        if collect_stdout and collect_stderr:
            return (rc, stdout, stderr)
        if collect_stdout:
            return (rc, stdout)
        if collect_stderr:
            return (rc, stderr)
        return rc

    def _patch_runprocess(self):
        if not self._master_run_process_patched:
            self.patch(runprocess, "run_process", self.patched_run_process)
            self._master_run_process_patched = True

    def add_run_process_expect_env(self, d):
        self._master_run_process_expect_env.update(d)

    def expect_commands(self, *exp):
        for e in exp:
            if not isinstance(e, ExpectMasterShell):
                raise Exception('All expectation must be an instance of ExpectMasterShell')

        self._patch_runprocess()
        self._expected_master_commands.extend(exp)
