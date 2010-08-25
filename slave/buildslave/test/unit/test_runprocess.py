import sys
import re
import os

import twisted
from twisted.trial import unittest
from twisted.internet import task, defer
from twisted.python import runtime

from buildslave.test.util.misc import nl
from buildslave.test.fake.slavebuilder import FakeSlaveBuilder
from buildslave.exceptions import AbandonChain
from buildslave import runprocess

def stdoutCommand(output):
    return [sys.executable, '-c', 'import sys; sys.stdout.write("%s\\n")' % output]

def stderrCommand(output):
    return [sys.executable, '-c', 'import sys; sys.stdout.write("%s\\n")' % output]

# windows returns rc 1, because exit status cannot indicate "signalled";
# posix returns rc -1 for "signalled"
FATAL_RC = -1
if runtime.platformType  == 'win32':
    FATAL_RC = 1

class TestRunProcess(unittest.TestCase):
    def testStart(self):
        basedir = "test_slave_commands_base.runprocess.start"
        b = FakeSlaveBuilder(False, basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), basedir)

        d = s.start()
        def check(ign):
            self.failUnless({'stdout': nl('hello\n')} in b.updates, b.show())
            self.failUnless({'rc': 0} in b.updates, b.show())
        d.addCallback(check)
        return d

    def testNoStdout(self):
        basedir = "test_slave_commands_base.runprocess.nostdout"
        b = FakeSlaveBuilder(False, basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), basedir, sendStdout=False)

        d = s.start()
        def check(ign):
            self.failIf({'stdout': nl('hello\n')} in b.updates, b.show())
            self.failUnless({'rc': 0} in b.updates, b.show())
        d.addCallback(check)
        return d

    def testKeepStdout(self):
        basedir = "test_slave_commands_base.runprocess.keepstdout"
        b = FakeSlaveBuilder(False, basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), basedir, keepStdout=True)

        d = s.start()
        def check(ign):
            self.failUnless({'stdout': nl('hello\n')} in b.updates, b.show())
            self.failUnless({'rc': 0} in b.updates, b.show())
            self.failUnlessEquals(s.stdout, nl('hello\n'))
        d.addCallback(check)
        return d

    def testStderr(self):
        basedir = "test_slave_commands_base.runprocess.stderr"
        b = FakeSlaveBuilder(False, basedir)
        s = runprocess.RunProcess(b,
                [sys.executable, '-c', 'import sys; sys.stderr.write("hello\\n")'], basedir)

        d = s.start()
        def check(ign):
            self.failIf({'stderr': nl('hello\n')} not in b.updates, b.show())
            self.failUnless({'rc': 0} in b.updates, b.show())
        d.addCallback(check)
        return d

    def testNoStderr(self):
        basedir = "test_slave_commands_base.runprocess.nostderr"
        b = FakeSlaveBuilder(False, basedir)
        s = runprocess.RunProcess(b,
                [sys.executable, '-c', 'import sys; sys.stderr.write("hello\\n")'],
                basedir, sendStderr=False)

        d = s.start()
        def check(ign):
            self.failIf({'stderr': nl('hello\n')} in b.updates, b.show())
            self.failUnless({'rc': 0} in b.updates, b.show())
        d.addCallback(check)
        return d

    def testKeepStderr(self):
        basedir = "test_slave_commands_base.runprocess.keepstderr"
        b = FakeSlaveBuilder(False, basedir)
        s = runprocess.RunProcess(b,
                [sys.executable, '-c', 'import sys; sys.stderr.write("hello\\n")'],
                basedir, keepStderr=True)

        d = s.start()
        def check(ign):
            self.failUnless({'stderr': nl('hello\n')} in b.updates, b.show())
            self.failUnless({'rc': 0} in b.updates, b.show())
            self.failUnlessEquals(s.stderr, nl('hello\n'))
        d.addCallback(check)
        return d

    def testStringCommand(self):
        basedir = "test_slave_commands_base.runprocess.string"
        b = FakeSlaveBuilder(False, basedir)
        s = runprocess.RunProcess(b, 'echo hello', basedir)

        d = s.start()
        def check(ign):
            self.failUnless({'stdout': nl('hello\n')} in b.updates, b.show())
            self.failUnless({'rc': 0} in b.updates, b.show())
        d.addCallback(check)
        return d

    def testCommandTimeout(self):
        basedir = "test_slave_commands_base.runprocess.timeout"
        b = FakeSlaveBuilder(False, basedir)
        s = runprocess.RunProcess(b, 'sleep 10; echo hello', basedir, timeout=5)
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
        basedir = "test_slave_commands_base.runprocess.maxtime"
        b = FakeSlaveBuilder(False, basedir)
        s = runprocess.RunProcess(b, 'sleep 10; echo hello', basedir, maxTime=5)
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
        basedir = "test_slave_commands_base.runprocess.badcommand"
        b = FakeSlaveBuilder(False, basedir)
        s = runprocess.RunProcess(b, ['command_that_doesnt_exist.exe'], basedir)
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
        basedir = "test_slave_commands_base.runprocess.start"
        b = FakeSlaveBuilder(False, basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'),
                basedir, environ={"FOO": "BAR"})

        d = s.start()
        def check(ign):
            headers = "".join([update.values()[0] for update in b.updates if update.keys() == ["header"] ])
            self.failUnless("FOO=BAR" in headers, "got:\n" + headers)
        d.addCallback(check)
        return d

    def testNoLogEnviron(self):
        basedir = "test_slave_commands_base.runprocess.start"
        b = FakeSlaveBuilder(False, basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'),
                basedir, environ={"FOO": "BAR"}, logEnviron=False)

        d = s.start()
        def check(ign):
            headers = "".join([update.values()[0] for update in b.updates if update.keys() == ["header"] ])
            self.failUnless("FOO=BAR" not in headers, "got:\n" + headers)
        d.addCallback(check)
        return d

    def testEnvironExpandVar(self):
        basedir = "test_slave_commands_base.runprocess.start"
        b = FakeSlaveBuilder(False, basedir)
        environ = {"EXPND": "-${PATH}-",
                   "DOESNT_EXPAND": "-${---}-",
                   "DOESNT_FIND": "-${DOESNT_EXISTS}-"}
        s = runprocess.RunProcess(b, stdoutCommand('hello'), basedir, environ=environ)

        d = s.start()
        def check(ign):
            headers = "".join([update.values()[0] for update in b.updates if update.keys() == ["header"] ])
            self.failUnless("EXPND=-$" not in headers, "got:\n" + headers)
            self.failUnless("DOESNT_FIND=--" in headers, "got:\n" + headers)
            self.failUnless("DOESNT_EXPAND=-${---}-"  in headers, "got:\n" + headers)
        d.addCallback(check)
        return d

    def testUnsetEnvironVar(self):
        basedir = "test_slave_commands_base.runprocess.start"
        b = FakeSlaveBuilder(False, basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), basedir, environ={"PATH":None})

        d = s.start()
        def check(ign):
            headers = "".join([update.values()[0] for update in b.updates if update.keys() == ["header"] ])
            self.failUnless(not re.match('\bPATH=',headers), "got:\n" + headers)
        d.addCallback(check)
        return d

class TestLogging(unittest.TestCase):
    def testSendStatus(self):
        basedir = "test_slave_commands_base.logging.sendStatus"
        b = FakeSlaveBuilder(False, basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), basedir)
        s.sendStatus({'stdout': nl('hello\n')})
        self.failUnlessEqual(b.updates, [{'stdout': nl('hello\n')}], b.show())

    def testSendBuffered(self):
        basedir = "test_slave_commands_base.logging.sendBuffered"
        b = FakeSlaveBuilder(False, basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), basedir)
        s._addToBuffers('stdout', 'hello ')
        s._addToBuffers('stdout', 'world')
        s._sendBuffers()
        self.failUnlessEqual(b.updates, [{'stdout': 'hello world'}], b.show())

    def testSendBufferedInterleaved(self):
        basedir = "test_slave_commands_base.logging.sendBufferedInterleaved"
        b = FakeSlaveBuilder(False, basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), basedir)
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
        basedir = "test_slave_commands_base.logging.sendBufferedChunked"
        b = FakeSlaveBuilder(False, basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), basedir)
        data = "x" * (runprocess.RunProcess.CHUNK_LIMIT * 3 / 2)
        s._addToBuffers('stdout', data)
        s._sendBuffers()
        self.failUnlessEqual(len(b.updates), 2)

    def testSendNotimeout(self):
        basedir = "test_slave_commands_base.logging.sendNotimeout"
        b = FakeSlaveBuilder(False, basedir)
        s = runprocess.RunProcess(b, stdoutCommand('hello'), basedir)
        data = "x" * (runprocess.RunProcess.BUFFER_SIZE + 1)
        s._addToBuffers('stdout', data)
        self.failUnlessEqual(len(b.updates), 1)

class TestLogFileWatcher(unittest.TestCase):
    def makeRP(self):
        b = FakeSlaveBuilder(False, 'base')
        rp = runprocess.RunProcess(b, stdoutCommand('hello'), b.basedir)
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
