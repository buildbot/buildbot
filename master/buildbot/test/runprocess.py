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
from __future__ import annotations

from typing import TYPE_CHECKING

from twisted.internet import defer

from buildbot.test.steps import ExpectMasterShell
from buildbot.test.steps import _check_env_is_expected
from buildbot.util import runprocess

if TYPE_CHECKING:
    from twisted.internet.interfaces import IReactorProcess
    from twisted.internet.interfaces import IReactorTime
    from twisted.trial import unittest

    _MasterRunProcessMixinBase = unittest.TestCase
else:
    _MasterRunProcessMixinBase = object


class MasterRunProcessMixin(_MasterRunProcessMixinBase):
    long_message = True

    def setup_master_run_process(self) -> None:
        self._master_run_process_patched = False
        self._expected_master_commands: list[ExpectMasterShell] = []
        self._master_run_process_expect_env: dict[str, str] = {}

    def assert_all_commands_ran(self) -> None:
        self.assertEqual(
            self._expected_master_commands, [], "assert all expected commands were run"
        )

    def patched_run_process(
        self,
        reactor: IReactorTime | IReactorProcess,
        command: list[str],
        workdir: str | None = None,
        env: dict[str, str] | None = None,
        collect_stdout: bool = True,
        collect_stderr: bool = True,
        stderr_is_error: bool = False,
        io_timeout: int = 300,
        runtime_timeout: int = 3600,
        sigterm_timeout: int = 5,
        initial_stdin: bytes | None = None,
        use_pty: bool = False,
    ) -> defer.Deferred[tuple[int | None, bytes, bytes] | tuple[int | None, bytes] | int | None]:
        _check_env_is_expected(self, self._master_run_process_expect_env, env)

        if not self._expected_master_commands:
            self.fail(f"got command {command} when no further commands were expected")

        expect = self._expected_master_commands.pop(0)

        rc, stdout, stderr = expect._check(self, command, workdir, env)

        if not collect_stderr and stderr_is_error and stderr:
            rc = -1

        if collect_stdout and collect_stderr:
            return defer.succeed((rc, stdout, stderr))
        if collect_stdout:
            return defer.succeed((rc, stdout))
        if collect_stderr:
            return defer.succeed((rc, stderr))
        return defer.succeed(rc)

    def _patch_runprocess(self) -> None:
        if not self._master_run_process_patched:
            self.patch(runprocess, "run_process", self.patched_run_process)
            self._master_run_process_patched = True

    def add_run_process_expect_env(self, d: dict[str, str]) -> None:
        self._master_run_process_expect_env.update(d)

    def expect_commands(self, *exp: ExpectMasterShell) -> None:
        for e in exp:
            if not isinstance(e, ExpectMasterShell):
                raise RuntimeError('All expectation must be an instance of ExpectMasterShell')

        self._patch_runprocess()
        self._expected_master_commands.extend(exp)
