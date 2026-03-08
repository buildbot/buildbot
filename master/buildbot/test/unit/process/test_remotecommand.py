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
from typing import Any
from unittest import mock

from twisted.trial import unittest

from buildbot.process import remotecommand
from buildbot.test.fake import logfile
from buildbot.test.util import interfaces
from buildbot.test.util.warnings import assertNotProducesWarnings
from buildbot.warnings import DeprecatedApiWarning

if TYPE_CHECKING:
    from collections.abc import Awaitable
    from collections.abc import Callable

    from twisted.internet import defer
    from twisted.python.failure import Failure

    from buildbot.process.buildstep import BuildStep
    from buildbot.process.log import Log
    from buildbot.process.log import StreamLog
    from buildbot.worker.protocols.base import Connection


class TestRemoteShellCommand(unittest.TestCase):
    def test_obfuscated_arguments(self) -> None:
        command = [
            "echo",
            ("obfuscated", "real", "fake"),
            "test",
            ("obfuscated", "real2", "fake2"),
            ("not obfuscated", "a", "b"),
            ("obfuscated"),  # not obfuscated
            ("obfuscated", "test"),  # not obfuscated
            ("obfuscated", "1", "2", "3"),  # not obfuscated)
        ]
        cmd = remotecommand.RemoteShellCommand("build", command)
        self.assertEqual(cmd.command, command)
        self.assertEqual(
            cmd.fake_command,
            [
                "echo",
                "fake",
                "test",
                "fake2",
                ("not obfuscated", "a", "b"),
                ("obfuscated"),  # not obfuscated
                # not obfuscated
                ("obfuscated", "test"),
                # not obfuscated)
                ("obfuscated", "1", "2", "3"),
            ],
        )

    def test_not_obfuscated_arguments(self) -> None:
        command = "echo test"
        cmd = remotecommand.RemoteShellCommand("build", command)
        self.assertEqual(cmd.command, command)
        self.assertEqual(cmd.fake_command, command)


# NOTE:
#
# This interface is considered private to Buildbot and may change without
# warning in future versions.


class Tests(interfaces.InterfaceTests, unittest.TestCase):
    def makeRemoteCommand(self, stdioLogName: str = 'stdio') -> remotecommand.RemoteCommand:
        return remotecommand.RemoteCommand('ping', {'arg': 'val'}, stdioLogName=stdioLogName)

    def test_signature_RemoteCommand_constructor(self) -> None:
        @self.assertArgSpecMatches(remotecommand.RemoteCommand.__init__)
        def __init__(
            self: Any,
            remote_command: str,
            args: dict[str, Any],
            ignore_updates: bool = False,
            collectStdout: bool = False,
            collectStderr: bool = False,
            decodeRC: dict[int | None, int] | None = None,
            stdioLogName: str = 'stdio',
        ) -> None:
            pass

    def test_signature_RemoteShellCommand_constructor(self) -> None:
        @self.assertArgSpecMatches(remotecommand.RemoteShellCommand.__init__)
        def __init__(
            self: Any,
            workdir: str | None,
            command: str | bytes | list[str | bytes | tuple[str, str, str]],
            env: dict[str, str] | None = None,
            want_stdout: int = 1,
            want_stderr: int = 1,
            timeout: float = 20 * 60,
            maxTime: float | None = None,
            max_lines: int | None = None,
            sigtermTime: float | None = None,
            logfiles: dict[str, str] | None = None,
            usePTY: bool | None = None,
            logEnviron: bool = True,
            collectStdout: bool = False,
            collectStderr: bool = False,
            interruptSignal: str | None = None,
            initialStdin: str | None = None,
            decodeRC: dict[int | None, int] | None = None,
            stdioLogName: str = 'stdio',
        ) -> None:
            pass

    def test_signature_run(self) -> None:
        cmd = self.makeRemoteCommand()

        @self.assertArgSpecMatches(cmd.run)
        def run(self: Any, step: BuildStep, conn: Connection, builder_name: str) -> None:
            pass

    def test_signature_useLog(self) -> None:
        cmd = self.makeRemoteCommand()

        @self.assertArgSpecMatches(cmd.useLog)
        def useLog(
            self: Any, log_: Log, closeWhenFinished: bool = False, logfileName: str | None = None
        ) -> None:
            pass

    def test_signature_useLogDelayed(self) -> None:
        cmd = self.makeRemoteCommand()

        @self.assertArgSpecMatches(cmd.useLogDelayed)
        def useLogDelayed(
            self: Any,
            logfileName: str,
            activateCallBack: Callable[
                [remotecommand.RemoteCommand], defer.Deferred[StreamLog] | Awaitable[StreamLog]
            ],
            closeWhenFinished: bool = False,
        ) -> None:
            pass

    def test_signature_interrupt(self) -> None:
        cmd = self.makeRemoteCommand()

        @self.assertArgSpecMatches(cmd.interrupt)
        def useLogDelayed(self: Any, why: Failure | str) -> None:
            pass

    def test_signature_didFail(self) -> None:
        cmd = self.makeRemoteCommand()

        @self.assertArgSpecMatches(cmd.didFail)
        def useLogDelayed(self: Any) -> None:
            pass

    def test_signature_logs(self) -> None:
        cmd = self.makeRemoteCommand()
        self.assertIsInstance(cmd.logs, dict)

    def test_signature_active(self) -> None:
        cmd = self.makeRemoteCommand()
        self.assertIsInstance(cmd.active, bool)

    def test_RemoteShellCommand_constructor(self) -> None:
        remotecommand.RemoteShellCommand('wkdir', 'some-command')

    def test_notStdioLog(self) -> None:
        logname = 'notstdio'
        cmd = self.makeRemoteCommand(stdioLogName=logname)
        log = logfile.FakeLogFile(logname)
        cmd.useLog(log)  # type: ignore[arg-type]
        cmd.addStdout('some stdout')
        self.assertEqual(log.stdout, 'some stdout')
        cmd.addStderr('some stderr')
        self.assertEqual(log.stderr, 'some stderr')
        cmd.addHeader('some header')
        self.assertEqual(log.header, 'some header')

    def test_RemoteShellCommand_usePTY_on_worker_2_16(self) -> None:
        cmd = remotecommand.RemoteShellCommand('workdir', 'shell')

        def workerVersion(command: str, oldversion: str | None = None) -> str:
            return '2.16'

        def workerVersionIsOlderThan(command: str, minversion: str) -> bool:
            return ['2', '16'] < minversion.split('.')

        step = mock.Mock()
        step.workerVersionIsOlderThan = workerVersionIsOlderThan
        step.workerVersion = workerVersion
        conn = mock.Mock()
        conn.remoteStartCommand = mock.Mock(return_value=None)
        conn.get_peer = mock.Mock(return_value="peer")

        cmd.run(step, conn, 'builder')

        self.assertEqual(cmd.args['usePTY'], 'slave-config')


class TestWorkerTransition(unittest.TestCase):
    def test_RemoteShellCommand_usePTY(self) -> None:
        with assertNotProducesWarnings(DeprecatedApiWarning):
            cmd = remotecommand.RemoteShellCommand('workdir', 'command')

        self.assertTrue(cmd.args['usePTY'] is None)

        with assertNotProducesWarnings(DeprecatedApiWarning):
            cmd = remotecommand.RemoteShellCommand('workdir', 'command', usePTY=True)

        self.assertTrue(cmd.args['usePTY'])

        with assertNotProducesWarnings(DeprecatedApiWarning):
            cmd = remotecommand.RemoteShellCommand('workdir', 'command', usePTY=False)

        self.assertFalse(cmd.args['usePTY'])
