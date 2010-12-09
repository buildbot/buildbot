import sys
import re
import os

import twisted
from twisted.trial import unittest
from twisted.internet import task
from twisted.python import runtime

from buildslave.test.util.misc import nl, BasedirMixin
from buildslave.test.fake.slavebuilder import FakeSlaveBuilder
from buildslave.exceptions import AbandonChain
from buildslave import runprocess

def stdoutCommand(output):
    return [sys.executable, '-c', 'import sys; sys.stdout.write("%s\\n")' % output]

def stderrCommand(output):
    return [sys.executable, '-c', 'import sys; sys.stderr.write("%s\\n")' % output]

def sleepCommand(dur):
    return [sys.executable, '-c', 'import time; time.sleep(%d)' % dur]

# windows returns rc 1, because exit status cannot indicate "signalled";
# posix returns rc -1 for "signalled"
FATAL_RC = -1
if runtime.platformType  == 'win32':
    FATAL_RC = 1

# We would like to see debugging output in the test.log
runprocess.RunProcessPP.debug = True

class TestRunProcess(BasedirMixin, unittest.TestCase):
    def setUp(self):
        self.setUpBasedir()

    def tearDown(self):
        self.tearDownBasedir()

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
        s = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir, sendStdout=False)

        d = s.start()
        def check(ign):
            self.failIf({'stdout': nl('hello\n')} in b.updates, b.show())
            self.failUnless({'rc': 0} in b.updates, b.show())
        d.addCallback(check)
        return d

    def testKeepStdout(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir, keepStdout=True)

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
        s = runprocess.RunProcess(b, stderrCommand("hello"), self.basedir, sendStderr=False)

        d = s.start()
        def check(ign):
            self.failIf({'stderr': nl('hello\n')} in b.updates, b.show())
            self.failUnless({'rc': 0} in b.updates, b.show())
        d.addCallback(check)
        return d

    def testKeepStderr(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(b, stderrCommand("hello"), self.basedir, keepStderr=True)

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

    def testCommandTimeout(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(b, sleepCommand(10), self.basedir, timeout=5)
        clock = task.Clock()
        s._reactor = clock
        d = s.start()
        def check(ign):
            self.failUnless({'stdout': nl('hello\n')} not in b.updates, b.show())
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
            self.failUnless({'stdout': nl('hello\n')} not in b.updates, b.show())
            self.failUnless({'rc': FATAL_RC} in b.updates, b.show())
        d.addCallback(check)
        clock.advance(6) # should knock out maxTime
        return d

    def testBadCommand(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(b, ['command_that_doesnt_exist.exe'], self.basedir)
        s.workdir = 1 # cause an exception
        d = s.start()
        def check(err):
            err.trap(AbandonChain)
            stderr = []
            # Here we're checking that the exception starting up the command
            # actually gets propogated back to the master.
            for u in b.updates:
                if 'stderr' in u:
                    stderr.append(u['stderr'])
            stderr = "".join(stderr)
            self.failUnless("TypeError" in stderr, stderr)
        d.addBoth(check)
        d.addBoth(lambda _ : self.flushLoggedErrors())
        return d
    if twisted.version.major <= 9 and sys.version_info[:2] >= (2,7):
        testBadCommand.skip = "flushLoggedErrors does not work correctly on 9.0.0 and earlier with Python-2.7"

    def testLogEnviron(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir,
                            environ={"FOO": "BAR"})

        d = s.start()
        def check(ign):
            headers = "".join([update.values()[0] for update in b.updates if update.keys() == ["header"] ])
            self.failUnless("FOO=BAR" in headers, "got:\n" + headers)
        d.addCallback(check)
        return d

    def testNoLogEnviron(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir,
                            environ={"FOO": "BAR"}, logEnviron=False)

        d = s.start()
        def check(ign):
            headers = "".join([update.values()[0] for update in b.updates if update.keys() == ["header"] ])
            self.failUnless("FOO=BAR" not in headers, "got:\n" + headers)
        d.addCallback(check)
        return d

    def testEnvironExpandVar(self):
        b = FakeSlaveBuilder(False, self.basedir)
        environ = {"EXPND": "-${PATH}-",
                   "DOESNT_EXPAND": "-${---}-",
                   "DOESNT_FIND": "-${DOESNT_EXISTS}-"}
        s = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir, environ=environ)

        d = s.start()
        def check(ign):
            headers = "".join([update.values()[0] for update in b.updates if update.keys() == ["header"] ])
            self.failUnless("EXPND=-$" not in headers, "got:\n" + headers)
            self.failUnless("DOESNT_FIND=--" in headers, "got:\n" + headers)
            self.failUnless("DOESNT_EXPAND=-${---}-"  in headers, "got:\n" + headers)
        d.addCallback(check)
        return d

    def testUnsetEnvironVar(self):
        b = FakeSlaveBuilder(False, self.basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), self.basedir,
                            environ={"PATH":None})

        d = s.start()
        def check(ign):
            headers = "".join([update.values()[0] for update in b.updates if update.keys() == ["header"] ])
            self.failUnless(not re.match('\bPATH=',headers), "got:\n" + headers)
        d.addCallback(check)
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
        self.assertEqual(st and st[2], 2, "statfile.log exists and size is correct")
        os.remove('statfile.log')
