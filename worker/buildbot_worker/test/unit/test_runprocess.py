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

import os
import pprint
import re
import signal
import sys
import time
from typing import TYPE_CHECKING
from typing import Any
from typing import NoReturn
from typing import Sequence
from typing import cast

import psutil
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import task
from twisted.python import log
from twisted.python import runtime
from twisted.python import util
from twisted.trial import unittest

from buildbot_worker import runprocess
from buildbot_worker import util as bsutil
from buildbot_worker.exceptions import AbandonChain
from buildbot_worker.test.util import compat
from buildbot_worker.test.util.misc import BasedirMixin
from buildbot_worker.test.util.misc import nl

try:
    from unittest.mock import Mock
except ImportError:
    from unittest.mock import Mock

if TYPE_CHECKING:
    from twisted.internet.defer import Deferred
    from twisted.internet.interfaces import IProcessProtocol
    from twisted.internet.interfaces import IReactorTime

    from buildbot_worker.util.twisted import InlineCallbacksType


def catCommand() -> list[str]:
    return [sys.executable, '-c', 'import sys; sys.stdout.write(sys.stdin.read())']


def stdoutCommand(output: str) -> list[str]:
    return [sys.executable, '-c', f'import sys; sys.stdout.write("{output}\\n")']


def stderrCommand(output: str) -> list[str]:
    return [sys.executable, '-c', f'import sys; sys.stderr.write("{output}\\n")']


def sleepCommand(dur: int) -> list[str]:
    return [sys.executable, '-c', f'import time; time.sleep({dur})']


def scriptCommand(function: str, *args: str) -> list[str]:
    runprocess_scripts = util.sibpath(__file__, 'runprocess-scripts.py')
    return [sys.executable, runprocess_scripts, function, *list(args)]


def printArgsCommand() -> list[str]:
    return [sys.executable, '-c', 'import sys; sys.stdout.write(repr(sys.argv[1:]))']


def print_text_command(lines: int, phrase: str) -> list[str]:
    return [
        sys.executable,
        '-c',
        f'''
import time
import sys
for _ in range({lines}):
    sys.stdout.write("{phrase}\\n")
    sys.stdout.flush()
    time.sleep(0.2)
''',
    ]


# windows returns rc 1, because exit status cannot indicate "signalled";
# posix returns rc -1 for "signalled"
FATAL_RC = -1
if runtime.platformType == 'win32':
    FATAL_RC = 1

# We would like to see debugging output in the test.log
runprocess.RunProcessPP.debug = True


class TestRunProcess(BasedirMixin, unittest.TestCase):
    def setUp(self) -> None:
        self.setUpBasedir()
        self.updates: list[Any] = []

    def send_update(self, status: list[Any]) -> None:
        for st in status:
            self.updates.append(st)

    def show(self) -> str:
        return pprint.pformat(self.updates)

    def tearDown(self) -> None:
        self.tearDownBasedir()

    def testCommandEncoding(self) -> None:
        s = runprocess.RunProcess(0, 'abcd', self.basedir, 'utf-8', self.send_update)
        self.assertIsInstance(s.command, bytes)
        self.assertIsInstance(s.fake_command, bytes)

    def testCommandEncodingList(self) -> None:
        s = runprocess.RunProcess(0, ['abcd', b'efg'], self.basedir, 'utf-8', self.send_update)
        self.assertIsInstance(s.command[0], bytes)
        self.assertIsInstance(s.fake_command[0], bytes)

    def testCommandEncodingObfuscated(self) -> None:
        s = runprocess.RunProcess(
            0, [bsutil.Obfuscated('abcd', 'ABCD')], self.basedir, 'utf-8', self.send_update
        )
        self.assertIsInstance(s.command[0], bytes)
        self.assertIsInstance(s.fake_command[0], bytes)

    @defer.inlineCallbacks
    def testStart(self) -> InlineCallbacksType[None]:
        s = runprocess.RunProcess(
            0, stdoutCommand('hello'), self.basedir, 'utf-8', self.send_update
        )

        yield s.start()

        self.assertTrue(('stdout', nl('hello\n')) in self.updates, self.show())
        self.assertTrue(('rc', 0) in self.updates, self.show())

    @defer.inlineCallbacks
    def testNoStdout(self) -> InlineCallbacksType[None]:
        s = runprocess.RunProcess(
            0, stdoutCommand('hello'), self.basedir, 'utf-8', self.send_update, sendStdout=False
        )

        yield s.start()

        self.assertFalse(('stdout', nl('hello\n')) in self.updates, self.show())
        self.assertTrue(('rc', 0) in self.updates, self.show())

    @defer.inlineCallbacks
    def testKeepStdout(self) -> InlineCallbacksType[None]:
        s = runprocess.RunProcess(
            0, stdoutCommand('hello'), self.basedir, 'utf-8', self.send_update, keepStdout=True
        )

        yield s.start()

        self.assertTrue(('stdout', nl('hello\n')) in self.updates, self.show())
        self.assertTrue(('rc', 0) in self.updates, self.show())
        self.assertEqual(s.stdout, nl('hello\n'))

    @defer.inlineCallbacks
    def testStderr(self) -> InlineCallbacksType[None]:
        s = runprocess.RunProcess(
            0, stderrCommand("hello"), self.basedir, 'utf-8', self.send_update
        )

        yield s.start()

        self.assertFalse(('stderr', nl('hello\n')) not in self.updates, self.show())
        self.assertTrue(('rc', 0) in self.updates, self.show())

    @defer.inlineCallbacks
    def testNoStderr(self) -> InlineCallbacksType[None]:
        s = runprocess.RunProcess(
            0, stderrCommand("hello"), self.basedir, 'utf-8', self.send_update, sendStderr=False
        )

        yield s.start()

        self.assertFalse(('stderr', nl('hello\n')) in self.updates, self.show())
        self.assertTrue(('rc', 0) in self.updates, self.show())

    @defer.inlineCallbacks
    def test_incrementalDecoder(self) -> InlineCallbacksType[None]:
        s = runprocess.RunProcess(
            0, stderrCommand("hello"), self.basedir, 'utf-8', self.send_update, sendStderr=True
        )
        pp = runprocess.RunProcessPP(s)
        # u"\N{SNOWMAN} when encoded to utf-8 bytes is b"\xe2\x98\x83"
        pp.outReceived(b"\xe2")
        pp.outReceived(b"\x98\x83")
        pp.errReceived(b"\xe2")
        pp.errReceived(b"\x98\x83")
        yield s.start()

        self.assertTrue(('stderr', "\N{SNOWMAN}") in self.updates)
        self.assertTrue(('stdout', "\N{SNOWMAN}") in self.updates)
        self.assertTrue(('rc', 0) in self.updates, self.show())

    @defer.inlineCallbacks
    def testInvalidUTF8(self) -> InlineCallbacksType[None]:
        s = runprocess.RunProcess(
            0, stderrCommand("hello"), self.basedir, 'utf-8', self.send_update, sendStderr=True
        )
        pp = runprocess.RunProcessPP(s)
        INVALID_UTF8 = b"\xff"
        with self.assertRaises(UnicodeDecodeError):
            INVALID_UTF8.decode('utf-8')
        pp.outReceived(INVALID_UTF8)
        yield s.start()
        stdout = next(value for key, value in self.updates if key == 'stdout')
        # On Python < 2.7 bytes is used, on Python >= 2.7 unicode
        self.assertIn(stdout, (b'\xef\xbf\xbd', '\ufffd'))
        self.assertTrue(('rc', 0) in self.updates, self.show())

    @defer.inlineCallbacks
    def testKeepStderr(self) -> InlineCallbacksType[None]:
        s = runprocess.RunProcess(
            0, stderrCommand("hello"), self.basedir, 'utf-8', self.send_update, keepStderr=True
        )

        yield s.start()

        self.assertTrue(('stderr', nl('hello\n')) in self.updates, self.show())
        self.assertTrue(('rc', 0) in self.updates, self.show())
        self.assertEqual(s.stderr, nl('hello\n'))

    @defer.inlineCallbacks
    def testStringCommand(self) -> InlineCallbacksType[None]:
        # careful!  This command must execute the same on windows and UNIX
        s = runprocess.RunProcess(0, 'echo hello', self.basedir, 'utf-8', self.send_update)

        yield s.start()

        self.assertTrue(('stdout', nl('hello\n')) in self.updates, self.show())
        self.assertTrue(('rc', 0) in self.updates, self.show())

    def testObfuscatedCommand(self) -> None:
        s = runprocess.RunProcess(
            0, [('obfuscated', 'abcd', 'ABCD')], self.basedir, 'utf-8', self.send_update
        )
        self.assertEqual(s.command, [b'abcd'])
        self.assertEqual(s.fake_command, [b'ABCD'])

    @defer.inlineCallbacks
    def testMultiWordStringCommand(self) -> InlineCallbacksType[None]:
        # careful!  This command must execute the same on windows and UNIX
        s = runprocess.RunProcess(
            0, 'echo Happy Days and Jubilation', self.basedir, 'utf-8', self.send_update
        )

        # no quoting occurs
        exp = nl('Happy Days and Jubilation\n')
        yield s.start()

        self.assertTrue(('stdout', exp) in self.updates, self.show())
        self.assertTrue(('rc', 0) in self.updates, self.show())

    @defer.inlineCallbacks
    def testInitialStdinUnicode(self) -> InlineCallbacksType[None]:
        s = runprocess.RunProcess(
            0, catCommand(), self.basedir, 'utf-8', self.send_update, initialStdin='hello'
        )

        yield s.start()

        self.assertTrue(('stdout', nl('hello')) in self.updates, self.show())
        self.assertTrue(('rc', 0) in self.updates, self.show())

    @defer.inlineCallbacks
    def testMultiWordStringCommandQuotes(self) -> InlineCallbacksType[None]:
        # careful!  This command must execute the same on windows and UNIX
        s = runprocess.RunProcess(
            0, 'echo "Happy Days and Jubilation"', self.basedir, 'utf-8', self.send_update
        )

        if runtime.platformType == "win32":
            # echo doesn't parse out the quotes, so they come through in the
            # output
            exp = nl('"Happy Days and Jubilation"\n')
        else:
            exp = nl('Happy Days and Jubilation\n')
        yield s.start()

        self.assertTrue(('stdout', exp) in self.updates, self.show())
        self.assertTrue(('rc', 0) in self.updates, self.show())

    @defer.inlineCallbacks
    def testTrickyArguments(self) -> InlineCallbacksType[None]:
        # make sure non-trivial arguments are passed verbatim
        args = [
            'Happy Days and Jubilation',  # spaces
            r"""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~""",  # special characters
            '%PATH%',  # Windows variable expansions
            # Expansions get an argument of their own, because the Windows
            # shell doesn't treat % as special unless it surrounds a
            # variable name.
        ]

        s = runprocess.RunProcess(
            0, printArgsCommand() + args, self.basedir, 'utf-8', self.send_update
        )
        yield s.start()

        self.assertTrue(('stdout', nl(repr(args))) in self.updates, self.show())
        self.assertTrue(('rc', 0) in self.updates, self.show())

    @defer.inlineCallbacks
    @compat.skipUnlessPlatformIs("win32")
    def testPipeString(self) -> InlineCallbacksType[None]:
        # this is highly contrived, but it proves the point.
        cmd = sys.executable + ' -c "import sys; sys.stdout.write(\'b\\na\\n\')" | sort'
        s = runprocess.RunProcess(0, cmd, self.basedir, 'utf-8', self.send_update)

        yield s.start()

        self.assertTrue(('stdout', nl('a\nb\n')) in self.updates, self.show())
        self.assertTrue(('rc', 0) in self.updates, self.show())

    @defer.inlineCallbacks
    def testCommandTimeout(self) -> InlineCallbacksType[None]:
        s = runprocess.RunProcess(
            0, sleepCommand(10), self.basedir, 'utf-8', self.send_update, timeout=5
        )
        clock = task.Clock()
        s._reactor = clock

        d = s.start()
        clock.advance(6)
        yield d

        self.assertTrue(('stdout', nl('hello\n')) not in self.updates, self.show())
        self.assertTrue(('rc', FATAL_RC) in self.updates, self.show())
        self.assertTrue(("failure_reason", "timeout_without_output") in self.updates, self.show())

    @defer.inlineCallbacks
    def testCommandMaxTime(self) -> InlineCallbacksType[None]:
        s = runprocess.RunProcess(
            0, sleepCommand(10), self.basedir, 'utf-8', self.send_update, maxTime=5
        )
        clock = task.Clock()
        s._reactor = clock

        d = s.start()
        clock.advance(6)  # should knock out maxTime
        yield d

        self.assertTrue(('stdout', nl('hello\n')) not in self.updates, self.show())
        self.assertTrue(('rc', FATAL_RC) in self.updates, self.show())
        self.assertTrue(("failure_reason", "timeout") in self.updates, self.show())

    @defer.inlineCallbacks
    def test_command_max_lines(self) -> InlineCallbacksType[None]:
        s = runprocess.RunProcess(
            0,
            print_text_command(5, 'hello'),
            self.basedir,
            'utf-8',
            self.send_update,
            sendStdout=True,
            max_lines=1,
        )

        d = s.start()
        yield d

        self.assertTrue(('stdout', nl('hello\n')) in self.updates, self.show())
        self.assertTrue(('rc', FATAL_RC) in self.updates, self.show())
        self.assertTrue(("failure_reason", "max_lines_failure") in self.updates, self.show())

    @compat.skipUnlessPlatformIs("posix")
    @defer.inlineCallbacks
    def test_stdin_closed(self) -> InlineCallbacksType[None]:
        s = runprocess.RunProcess(
            0,
            scriptCommand('assert_stdin_closed'),
            self.basedir,
            'utf-8',
            self.send_update,
            # if usePTY=True, stdin is never closed
            usePTY=False,
            logEnviron=False,
        )
        yield s.start()

        self.assertTrue(('rc', 0) in self.updates, self.show())

    @defer.inlineCallbacks
    def test_startCommand_exception(self) -> InlineCallbacksType[None]:
        s = runprocess.RunProcess(0, ['whatever'], self.basedir, 'utf-8', self.send_update)

        # set up to cause an exception in _startCommand
        def _startCommand(*args: Any, **kwargs: Any) -> NoReturn:
            raise RuntimeError('error message')

        s._startCommand = _startCommand  # type: ignore[method-assign]

        try:
            yield s.start()
        except AbandonChain:
            pass

        _stderr: list[str] = []
        # Here we're checking that the exception starting up the command
        # actually gets propagated back to the master in stderr.
        for key, value in self.updates:
            if key == 'stderr':
                _stderr.append(value)
        stderr = ''.join(_stderr)
        self.assertTrue(stderr.startswith('error in RunProcess._startCommand (error message)'))

        yield self.flushLoggedErrors()

    @defer.inlineCallbacks
    def testLogEnviron(self) -> InlineCallbacksType[None]:
        s = runprocess.RunProcess(
            0,
            stdoutCommand('hello'),
            self.basedir,
            'utf-8',
            self.send_update,
            environ={"FOO": "BAR"},
        )

        yield s.start()

        headers = "".join([value for key, value in self.updates if key == "header"])
        self.assertTrue("FOO=BAR" in headers, "got:\n" + headers)

    @defer.inlineCallbacks
    def testNoLogEnviron(self) -> InlineCallbacksType[None]:
        s = runprocess.RunProcess(
            0,
            stdoutCommand('hello'),
            self.basedir,
            'utf-8',
            self.send_update,
            environ={"FOO": "BAR"},
            logEnviron=False,
        )

        yield s.start()

        headers = "".join([
            next(iter(update.values())) for update in self.updates if list(update) == ["header"]
        ])
        self.assertTrue("FOO=BAR" not in headers, "got:\n" + headers)

    @defer.inlineCallbacks
    def testEnvironExpandVar(self) -> InlineCallbacksType[None]:
        environ = {
            "EXPND": "-${PATH}-",
            "DOESNT_EXPAND": "-${---}-",
            "DOESNT_FIND": "-${DOESNT_EXISTS}-",
        }
        s = runprocess.RunProcess(
            0, stdoutCommand('hello'), self.basedir, 'utf-8', self.send_update, environ=environ
        )

        yield s.start()

        headers = "".join([value for key, value in self.updates if key == "header"])
        self.assertTrue("EXPND=-$" not in headers, "got:\n" + headers)
        self.assertTrue("DOESNT_FIND=--" in headers, "got:\n" + headers)
        self.assertTrue("DOESNT_EXPAND=-${---}-" in headers, "got:\n" + headers)

    @defer.inlineCallbacks
    def testUnsetEnvironVar(self) -> InlineCallbacksType[None]:
        s = runprocess.RunProcess(
            0,
            stdoutCommand('hello'),
            self.basedir,
            'utf-8',
            self.send_update,
            environ={"PATH": None},
        )

        yield s.start()

        headers = "".join([
            next(iter(update.values())) for update in self.updates if list(update) == ["header"]
        ])
        self.assertFalse(re.match('\bPATH=', headers), "got:\n" + headers)

    @defer.inlineCallbacks
    def testEnvironPythonPath(self) -> InlineCallbacksType[None]:
        s = runprocess.RunProcess(
            0,
            stdoutCommand('hello'),
            self.basedir,
            'utf-8',
            self.send_update,
            environ={"PYTHONPATH": 'a'},
        )

        yield s.start()

        headers = "".join([
            next(iter(update.values())) for update in self.updates if list(update) == ["header"]
        ])
        self.assertFalse(re.match(f'\bPYTHONPATH=a{os.pathsep}', headers), "got:\n" + headers)

    @defer.inlineCallbacks
    def testEnvironArray(self) -> InlineCallbacksType[None]:
        s = runprocess.RunProcess(
            0,
            stdoutCommand('hello'),
            self.basedir,
            'utf-8',
            self.send_update,
            environ={"FOO": ['a', 'b']},
        )

        yield s.start()

        headers = "".join([
            next(iter(update.values())) for update in self.updates if list(update) == ["header"]
        ])
        self.assertFalse(re.match(f'\bFOO=a{os.pathsep}b\b', headers), "got:\n" + headers)

    def testEnvironInt(self) -> None:
        with self.assertRaises(RuntimeError):
            runprocess.RunProcess(
                0,
                stdoutCommand('hello'),
                self.basedir,
                'utf-8',
                self.send_update,
                environ={"BUILD_NUMBER": 13},
            )

    def _test_spawnAsBatch(self, cmd: Sequence[str], comspec: str) -> None:
        def spawnProcess(
            processProtocol: IProcessProtocol,
            executable: bytes | str,
            args: Sequence[str],
            *pargs: Any,
            **kwargs: Any,
        ) -> None:
            self.assertTrue(args[0].lower().endswith("cmd.exe"), f"{args[0]} is not cmd.exe")

        self.patch(runprocess.reactor, "spawnProcess", spawnProcess)
        tempEnviron = os.environ.copy()
        if 'COMSPEC' not in tempEnviron:
            tempEnviron['COMSPEC'] = comspec
        self.patch(os, "environ", tempEnviron)
        s = runprocess.RunProcess(0, cmd, self.basedir, 'utf-8', self.send_update)
        s.pp = runprocess.RunProcessPP(s)
        s.deferred = defer.Deferred()
        d = s._spawnAsBatch(s.pp, s.command, "args", tempEnviron, "path", False)
        return d

    @defer.inlineCallbacks
    @compat.skipUnlessPlatformIs("win32")
    def test_assign_exited_process(self) -> InlineCallbacksType[None]:
        s = runprocess.RunProcess(
            0,
            ["cmd.exe", "/c", "exit"],
            self.basedir,
            'utf-8',
            self.send_update,
        )
        yield s.start()

        # Assert that the process completed successfully
        self.assertTrue(('rc', 0) in self.updates, self.show())

    def test_spawnAsBatchCommandString(self) -> None:
        return self._test_spawnAsBatch("dir c:/", "cmd.exe")

    def test_spawnAsBatchCommandList(self) -> None:
        return self._test_spawnAsBatch(stdoutCommand('hello'), "cmd.exe /c")

    def test_spawnAsBatchCommandWithNonAscii(self) -> None:
        return self._test_spawnAsBatch("echo \u6211", "cmd.exe")

    def test_spawnAsBatchCommandListWithNonAscii(self) -> None:
        return self._test_spawnAsBatch(['echo', "\u6211"], "cmd.exe /c")


class TestPOSIXKilling(BasedirMixin, unittest.TestCase):
    timeout = 60  # takes a while on oversubscribed test machines

    if runtime.platformType != "posix":
        skip = "not a POSIX platform"

    def setUp(self) -> None:
        self.pidfiles: list[str] = []
        self.setUpBasedir()
        self.updates: list[Any] = []

    def send_update(self, status: list[tuple[str, int] | tuple[str, str]]) -> None:
        self.updates.append(status)

    def tearDown(self) -> None:
        # make sure all of the subprocesses are dead
        for pidfile in self.pidfiles:
            if not os.path.exists(pidfile):
                continue
            with open(pidfile) as f:
                pid = f.read()
            if not pid:
                return
            try:
                os.kill(int(pid), signal.SIGKILL)
            except OSError:
                pass

        # and clean up leftover pidfiles
        for pidfile in self.pidfiles:
            if os.path.exists(pidfile):
                os.unlink(pidfile)

        self.tearDownBasedir()

    def newPidfile(self) -> str:
        pidfile = os.path.abspath(f"test-{len(self.pidfiles)}.pid")
        if os.path.exists(pidfile):
            os.unlink(pidfile)
        self.pidfiles.append(pidfile)
        return pidfile

    def waitForPidfile(self, pidfile: str) -> Deferred:
        # wait for a pidfile, and return the pid via a Deferred
        until = time.time() + self.timeout
        d: defer.Deferred[int] = defer.Deferred()

        poll_reactor: IReactorTime = cast("IReactorTime", reactor)

        def poll() -> None:
            if poll_reactor.seconds() > until:
                d.errback(RuntimeError(f"pidfile {pidfile} never appeared"))
                return
            if os.path.exists(pidfile):
                try:
                    with open(pidfile) as f:
                        pid = int(f.read())
                except (OSError, TypeError, ValueError):
                    pid = None

                if pid is not None:
                    d.callback(pid)
                    return
            poll_reactor.callLater(0.01, poll)

        poll()  # poll right away
        return d

    def assertAlive(self, pid: int) -> None:
        try:
            os.kill(pid, 0)
        except OSError:
            self.fail(f"pid {pid} still alive")

    def assertDead(self, pid: int, timeout: int = 5) -> None:
        log.msg(f"checking pid {pid!r}")

        def check() -> bool:
            try:
                os.kill(pid, 0)
            except OSError:
                return True  # dead
            return False  # alive

        # check immediately
        if check():
            return

        # poll every 100'th of a second; this allows us to test for
        # processes that have been killed, but where the signal hasn't
        # been delivered yet
        until = time.time() + timeout
        while time.time() < until:
            time.sleep(0.01)
            if check():
                return
        self.fail(f"pid {pid} still alive after {timeout}s")

    # tests

    def test_simple_interruptSignal(self) -> Deferred:
        return self.test_simple('TERM')

    def test_simple(self, interruptSignal: str | None = None) -> Deferred:
        # test a simple process that just sleeps waiting to die
        pidfile = self.newPidfile()
        self.pid = None

        s = runprocess.RunProcess(
            0,
            scriptCommand('write_pidfile_and_sleep', pidfile),
            self.basedir,
            'utf-8',
            self.send_update,
        )
        if interruptSignal is not None:
            s.interruptSignal = interruptSignal
        runproc_d = s.start()

        pidfile_d = self.waitForPidfile(pidfile)

        def check_alive(pid: int) -> None:
            self.pid = pid  # for use in check_dead
            # test that the process is still alive
            self.assertAlive(pid)
            # and tell the RunProcess object to kill it
            s.kill("diaf")

        pidfile_d.addCallback(check_alive)

        def check_dead(_: Any) -> None:
            assert self.pid is not None
            self.assertDead(self.pid)

        runproc_d.addCallback(check_dead)
        return defer.gatherResults([pidfile_d, runproc_d], consumeErrors=True)

    def test_sigterm(self, interruptSignal: None = None) -> Deferred:
        # Tests that the process will receive SIGTERM if sigtermTimeout
        # is not None
        pidfile = self.newPidfile()
        self.pid = None
        s = runprocess.RunProcess(
            0,
            scriptCommand('write_pidfile_and_sleep', pidfile),
            self.basedir,
            'utf-8',
            self.send_update,
            sigtermTime=1,
        )
        runproc_d = s.start()
        pidfile_d = self.waitForPidfile(pidfile)
        self.receivedSIGTERM = False

        def check_alive(pid: int) -> None:
            # Create a mock process that will check if we receive SIGTERM
            mock_process = Mock(wraps=s.process)
            mock_process.pgid = None  # Skips over group SIGTERM
            mock_process.pid = pid
            process = s.process

            def _mock_signalProcess(sig: str) -> None:
                if sig == "TERM":
                    self.receivedSIGTERM = True
                process.signalProcess(sig)

            mock_process.signalProcess = _mock_signalProcess
            s.process = mock_process

            self.pid = pid  # for use in check_dead
            # test that the process is still alive
            self.assertAlive(pid)
            # and tell the RunProcess object to kill it
            s.kill("diaf")

        pidfile_d.addCallback(check_alive)

        def check_dead(_: Any) -> None:
            self.assertEqual(self.receivedSIGTERM, True)
            assert self.pid is not None
            self.assertDead(self.pid)

        runproc_d.addCallback(check_dead)
        return defer.gatherResults([pidfile_d, runproc_d], consumeErrors=True)

    def test_pgroup_usePTY(self) -> Deferred:
        return self.do_test_pgroup(usePTY=True)

    def test_pgroup_no_usePTY(self) -> Deferred:
        return self.do_test_pgroup(usePTY=False)

    def test_pgroup_no_usePTY_no_pgroup(self) -> Deferred:
        # note that this configuration is not *used*, but that it is
        # still supported, and correctly fails to kill the child process
        return self.do_test_pgroup(usePTY=False, useProcGroup=False, expectChildSurvival=True)

    @defer.inlineCallbacks
    def do_test_pgroup(
        self, usePTY: bool, useProcGroup: bool = True, expectChildSurvival: bool = False
    ) -> InlineCallbacksType[None]:
        # test that a process group gets killed
        parent_pidfile = self.newPidfile()
        self.parent_pid = None
        child_pidfile = self.newPidfile()
        self.child_pid = None

        s = runprocess.RunProcess(
            0,
            scriptCommand('spawn_child', parent_pidfile, child_pidfile),
            self.basedir,
            'utf-8',
            self.send_update,
            usePTY=usePTY,
            useProcGroup=useProcGroup,
        )
        runproc_d = s.start()

        # wait for both processes to start up, then call s.kill
        parent_pidfile_d = self.waitForPidfile(parent_pidfile)
        child_pidfile_d = self.waitForPidfile(child_pidfile)
        pidfiles_d = defer.gatherResults([parent_pidfile_d, child_pidfile_d], consumeErrors=True)

        def got_pids(pids: Sequence[int]) -> None:
            self.parent_pid, self.child_pid = pids

        pidfiles_d.addCallback(got_pids)

        def kill(_: Any) -> None:
            s.kill("diaf")

        pidfiles_d.addCallback(kill)

        # check that both processes are dead after RunProcess is done
        yield defer.gatherResults([pidfiles_d, runproc_d], consumeErrors=True)

        assert self.parent_pid is not None
        self.assertDead(self.parent_pid)
        assert self.child_pid is not None
        if expectChildSurvival:
            self.assertAlive(self.child_pid)
        else:
            self.assertDead(self.child_pid)

    def test_double_fork_usePTY(self) -> Deferred:
        return self.do_test_double_fork(usePTY=True)

    def test_double_fork_no_usePTY(self) -> Deferred:
        return self.do_test_double_fork(usePTY=False)

    def test_double_fork_no_usePTY_no_pgroup(self) -> Deferred:
        # note that this configuration is not *used*, but that it is
        # still supported, and correctly fails to kill the child process
        return self.do_test_double_fork(usePTY=False, useProcGroup=False, expectChildSurvival=True)

    @defer.inlineCallbacks
    def do_test_double_fork(
        self, usePTY: bool, useProcGroup: bool = True, expectChildSurvival: bool = False
    ) -> InlineCallbacksType[None]:
        # when a spawned process spawns another process, and then dies itself
        # (either intentionally or accidentally), we should be able to clean up
        # the child.
        parent_pidfile = self.newPidfile()
        self.parent_pid = None
        child_pidfile = self.newPidfile()
        self.child_pid = None

        s = runprocess.RunProcess(
            0,
            scriptCommand('double_fork', parent_pidfile, child_pidfile),
            self.basedir,
            'utf-8',
            self.send_update,
            usePTY=usePTY,
            useProcGroup=useProcGroup,
        )
        runproc_d = s.start()

        # wait for both processes to start up, then call s.kill
        parent_pidfile_d = self.waitForPidfile(parent_pidfile)
        child_pidfile_d = self.waitForPidfile(child_pidfile)
        pidfiles_d = defer.gatherResults([parent_pidfile_d, child_pidfile_d], consumeErrors=True)

        def got_pids(pids: Sequence[int]) -> None:
            self.parent_pid, self.child_pid = pids

        pidfiles_d.addCallback(got_pids)

        def kill(_: Any) -> None:
            s.kill("diaf")

        pidfiles_d.addCallback(kill)

        # check that both processes are dead after RunProcess is done
        yield defer.gatherResults([pidfiles_d, runproc_d], consumeErrors=True)

        assert self.parent_pid is not None
        self.assertDead(self.parent_pid)
        assert self.child_pid is not None
        if expectChildSurvival:
            self.assertAlive(self.child_pid)
        else:
            self.assertDead(self.child_pid)


class TestWindowsKilling(BasedirMixin, unittest.TestCase):
    if runtime.platformType != "win32":
        skip = "not a Windows platform"

    def setUp(self) -> None:
        self.pidfiles: list[str] = []
        self.setUpBasedir()
        self.updates: list[Any] = []

    def send_update(self, status: Any) -> None:
        self.updates.append(status)

    def tearDown(self) -> None:
        # make sure all of the subprocesses are dead
        for pidfile in self.pidfiles:
            if not os.path.exists(pidfile):
                continue
            with open(pidfile) as f:
                pid_str = f.read()
            if not pid_str:
                return
            pid = int(pid_str)
            try:
                psutil.Process(pid).kill()
            except psutil.NoSuchProcess:
                pass
            while psutil.pid_exists(pid):
                time.sleep(0.01)

        # and clean up leftover pidfiles
        for pidfile in self.pidfiles:
            if os.path.exists(pidfile):
                os.unlink(pidfile)

        self.tearDownBasedir()

    def new_pid_file(self) -> str:
        pidfile = os.path.abspath(f"test-{len(self.pidfiles)}.pid")
        if os.path.exists(pidfile):
            os.unlink(pidfile)
        self.pidfiles.append(pidfile)
        return pidfile

    def wait_for_pidfile(self, pidfile: str) -> Deferred[int]:
        # wait for a pidfile, and return the pid via a Deferred
        until = time.time() + 10
        d: defer.Deferred[int] = defer.Deferred()

        poll_reactor: IReactorTime = cast("IReactorTime", reactor)

        def poll() -> None:
            if poll_reactor.seconds() > until:
                d.errback(RuntimeError(f"pidfile {pidfile} never appeared"))
                return
            if os.path.exists(pidfile):
                try:
                    with open(pidfile) as f:
                        pid = int(f.read())
                except (OSError, TypeError, ValueError):
                    pid = None

                if pid is not None:
                    d.callback(pid)
                    return
            poll_reactor.callLater(0.01, poll)

        poll()  # poll right away
        return d

    def assert_alive(self, pid: int) -> None:
        if not psutil.pid_exists(pid):
            self.fail(f"pid {pid} dead, but expected it to be alive")

    def assert_dead(self, pid: int, timeout: int = 5) -> None:
        log.msg(f"checking pid {pid!r}")

        # check immediately
        if not psutil.pid_exists(pid):
            return

        # poll every 100'th of a second; this allows us to test for
        # processes that have been killed, but where the signal hasn't
        # been delivered yet
        until = time.time() + timeout
        while time.time() < until:
            time.sleep(0.01)
            if not psutil.pid_exists(pid):
                return
        self.fail(f"pid {pid} still alive after {timeout}s")

    # tests

    @defer.inlineCallbacks
    def test_simple(self, interrupt_signal: str | None = None) -> InlineCallbacksType[None]:
        # test a simple process that just sleeps waiting to die
        pidfile = self.new_pid_file()

        s = runprocess.RunProcess(
            0,
            scriptCommand('write_pidfile_and_sleep', pidfile),
            self.basedir,
            'utf-8',
            self.send_update,
        )
        if interrupt_signal is not None:
            s.interruptSignal = interrupt_signal
        runproc_d = s.start()

        pid = yield self.wait_for_pidfile(pidfile)

        self.assert_alive(pid)

        # test that the process is still alive and tell the RunProcess object to kill it
        s.kill("diaf")

        yield runproc_d
        self.assert_dead(pid)

    @defer.inlineCallbacks
    def test_sigterm(self) -> InlineCallbacksType[None]:
        # Tests that the process will receive SIGTERM if sigtermTimeout is not None
        pidfile = self.new_pid_file()

        s = runprocess.RunProcess(
            0,
            scriptCommand('write_pidfile_and_sleep', pidfile),
            self.basedir,
            'utf-8',
            self.send_update,
            sigtermTime=1,
        )

        taskkill_calls = []
        orig_taskkill = s._win32_taskkill

        def mock_taskkill(pid: int, force: bool) -> None:
            taskkill_calls.append(force)
            orig_taskkill(pid, force)

        s._win32_taskkill = mock_taskkill  # type: ignore[method-assign]

        runproc_d = s.start()
        pid = yield self.wait_for_pidfile(pidfile)
        # test that the process is still alive
        self.assert_alive(pid)
        # and tell the RunProcess object to kill it
        s.kill("diaf")

        yield runproc_d
        self.assertEqual(taskkill_calls, [False, True])
        self.assert_dead(pid)

    @defer.inlineCallbacks
    def test_with_child(self) -> InlineCallbacksType[None]:
        # test that a process group gets killed
        parent_pidfile = self.new_pid_file()
        child_pidfile = self.new_pid_file()

        s = runprocess.RunProcess(
            0,
            scriptCommand('spawn_child', parent_pidfile, child_pidfile),
            self.basedir,
            'utf-8',
            self.send_update,
        )
        runproc_d = s.start()

        # wait for both processes to start up, then call s.kill
        parent_pid = yield self.wait_for_pidfile(parent_pidfile)
        child_pid = yield self.wait_for_pidfile(child_pidfile)

        s.kill("diaf")

        yield runproc_d

        self.assert_dead(parent_pid)
        self.assert_dead(child_pid)

    @defer.inlineCallbacks
    def test_with_child_parent_dies(self) -> InlineCallbacksType[None]:
        # when a spawned process spawns another process, and then dies itself
        # (either intentionally or accidentally), we kill the child processes.
        parent_pidfile = self.new_pid_file()
        child_pidfile = self.new_pid_file()

        s = runprocess.RunProcess(
            0,
            scriptCommand('double_fork', parent_pidfile, child_pidfile),
            self.basedir,
            'utf-8',
            self.send_update,
        )
        runproc_d = s.start()
        # wait for both processes to start up, then call s.kill
        parent_pid = yield self.wait_for_pidfile(parent_pidfile)
        child_pid = yield self.wait_for_pidfile(child_pidfile)

        s.kill("diaf")

        # check that both processes are dead after RunProcess is done
        yield runproc_d

        self.assert_dead(parent_pid)
        self.assert_dead(child_pid)


class TestLogFileWatcher(BasedirMixin, unittest.TestCase):
    def setUp(self) -> None:
        self.setUpBasedir()
        self.updates: list[Any] = []

    def send_update(self, status: list[tuple[str, tuple[str, str]]]) -> None:
        for st in status:
            self.updates.append(st)

    def show(self) -> str:
        return pprint.pformat(self.updates)

    def tearDown(self) -> None:
        self.tearDownBasedir()

    def makeRP(self) -> runprocess.RunProcess:
        rp = runprocess.RunProcess(
            0, stdoutCommand('hello'), self.basedir, 'utf-8', self.send_update
        )
        return rp

    def test_statFile_missing(self) -> None:
        rp = self.makeRP()
        test_filename = 'test_runprocess_test_statFile_missing.log'
        if os.path.exists(test_filename):
            os.remove(test_filename)
        lf = runprocess.LogFileWatcher(rp, 'test', test_filename, False)
        self.assertFalse(lf.statFile(), f"{test_filename} doesn't exist")

    def test_statFile_exists(self) -> None:
        rp = self.makeRP()
        test_filename = 'test_runprocess_test_statFile_exists.log'
        try:
            with open(test_filename, 'w') as f:
                f.write('hi')
            lf = runprocess.LogFileWatcher(rp, 'test', test_filename, False)
            st = lf.statFile()
            self.assertEqual(st and st[2], 2, "statfile.log exists and size is correct")
        finally:
            os.remove(test_filename)

    def test_invalid_utf8(self) -> None:
        # create the log file watcher first
        rp = self.makeRP()
        test_filename = 'test_runprocess_test_invalid_utf8.log'

        try:
            lf = runprocess.LogFileWatcher(rp, 'test', test_filename, follow=False, poll=False)
            # now write to the log file
            INVALID_UTF8 = b'before\xffafter'
            with open(test_filename, 'wb') as f:
                f.write(INVALID_UTF8)
            # the watcher picks up the changed log
            lf.poll()
            # the log file content was captured and the invalid byte replaced with \ufffd (the
            # replacement character, often a black diamond with a white question mark)
            REPLACED = 'before\ufffdafter'
            self.assertEqual(self.updates, [('log', ('test', REPLACED))])

        finally:
            lf.stop()
            os.remove(f.name)
