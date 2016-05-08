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

import os
import re
import signal
import sys
import time

from mock import Mock
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import task
from twisted.python import log
from twisted.python import runtime
from twisted.python import util
from twisted.trial import unittest

from buildslave import util as bsutil
from buildslave import runprocess
from buildslave.exceptions import AbandonChain
from buildslave.test.fake.slavebuilder import FakeSlaveBuilder
from buildslave.test.util import compat
from buildslave.test.util.misc import BasedirMixin
from buildslave.test.util.misc import nl


def catCommand():
    return [sys.executable, '-c', 'import sys; sys.stdout.write(sys.stdin.read())']


def stdoutCommand(output):
    return [sys.executable, '-c', 'import sys; sys.stdout.write("%s\\n")' % output]


def stderrCommand(output):
    return [sys.executable, '-c', 'import sys; sys.stderr.write("%s\\n")' % output]


def sleepCommand(dur):
    return [sys.executable, '-c', 'import time; time.sleep(%d)' % dur]


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
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(b, u'abcd', self.basedir)
        self.assertIsInstance(s.command, str)
        self.assertIsInstance(s.fake_command, str)

    def testCommandEncodingList(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(b, [u'abcd', 'efg'], self.basedir)
        self.assertIsInstance(s.command[0], str)
        self.assertIsInstance(s.fake_command[0], str)

    def testCommandEncodingObfuscated(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(b,
                                  [bsutil.Obfuscated(u'abcd', u'ABCD')],
                                  self.basedir)
        self.assertIsInstance(s.command[0], str)
        self.assertIsInstance(s.fake_command[0], str)

    def testStart(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir)

        d = s.start()

        def check(ign):
            self.failUnless({'stdout': nl('hello\n')} in b.updates, b.show())
            self.failUnless({'rc': 0} in b.updates, b.show())
        d.addCallback(check)
        return d

    def testNoStdout(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(
            b, stdoutCommand('hello'), self.basedir, sendStdout=False)

        d = s.start()

        def check(ign):
            self.failIf({'stdout': nl('hello\n')} in b.updates, b.show())
            self.failUnless({'rc': 0} in b.updates, b.show())
        d.addCallback(check)
        return d

    def testKeepStdout(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(
            b, stdoutCommand('hello'), self.basedir, keepStdout=True)

        d = s.start()

        def check(ign):
            self.failUnless({'stdout': nl('hello\n')} in b.updates, b.show())
            self.failUnless({'rc': 0} in b.updates, b.show())
            self.failUnlessEquals(s.stdout, nl('hello\n'))
        d.addCallback(check)
        return d

    def testStderr(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(b, stderrCommand("hello"), self.basedir)

        d = s.start()

        def check(ign):
            self.failIf({'stderr': nl('hello\n')} not in b.updates, b.show())
            self.failUnless({'rc': 0} in b.updates, b.show())
        d.addCallback(check)
        return d

    def testNoStderr(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(
            b, stderrCommand("hello"), self.basedir, sendStderr=False)

        d = s.start()

        def check(ign):
            self.failIf({'stderr': nl('hello\n')} in b.updates, b.show())
            self.failUnless({'rc': 0} in b.updates, b.show())
        d.addCallback(check)
        return d

    def testKeepStderr(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(
            b, stderrCommand("hello"), self.basedir, keepStderr=True)

        d = s.start()

        def check(ign):
            self.failUnless({'stderr': nl('hello\n')} in b.updates, b.show())
            self.failUnless({'rc': 0} in b.updates, b.show())
            self.failUnlessEquals(s.stderr, nl('hello\n'))
        d.addCallback(check)
        return d

    def testStringCommand(self):
        b = FakeSlaveBuilder(False, self.basedir)
        # careful!  This command must execute the same on windows and UNIX
        s = runprocess.RunProcess(b, 'echo hello', self.basedir)

        d = s.start()

        def check(ign):
            self.failUnless({'stdout': nl('hello\n')} in b.updates, b.show())
            self.failUnless({'rc': 0} in b.updates, b.show())
        d.addCallback(check)
        return d

    def testObfuscatedCommand(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(b,
                                  [('obfuscated', 'abcd', 'ABCD')],
                                  self.basedir)
        self.assertEqual(s.command, ['abcd'])
        self.assertEqual(s.fake_command, ['ABCD'])

    def testMultiWordStringCommand(self):
        b = FakeSlaveBuilder(False, self.basedir)
        # careful!  This command must execute the same on windows and UNIX
        s = runprocess.RunProcess(b, 'echo Happy Days and Jubilation',
                                  self.basedir)

        # no quoting occurs
        exp = nl('Happy Days and Jubilation\n')
        d = s.start()

        def check(ign):
            self.failUnless({'stdout': exp} in b.updates, b.show())
            self.failUnless({'rc': 0} in b.updates, b.show())
        d.addCallback(check)
        return d

    def testInitialStdinUnicode(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(
            b, catCommand(), self.basedir, initialStdin=u'hello')

        d = s.start()

        def check(ign):
            self.failUnless({'stdout': nl('hello')} in b.updates, b.show())
            self.failUnless({'rc': 0} in b.updates, b.show())
        d.addCallback(check)
        return d

    def testMultiWordStringCommandQuotes(self):
        b = FakeSlaveBuilder(False, self.basedir)
        # careful!  This command must execute the same on windows and UNIX
        s = runprocess.RunProcess(b, 'echo "Happy Days and Jubilation"',
                                  self.basedir)

        if runtime.platformType == "win32":
            # echo doesn't parse out the quotes, so they come through in the
            # output
            exp = nl('"Happy Days and Jubilation"\n')
        else:
            exp = nl('Happy Days and Jubilation\n')
        d = s.start()

        def check(ign):
            self.failUnless({'stdout': exp} in b.updates, b.show())
            self.failUnless({'rc': 0} in b.updates, b.show())
        d.addCallback(check)
        return d

    def testTrickyArguments(self):
        # make sure non-trivial arguments are passed verbatim
        b = FakeSlaveBuilder(False, self.basedir)

        args = [
            'Happy Days and Jubilation',  # spaces
            r'''!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~''',  # special characters
            '%PATH%',  # Windows variable expansions
            # Expansions get an argument of their own, because the Windows
            # shell doesn't treat % as special unless it surrounds a
            # variable name.
        ]

        s = runprocess.RunProcess(b, printArgsCommand() + args, self.basedir)
        d = s.start()

        def check(ign):
            self.failUnless({'stdout': nl(repr(args))} in b.updates, b.show())
            self.failUnless({'rc': 0} in b.updates, b.show())
        d.addCallback(check)
        return d

    @compat.skipUnlessPlatformIs("win32")
    def testPipeString(self):
        b = FakeSlaveBuilder(False, self.basedir)
        # this is highly contrived, but it proves the point.
        cmd = sys.executable + \
            ' -c "import sys; sys.stdout.write(\'b\\na\\n\')" | sort'
        s = runprocess.RunProcess(b, cmd, self.basedir)

        d = s.start()

        def check(ign):
            self.failUnless({'stdout': nl('a\nb\n')} in b.updates, b.show())
            self.failUnless({'rc': 0} in b.updates, b.show())
        d.addCallback(check)
        return d

    def testCommandTimeout(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(b, sleepCommand(10), self.basedir, timeout=5)
        clock = task.Clock()
        s._reactor = clock
        d = s.start()

        def check(ign):
            self.failUnless(
                {'stdout': nl('hello\n')} not in b.updates, b.show())
            self.failUnless({'rc': FATAL_RC} in b.updates, b.show())
        d.addCallback(check)
        clock.advance(6)
        return d

    def testCommandMaxTime(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(b, sleepCommand(10), self.basedir, maxTime=5)
        clock = task.Clock()
        s._reactor = clock
        d = s.start()

        def check(ign):
            self.failUnless(
                {'stdout': nl('hello\n')} not in b.updates, b.show())
            self.failUnless({'rc': FATAL_RC} in b.updates, b.show())
        d.addCallback(check)
        clock.advance(6)  # should knock out maxTime
        return d

    @compat.skipUnlessPlatformIs("posix")
    def test_stdin_closed(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(b,
                                  scriptCommand('assert_stdin_closed'),
                                  self.basedir,
                                  # if usePTY=True, stdin is never closed
                                  usePTY=False,
                                  logEnviron=False)
        d = s.start()

        def check(ign):
            self.failUnless({'rc': 0} in b.updates, b.show())
        d.addCallback(check)
        return d

    @compat.usesFlushLoggedErrors
    def test_startCommand_exception(self):
        b = FakeSlaveBuilder(False, self.basedir)
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
            # actually gets propogated back to the master in stderr.
            for u in b.updates:
                if 'stderr' in u:
                    stderr.append(u['stderr'])
            stderr = "".join(stderr)
            self.failUnless("RuntimeError" in stderr, stderr)
        d.addBoth(check)
        d.addBoth(lambda _: self.flushLoggedErrors())
        return d

    def testLogEnviron(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir,
                                  environ={"FOO": "BAR"})

        d = s.start()

        def check(ign):
            headers = "".join([list(update.values())[0]
                               for update in b.updates if list(update) == ["header"]])
            self.failUnless("FOO=BAR" in headers, "got:\n" + headers)
        d.addCallback(check)
        return d

    def testNoLogEnviron(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir,
                                  environ={"FOO": "BAR"}, logEnviron=False)

        d = s.start()

        def check(ign):
            headers = "".join([list(update.values())[0]
                               for update in b.updates if list(update) == ["header"]])
            self.failUnless("FOO=BAR" not in headers, "got:\n" + headers)
        d.addCallback(check)
        return d

    def testEnvironExpandVar(self):
        b = FakeSlaveBuilder(False, self.basedir)
        environ = {"EXPND": "-${PATH}-",
                   "DOESNT_EXPAND": "-${---}-",
                   "DOESNT_FIND": "-${DOESNT_EXISTS}-"}
        s = runprocess.RunProcess(
            b, stdoutCommand('hello'), self.basedir, environ=environ)

        d = s.start()

        def check(ign):
            headers = "".join([list(update.values())[0]
                               for update in b.updates if list(update) == ["header"]])
            self.failUnless("EXPND=-$" not in headers, "got:\n" + headers)
            self.failUnless("DOESNT_FIND=--" in headers, "got:\n" + headers)
            self.failUnless(
                "DOESNT_EXPAND=-${---}-" in headers, "got:\n" + headers)
        d.addCallback(check)
        return d

    def testUnsetEnvironVar(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir,
                                  environ={"PATH": None})

        d = s.start()

        def check(ign):
            headers = "".join([list(update.values())[0]
                               for update in b.updates if list(update) == ["header"]])
            self.failUnless(
                not re.match('\bPATH=', headers), "got:\n" + headers)
        d.addCallback(check)
        return d

    def testEnvironPythonPath(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir,
                                  environ={"PYTHONPATH": 'a'})

        d = s.start()

        def check(ign):
            headers = "".join([list(update.values())[0]
                               for update in b.updates if list(update) == ["header"]])
            self.failUnless(not re.match('\bPYTHONPATH=a%s' % (os.pathsep), headers),
                            "got:\n" + headers)
        d.addCallback(check)
        return d

    def testEnvironArray(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir,
                                  environ={"FOO": ['a', 'b']})

        d = s.start()

        def check(ign):
            headers = "".join([list(update.values())[0]
                               for update in b.updates if list(update) == ["header"]])
            self.failUnless(not re.match('\bFOO=a%sb\b' % (os.pathsep), headers),
                            "got:\n" + headers)
        d.addCallback(check)
        return d

    def testEnvironInt(self):
        b = FakeSlaveBuilder(False, self.basedir)
        self.assertRaises(RuntimeError, lambda:
                          runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir,
                                                environ={"BUILD_NUMBER": 13}))


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
            pid = open(pidfile).read()
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
        pidfile = os.path.abspath("test-%d.pid" % len(self.pidfiles))
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
                d.errback(RuntimeError("pidfile %s never appeared" % pidfile))
                return
            if os.path.exists(pidfile):
                try:
                    pid = int(open(pidfile).read())
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
            self.fail("pid %d still alive" % (pid,))

    def assertDead(self, pid, timeout=5):
        log.msg("checking pid %r" % (pid,))

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
        self.fail("pid %d still alive after %ds" % (pid, timeout))

    # tests

    def test_simple_interruptSignal(self):
        return self.test_simple('TERM')

    def test_simple(self, interruptSignal=None):

        # test a simple process that just sleeps waiting to die
        pidfile = self.newPidfile()
        self.pid = None

        b = FakeSlaveBuilder(False, self.basedir)
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
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(b,
                                  scriptCommand(
                                      'write_pidfile_and_sleep', pidfile),
                                  self.basedir, sigtermTime=1)
        runproc_d = s.start()
        pidfile_d = self.waitForPidfile(pidfile)
        self.receivedSIGTERM = False

        def check_alive(pid):
            # Create a mock process that will check if we recieve SIGTERM
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
            self.failUnlessEqual(self.receivedSIGTERM, True)
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

    def do_test_pgroup(self, usePTY, useProcGroup=True,
                       expectChildSurvival=False):
        # test that a process group gets killed
        parent_pidfile = self.newPidfile()
        self.parent_pid = None
        child_pidfile = self.newPidfile()
        self.child_pid = None

        b = FakeSlaveBuilder(False, self.basedir)
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
        d = defer.gatherResults([pidfiles_d, runproc_d])

        def check_dead(_):
            self.assertDead(self.parent_pid)
            if expectChildSurvival:
                self.assertAlive(self.child_pid)
            else:
                self.assertDead(self.child_pid)
        d.addCallback(check_dead)
        return d

    def test_double_fork_usePTY(self):
        return self.do_test_double_fork(usePTY=True)

    def test_double_fork_no_usePTY(self):
        return self.do_test_double_fork(usePTY=False)

    def test_double_fork_no_usePTY_no_pgroup(self):
        # note that this configuration is not *used*, but that it is
        # still supported, and correctly fails to kill the child process
        return self.do_test_double_fork(usePTY=False, useProcGroup=False,
                                        expectChildSurvival=True)

    def do_test_double_fork(self, usePTY, useProcGroup=True,
                            expectChildSurvival=False):
        # when a spawned process spawns another process, and then dies itself
        # (either intentionally or accidentally), we should be able to clean up
        # the child.
        parent_pidfile = self.newPidfile()
        self.parent_pid = None
        child_pidfile = self.newPidfile()
        self.child_pid = None

        b = FakeSlaveBuilder(False, self.basedir)
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
        d = defer.gatherResults([pidfiles_d, runproc_d])

        def check_dead(_):
            self.assertDead(self.parent_pid)
            if expectChildSurvival:
                self.assertAlive(self.child_pid)
            else:
                self.assertDead(self.child_pid)
        d.addCallback(check_dead)
        return d


class TestLogging(BasedirMixin, unittest.TestCase):

    def setUp(self):
        self.setUpBasedir()

    def tearDown(self):
        self.tearDownBasedir()

    def testSendStatus(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir)
        s.sendStatus({'stdout': nl('hello\n')})
        self.failUnlessEqual(b.updates, [{'stdout': nl('hello\n')}], b.show())

    def testSendBuffered(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir)
        s._addToBuffers('stdout', 'hello ')
        s._addToBuffers('stdout', 'world')
        s._sendBuffers()
        self.failUnlessEqual(b.updates, [{'stdout': 'hello world'}], b.show())

    def testSendBufferedInterleaved(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir)
        s._addToBuffers('stdout', 'hello ')
        s._addToBuffers('stderr', 'DIEEEEEEE')
        s._addToBuffers('stdout', 'world')
        s._sendBuffers()
        self.failUnlessEqual(b.updates, [
            {'stdout': 'hello '},
            {'stderr': 'DIEEEEEEE'},
            {'stdout': 'world'},
        ])

    def testSendChunked(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir)
        data = "x" * (runprocess.RunProcess.CHUNK_LIMIT * 3 / 2)
        s._addToBuffers('stdout', data)
        s._sendBuffers()
        self.failUnlessEqual(len(b.updates), 2)

    def testSendNotimeout(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir)
        data = "x" * (runprocess.RunProcess.BUFFER_SIZE + 1)
        s._addToBuffers('stdout', data)
        self.failUnlessEqual(len(b.updates), 1)


class TestLogFileWatcher(BasedirMixin, unittest.TestCase):

    def setUp(self):
        self.setUpBasedir()

    def tearDown(self):
        self.tearDownBasedir()

    def makeRP(self):
        b = FakeSlaveBuilder(False, self.basedir)
        rp = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir)
        return rp

    def test_statFile_missing(self):
        rp = self.makeRP()
        if os.path.exists('statfile.log'):
            os.remove('statfile.log')
        lf = runprocess.LogFileWatcher(rp, 'test', 'statfile.log', False)
        self.assertFalse(lf.statFile(), "statfile.log doesn't exist")

    def test_statFile_exists(self):
        rp = self.makeRP()
        open('statfile.log', 'w').write('hi')
        lf = runprocess.LogFileWatcher(rp, 'test', 'statfile.log', False)
        st = lf.statFile()
        self.assertEqual(
            st and st[2], 2, "statfile.log exists and size is correct")
        os.remove('statfile.log')
