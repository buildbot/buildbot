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
from __future__ import division
from __future__ import print_function

import os
import re
import signal
import sys
import tempfile
import time

from mock import Mock

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
from buildbot_worker.test.fake.workerforbuilder import FakeWorkerForBuilder
from buildbot_worker.test.util import compat
from buildbot_worker.test.util.misc import BasedirMixin
from buildbot_worker.test.util.misc import nl


def catCommand():
    return [sys.executable, '-c', 'import sys; sys.stdout.write(sys.stdin.read())']


def stdoutCommand(output):
    return [sys.executable, '-c', 'import sys; sys.stdout.write("{0}\\n")'.format(output)]


def stderrCommand(output):
    return [sys.executable, '-c', 'import sys; sys.stderr.write("{0}\\n")'.format(output)]


def sleepCommand(dur):
    return [sys.executable, '-c', 'import time; time.sleep({0})'.format(dur)]


def scriptCommand(function, *args):
    runprocess_scripts = util.sibpath(__file__, 'runprocess-scripts.py')
    return [sys.executable, runprocess_scripts, function] + list(args)


def printArgsCommand():
    return [sys.executable, '-c', 'import sys; sys.stdout.write(repr(sys.argv[1:]))']


# windows returns rc 1, because exit status cannot indicate "signalled";
# posix returns rc -1 for "signalled"
FATAL_RC = -1
if runtime.platformType == 'win32':
    FATAL_RC = 1

# We would like to see debugging output in the test.log
runprocess.RunProcessPP.debug = True


class TestRunProcess(BasedirMixin, unittest.TestCase):

    def setUp(self):
        self.setUpBasedir()

    def tearDown(self):
        self.tearDownBasedir()

    def testCommandEncoding(self):
        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(b, u'abcd', self.basedir)
        self.assertIsInstance(s.command, bytes)
        self.assertIsInstance(s.fake_command, bytes)

    def testCommandEncodingList(self):
        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(b, [u'abcd', b'efg'], self.basedir)
        self.assertIsInstance(s.command[0], bytes)
        self.assertIsInstance(s.fake_command[0], bytes)

    def testCommandEncodingObfuscated(self):
        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(b,
                                  [bsutil.Obfuscated(u'abcd', u'ABCD')],
                                  self.basedir)
        self.assertIsInstance(s.command[0], bytes)
        self.assertIsInstance(s.fake_command[0], bytes)

    @defer.inlineCallbacks
    def testStart(self):
        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir)

        yield s.start()

        self.assertTrue({'stdout': nl('hello\n')} in b.updates, b.show())
        self.assertTrue({'rc': 0} in b.updates, b.show())

    @defer.inlineCallbacks
    def testNoStdout(self):
        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(
            b, stdoutCommand('hello'), self.basedir, sendStdout=False)

        yield s.start()

        self.failIf({'stdout': nl('hello\n')} in b.updates, b.show())
        self.assertTrue({'rc': 0} in b.updates, b.show())

    @defer.inlineCallbacks
    def testKeepStdout(self):
        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(
            b, stdoutCommand('hello'), self.basedir, keepStdout=True)

        yield s.start()

        self.assertTrue({'stdout': nl('hello\n')} in b.updates, b.show())
        self.assertTrue({'rc': 0} in b.updates, b.show())
        self.assertEqual(s.stdout, nl('hello\n'))

    @defer.inlineCallbacks
    def testStderr(self):
        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(b, stderrCommand("hello"), self.basedir)

        yield s.start()

        self.failIf({'stderr': nl('hello\n')} not in b.updates, b.show())
        self.assertTrue({'rc': 0} in b.updates, b.show())

    @defer.inlineCallbacks
    def testNoStderr(self):
        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(
            b, stderrCommand("hello"), self.basedir, sendStderr=False)

        yield s.start()

        self.failIf({'stderr': nl('hello\n')} in b.updates, b.show())
        self.assertTrue({'rc': 0} in b.updates, b.show())

    @defer.inlineCallbacks
    def test_incrementalDecoder(self):
        b = FakeWorkerForBuilder(self.basedir)
        b.unicode_encoding = "utf-8"
        s = runprocess.RunProcess(
            b, stderrCommand("hello"), self.basedir, sendStderr=True)
        pp = runprocess.RunProcessPP(s)
        # u"\N{SNOWMAN} when encoded to utf-8 bytes is b"\xe2\x98\x83"
        pp.outReceived(b"\xe2")
        pp.outReceived(b"\x98\x83")
        pp.errReceived(b"\xe2")
        pp.errReceived(b"\x98\x83")
        yield s.start()

        self.assertTrue({'stderr': u"\N{SNOWMAN}"} in b.updates)
        self.assertTrue({'stdout': u"\N{SNOWMAN}"} in b.updates)
        self.assertTrue({'rc': 0} in b.updates, b.show())

    @defer.inlineCallbacks
    def testInvalidUTF8(self):
        b = FakeWorkerForBuilder(self.basedir)
        b.unicode_encoding = "utf-8"
        s = runprocess.RunProcess(
            b, stderrCommand("hello"), self.basedir, sendStderr=True)
        pp = runprocess.RunProcessPP(s)
        INVALID_UTF8 = b"\xff"
        with self.assertRaises(UnicodeDecodeError):
            INVALID_UTF8.decode('utf-8')
        pp.outReceived(INVALID_UTF8)
        yield s.start()
        stdout = [up['stdout'] for up in b.updates if 'stdout' in up][0]
        # On Python < 2.7 bytes is used, on Python >= 2.7 unicode
        self.assertIn(stdout, (b'\xef\xbf\xbd', u'\ufffd'))
        self.assertTrue({'rc': 0} in b.updates, b.show())

    @defer.inlineCallbacks
    def testKeepStderr(self):
        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(
            b, stderrCommand("hello"), self.basedir, keepStderr=True)

        yield s.start()

        self.assertTrue({'stderr': nl('hello\n')} in b.updates, b.show())
        self.assertTrue({'rc': 0} in b.updates, b.show())
        self.assertEqual(s.stderr, nl('hello\n'))

    @defer.inlineCallbacks
    def testStringCommand(self):
        b = FakeWorkerForBuilder(self.basedir)
        # careful!  This command must execute the same on windows and UNIX
        s = runprocess.RunProcess(b, 'echo hello', self.basedir)

        yield s.start()

        self.assertTrue({'stdout': nl('hello\n')} in b.updates, b.show())
        self.assertTrue({'rc': 0} in b.updates, b.show())

    def testObfuscatedCommand(self):
        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(b,
                                  [('obfuscated', 'abcd', 'ABCD')],
                                  self.basedir)
        self.assertEqual(s.command, [b'abcd'])
        self.assertEqual(s.fake_command, [b'ABCD'])

    @defer.inlineCallbacks
    def testMultiWordStringCommand(self):
        b = FakeWorkerForBuilder(self.basedir)
        # careful!  This command must execute the same on windows and UNIX
        s = runprocess.RunProcess(b, 'echo Happy Days and Jubilation',
                                  self.basedir)

        # no quoting occurs
        exp = nl('Happy Days and Jubilation\n')
        yield s.start()

        self.assertTrue({'stdout': exp} in b.updates, b.show())
        self.assertTrue({'rc': 0} in b.updates, b.show())

    @defer.inlineCallbacks
    def testInitialStdinUnicode(self):
        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(
            b, catCommand(), self.basedir, initialStdin=u'hello')

        yield s.start()

        self.assertTrue({'stdout': nl('hello')} in b.updates, b.show())
        self.assertTrue({'rc': 0} in b.updates, b.show())

    @defer.inlineCallbacks
    def testMultiWordStringCommandQuotes(self):
        b = FakeWorkerForBuilder(self.basedir)
        # careful!  This command must execute the same on windows and UNIX
        s = runprocess.RunProcess(b, 'echo "Happy Days and Jubilation"',
                                  self.basedir)

        if runtime.platformType == "win32":
            # echo doesn't parse out the quotes, so they come through in the
            # output
            exp = nl('"Happy Days and Jubilation"\n')
        else:
            exp = nl('Happy Days and Jubilation\n')
        yield s.start()

        self.assertTrue({'stdout': exp} in b.updates, b.show())
        self.assertTrue({'rc': 0} in b.updates, b.show())

    @defer.inlineCallbacks
    def testTrickyArguments(self):
        # make sure non-trivial arguments are passed verbatim
        b = FakeWorkerForBuilder(self.basedir)

        args = [
            'Happy Days and Jubilation',  # spaces
            r'''!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~''',  # special characters
            '%PATH%',  # Windows variable expansions
            # Expansions get an argument of their own, because the Windows
            # shell doesn't treat % as special unless it surrounds a
            # variable name.
        ]

        s = runprocess.RunProcess(b, printArgsCommand() + args, self.basedir)
        yield s.start()

        self.assertTrue({'stdout': nl(repr(args))} in b.updates, b.show())
        self.assertTrue({'rc': 0} in b.updates, b.show())

    @defer.inlineCallbacks
    @compat.skipUnlessPlatformIs("win32")
    def testPipeString(self):
        b = FakeWorkerForBuilder(self.basedir)
        # this is highly contrived, but it proves the point.
        cmd = sys.executable + \
            ' -c "import sys; sys.stdout.write(\'b\\na\\n\')" | sort'
        s = runprocess.RunProcess(b, cmd, self.basedir)

        yield s.start()

        self.assertTrue({'stdout': nl('a\nb\n')} in b.updates, b.show())
        self.assertTrue({'rc': 0} in b.updates, b.show())

    @defer.inlineCallbacks
    def testCommandTimeout(self):
        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(b, sleepCommand(10), self.basedir, timeout=5)
        clock = task.Clock()
        s._reactor = clock

        d = s.start()
        clock.advance(6)
        yield d

        self.assertTrue(
            {'stdout': nl('hello\n')} not in b.updates, b.show())
        self.assertTrue({'rc': FATAL_RC} in b.updates, b.show())

    @defer.inlineCallbacks
    def testCommandMaxTime(self):
        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(b, sleepCommand(10), self.basedir, maxTime=5)
        clock = task.Clock()
        s._reactor = clock

        d = s.start()
        clock.advance(6)  # should knock out maxTime
        yield d

        self.assertTrue(
            {'stdout': nl('hello\n')} not in b.updates, b.show())
        self.assertTrue({'rc': FATAL_RC} in b.updates, b.show())

    @compat.skipUnlessPlatformIs("posix")
    @defer.inlineCallbacks
    def test_stdin_closed(self):
        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(b,
                                  scriptCommand('assert_stdin_closed'),
                                  self.basedir,
                                  # if usePTY=True, stdin is never closed
                                  usePTY=False,
                                  logEnviron=False)
        yield s.start()

        self.assertTrue({'rc': 0} in b.updates, b.show())

    @compat.usesFlushLoggedErrors
    def test_startCommand_exception(self):
        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(b, ['whatever'], self.basedir)

        # set up to cause an exception in _startCommand
        def _startCommand(*args, **kwargs):
            raise RuntimeError()
        s._startCommand = _startCommand

        d = s.start()

        def check(err):
            err.trap(AbandonChain)
            stderr = []
            # Here we're checking that the exception starting up the command
            # actually gets propagated back to the master in stderr.
            for u in b.updates:
                if 'stderr' in u:
                    stderr.append(u['stderr'])
            stderr = "".join(stderr)
            self.assertTrue("RuntimeError" in stderr, stderr)
        d.addBoth(check)
        d.addBoth(lambda _: self.flushLoggedErrors())
        return d

    @defer.inlineCallbacks
    def testLogEnviron(self):
        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir,
                                  environ={"FOO": "BAR"})

        yield s.start()

        headers = "".join([list(update.values())[0]
                           for update in b.updates if list(update) == ["header"]])
        self.assertTrue("FOO=BAR" in headers, "got:\n" + headers)

    @defer.inlineCallbacks
    def testNoLogEnviron(self):
        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir,
                                  environ={"FOO": "BAR"}, logEnviron=False)

        yield s.start()

        headers = "".join([list(update.values())[0]
                           for update in b.updates if list(update) == ["header"]])
        self.assertTrue("FOO=BAR" not in headers, "got:\n" + headers)

    @defer.inlineCallbacks
    def testEnvironExpandVar(self):
        b = FakeWorkerForBuilder(self.basedir)
        environ = {"EXPND": "-${PATH}-",
                   "DOESNT_EXPAND": "-${---}-",
                   "DOESNT_FIND": "-${DOESNT_EXISTS}-"}
        s = runprocess.RunProcess(
            b, stdoutCommand('hello'), self.basedir, environ=environ)

        yield s.start()

        headers = "".join([list(update.values())[0]
                           for update in b.updates if list(update) == ["header"]])
        self.assertTrue("EXPND=-$" not in headers, "got:\n" + headers)
        self.assertTrue("DOESNT_FIND=--" in headers, "got:\n" + headers)
        self.assertTrue(
            "DOESNT_EXPAND=-${---}-" in headers, "got:\n" + headers)

    @defer.inlineCallbacks
    def testUnsetEnvironVar(self):
        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir,
                                  environ={"PATH": None})

        yield s.start()

        headers = "".join([list(update.values())[0]
                           for update in b.updates if list(update) == ["header"]])
        self.assertFalse(
            re.match('\bPATH=', headers), "got:\n" + headers)

    @defer.inlineCallbacks
    def testEnvironPythonPath(self):
        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir,
                                  environ={"PYTHONPATH": 'a'})

        yield s.start()

        headers = "".join([list(update.values())[0]
                           for update in b.updates if list(update) == ["header"]])
        self.assertFalse(re.match('\bPYTHONPATH=a{0}'.format(os.pathsep), headers),
                         "got:\n" + headers)

    @defer.inlineCallbacks
    def testEnvironArray(self):
        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir,
                                  environ={"FOO": ['a', 'b']})

        yield s.start()

        headers = "".join([list(update.values())[0]
                           for update in b.updates if list(update) == ["header"]])
        self.assertFalse(re.match('\bFOO=a{0}b\b'.format(os.pathsep), headers),
                         "got:\n" + headers)

    def testEnvironInt(self):
        b = FakeWorkerForBuilder(self.basedir)
        with self.assertRaises(RuntimeError):
            runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir,
                                  environ={"BUILD_NUMBER": 13})

    def _test_spawnAsBatch(self, cmd, comspec):

        def spawnProcess(processProtocol, executable, args=(), env=None,
                         path=None, uid=None, gid=None, usePTY=False, childFDs=None):
            self.assertTrue(args[0].lower().endswith("cmd.exe"),
                            "{0} is not cmd.exe".format(args[0]))

        self.patch(runprocess.reactor, "spawnProcess", spawnProcess)
        tempEnviron = os.environ.copy()
        if 'COMSPEC' not in tempEnviron:
            tempEnviron['COMSPEC'] = comspec
        self.patch(os, "environ", tempEnviron)
        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(b, cmd, self.basedir)
        s.pp = runprocess.RunProcessPP(s)
        s.deferred = defer.Deferred()
        d = s._spawnAsBatch(s.pp, s.command, "args",
                            tempEnviron, "path", False)
        return d

    def test_spawnAsBatchCommandString(self):
        return self._test_spawnAsBatch("dir c:/", "cmd.exe")

    def test_spawnAsBatchCommandList(self):
        return self._test_spawnAsBatch(stdoutCommand('hello'), "cmd.exe /c")

    def test_spawnAsBatchCommandWithNonAscii(self):
        return self._test_spawnAsBatch(u"echo \u6211", "cmd.exe")

    def test_spawnAsBatchCommandListWithNonAscii(self):
        return self._test_spawnAsBatch(['echo', u"\u6211"], "cmd.exe /c")


class TestPOSIXKilling(BasedirMixin, unittest.TestCase):

    if runtime.platformType != "posix":
        skip = "not a POSIX platform"

    def setUp(self):
        self.pidfiles = []
        self.setUpBasedir()

    def tearDown(self):
        # make sure all of the subprocesses are dead
        for pidfile in self.pidfiles:
            if not os.path.exists(pidfile):
                continue
            with open(pidfile) as f:
                pid = f.read()
            if not pid:
                return
            pid = int(pid)
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

        # and clean up leftover pidfiles
        for pidfile in self.pidfiles:
            if os.path.exists(pidfile):
                os.unlink(pidfile)

        self.tearDownBasedir()

    def newPidfile(self):
        pidfile = os.path.abspath("test-{0}.pid".format(len(self.pidfiles)))
        if os.path.exists(pidfile):
            os.unlink(pidfile)
        self.pidfiles.append(pidfile)
        return pidfile

    def waitForPidfile(self, pidfile):
        # wait for a pidfile, and return the pid via a Deferred
        until = time.time() + 10
        d = defer.Deferred()

        def poll():
            if reactor.seconds() > until:
                d.errback(RuntimeError(
                    "pidfile {0} never appeared".format(pidfile)))
                return
            if os.path.exists(pidfile):
                try:
                    with open(pidfile) as f:
                        pid = int(f.read())
                except (IOError, TypeError, ValueError):
                    pid = None

                if pid is not None:
                    d.callback(pid)
                    return
            reactor.callLater(0.01, poll)
        poll()  # poll right away
        return d

    def assertAlive(self, pid):
        try:
            os.kill(pid, 0)
        except OSError:
            self.fail("pid {0} still alive".format(pid))

    def assertDead(self, pid, timeout=5):
        log.msg("checking pid {0!r}".format(pid))

        def check():
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
        self.fail("pid {0} still alive after {1}s".format(pid, timeout))

    # tests

    def test_simple_interruptSignal(self):
        return self.test_simple('TERM')

    def test_simple(self, interruptSignal=None):

        # test a simple process that just sleeps waiting to die
        pidfile = self.newPidfile()
        self.pid = None

        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(b,
                                  scriptCommand(
                                      'write_pidfile_and_sleep', pidfile),
                                  self.basedir)
        if interruptSignal is not None:
            s.interruptSignal = interruptSignal
        runproc_d = s.start()

        pidfile_d = self.waitForPidfile(pidfile)

        def check_alive(pid):
            self.pid = pid  # for use in check_dead
            # test that the process is still alive
            self.assertAlive(pid)
            # and tell the RunProcess object to kill it
            s.kill("diaf")
        pidfile_d.addCallback(check_alive)

        def check_dead(_):
            self.assertDead(self.pid)
        runproc_d.addCallback(check_dead)
        return defer.gatherResults([pidfile_d, runproc_d])

    def test_sigterm(self, interruptSignal=None):

        # Tests that the process will receive SIGTERM if sigtermTimeout
        # is not None
        pidfile = self.newPidfile()
        self.pid = None
        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(b,
                                  scriptCommand(
                                      'write_pidfile_and_sleep', pidfile),
                                  self.basedir, sigtermTime=1)
        runproc_d = s.start()
        pidfile_d = self.waitForPidfile(pidfile)
        self.receivedSIGTERM = False

        def check_alive(pid):
            # Create a mock process that will check if we receive SIGTERM
            mock_process = Mock(wraps=s.process)
            mock_process.pgid = None  # Skips over group SIGTERM
            mock_process.pid = pid
            process = s.process

            def _mock_signalProcess(sig):
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

        def check_dead(_):
            self.assertEqual(self.receivedSIGTERM, True)
            self.assertDead(self.pid)
        runproc_d.addCallback(check_dead)
        return defer.gatherResults([pidfile_d, runproc_d])

    def test_pgroup_usePTY(self):
        return self.do_test_pgroup(usePTY=True)

    def test_pgroup_no_usePTY(self):
        return self.do_test_pgroup(usePTY=False)

    def test_pgroup_no_usePTY_no_pgroup(self):
        # note that this configuration is not *used*, but that it is
        # still supported, and correctly fails to kill the child process
        return self.do_test_pgroup(usePTY=False, useProcGroup=False,
                                   expectChildSurvival=True)

    @defer.inlineCallbacks
    def do_test_pgroup(self, usePTY, useProcGroup=True,
                       expectChildSurvival=False):
        # test that a process group gets killed
        parent_pidfile = self.newPidfile()
        self.parent_pid = None
        child_pidfile = self.newPidfile()
        self.child_pid = None

        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(b,
                                  scriptCommand(
                                      'spawn_child', parent_pidfile, child_pidfile),
                                  self.basedir,
                                  usePTY=usePTY,
                                  useProcGroup=useProcGroup)
        runproc_d = s.start()

        # wait for both processes to start up, then call s.kill
        parent_pidfile_d = self.waitForPidfile(parent_pidfile)
        child_pidfile_d = self.waitForPidfile(child_pidfile)
        pidfiles_d = defer.gatherResults([parent_pidfile_d, child_pidfile_d])

        def got_pids(pids):
            self.parent_pid, self.child_pid = pids
        pidfiles_d.addCallback(got_pids)

        def kill(_):
            s.kill("diaf")
        pidfiles_d.addCallback(kill)

        # check that both processes are dead after RunProcess is done
        yield defer.gatherResults([pidfiles_d, runproc_d])

        self.assertDead(self.parent_pid)
        if expectChildSurvival:
            self.assertAlive(self.child_pid)
        else:
            self.assertDead(self.child_pid)

    def test_double_fork_usePTY(self):
        return self.do_test_double_fork(usePTY=True)

    def test_double_fork_no_usePTY(self):
        return self.do_test_double_fork(usePTY=False)

    def test_double_fork_no_usePTY_no_pgroup(self):
        # note that this configuration is not *used*, but that it is
        # still supported, and correctly fails to kill the child process
        return self.do_test_double_fork(usePTY=False, useProcGroup=False,
                                        expectChildSurvival=True)

    @defer.inlineCallbacks
    def do_test_double_fork(self, usePTY, useProcGroup=True,
                            expectChildSurvival=False):
        # when a spawned process spawns another process, and then dies itself
        # (either intentionally or accidentally), we should be able to clean up
        # the child.
        parent_pidfile = self.newPidfile()
        self.parent_pid = None
        child_pidfile = self.newPidfile()
        self.child_pid = None

        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(b,
                                  scriptCommand(
                                      'double_fork', parent_pidfile, child_pidfile),
                                  self.basedir,
                                  usePTY=usePTY,
                                  useProcGroup=useProcGroup)
        runproc_d = s.start()

        # wait for both processes to start up, then call s.kill
        parent_pidfile_d = self.waitForPidfile(parent_pidfile)
        child_pidfile_d = self.waitForPidfile(child_pidfile)
        pidfiles_d = defer.gatherResults([parent_pidfile_d, child_pidfile_d])

        def got_pids(pids):
            self.parent_pid, self.child_pid = pids
        pidfiles_d.addCallback(got_pids)

        def kill(_):
            s.kill("diaf")
        pidfiles_d.addCallback(kill)

        # check that both processes are dead after RunProcess is done
        yield defer.gatherResults([pidfiles_d, runproc_d])

        self.assertDead(self.parent_pid)
        if expectChildSurvival:
            self.assertAlive(self.child_pid)
        else:
            self.assertDead(self.child_pid)


class TestLogging(BasedirMixin, unittest.TestCase):

    def setUp(self):
        self.setUpBasedir()

    def tearDown(self):
        self.tearDownBasedir()

    def testSendStatus(self):
        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir)
        s.sendStatus({'stdout': nl('hello\n')})
        self.assertEqual(b.updates, [{'stdout': nl('hello\n')}], b.show())

    def testSendBuffered(self):
        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir)
        s._addToBuffers('stdout', 'hello ')
        s._addToBuffers('stdout', 'world')
        s._sendBuffers()
        self.assertEqual(b.updates, [{'stdout': 'hello world'}], b.show())

    def testSendBufferedInterleaved(self):
        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir)
        s._addToBuffers('stdout', 'hello ')
        s._addToBuffers('stderr', 'DIEEEEEEE')
        s._addToBuffers('stdout', 'world')
        s._sendBuffers()
        self.assertEqual(b.updates, [
            {'stdout': 'hello '},
            {'stderr': 'DIEEEEEEE'},
            {'stdout': 'world'},
        ])

    def testSendChunked(self):
        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir)
        data = "x" * int(runprocess.RunProcess.CHUNK_LIMIT * 3 / 2)
        s._addToBuffers('stdout', data)
        s._sendBuffers()
        self.assertEqual(len(b.updates), 2)

    def testSendNotimeout(self):
        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir)
        data = "x" * (runprocess.RunProcess.BUFFER_SIZE + 1)
        s._addToBuffers('stdout', data)
        self.assertEqual(len(b.updates), 1)

    def testSendLog(self):
        b = FakeWorkerForBuilder(self.basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir)
        s._addToBuffers(('log', 'stdout'), 'hello ')
        s._sendBuffers()
        self.assertEqual(b.updates, [
            {'log': ('stdout', 'hello ')},
        ])


class TestLogFileWatcher(BasedirMixin, unittest.TestCase):

    def setUp(self):
        self.setUpBasedir()

    def tearDown(self):
        self.tearDownBasedir()

    def makeRP(self):
        b = FakeWorkerForBuilder(self.basedir)
        rp = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir)
        return rp

    def tempLogFile(self, prefix):
        return tempfile.NamedTemporaryFile(
            prefix=prefix + '_', suffix='.log', mode='w', delete=False)

    def test_statFile_missing(self):
        rp = self.makeRP()
        with self.tempLogFile('statfile') as f:
            pass
        os.remove(f.name)
        lf = runprocess.LogFileWatcher(rp, 'test', f.name, False)
        self.assertFalse(lf.statFile(), "statfile.log doesn't exist")

    def test_statFile_exists(self):
        rp = self.makeRP()
        with self.tempLogFile('statfile') as f:
            f.write('hi')
        lf = runprocess.LogFileWatcher(rp, 'test', f.name, False)
        st = lf.statFile()
        self.assertEqual(
            st and st[2], 2, "statfile.log exists and size is correct")
        os.remove(f.name)

    def test_invalid_utf8(self):
        # create the log file watcher first
        rp = self.makeRP()
        with self.tempLogFile('invalid_utf8') as f:
            pass
        os.remove(f.name)
        lf = runprocess.LogFileWatcher(rp, 'test', f.name,
                                       follow=False, poll=False)
        # now write to the log file
        INVALID_UTF8 = b'before\xffafter'
        with open(f.name, 'wb') as log_file:
            log_file.write(INVALID_UTF8)
        # the watcher picks up the changed log
        lf.poll()
        # flush she buffer
        rp._sendBuffers()
        # the log file content was captured and the invalid byte replaced with \ufffd (the
        # replacement character, often a black diamond with a white question mark)
        REPLACED = u'before\ufffdafter'
        self.assertEqual(rp.builder.updates, [{'log': ('test', REPLACED)}])
        # cleanup
        lf.stop()
        os.remove(f.name)
