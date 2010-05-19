import sys, re

from twisted.trial import unittest
from twisted.internet import task, defer

from buildbot.slave.commands.base import SlaveShellCommand, ShellCommand, Obfuscated, \
    DummyCommand, WaitCommand, waitCommandRegistry, AbandonChain
from buildbot.slave.commands.utils import getCommand

class FakeSlaveBuilder:
    debug = False
    def __init__(self, usePTY, basedir):
        self.updates = []
        self.basedir = basedir
        self.usePTY = usePTY

    def sendUpdate(self, data):
        if self.debug:
            print "FakeSlaveBuilder.sendUpdate", data
        self.updates.append(data)

def stdoutCommand(output):
    return [sys.executable, '-c', 'import sys; sys.stdout.write("%s\\n")' % output]

def stderrCommand(output):
    return [sys.executable, '-c', 'import sys; sys.stdout.write("%s\\n")' % output]

class TestShellCommand(unittest.TestCase):
    def testStart(self):
        basedir = "test_slave_commands_base.shellcommand.start"
        b = FakeSlaveBuilder(False, basedir)
        s = ShellCommand(b, stdoutCommand('hello'), basedir)

        d = s.start()
        def check(ign):
            self.failUnless({'stdout': 'hello\n'} in b.updates)
            self.failUnless({'rc': 0} in b.updates)
        d.addCallback(check)
        return d

    def testNoStdout(self):
        basedir = "test_slave_commands_base.shellcommand.nostdout"
        b = FakeSlaveBuilder(False, basedir)
        s = ShellCommand(b, stdoutCommand('hello'), basedir, sendStdout=False)

        d = s.start()
        def check(ign):
            self.failIf({'stdout': 'hello\n'} in b.updates)
            self.failUnless({'rc': 0} in b.updates)
        d.addCallback(check)
        return d

    def testKeepStdout(self):
        basedir = "test_slave_commands_base.shellcommand.keepstdout"
        b = FakeSlaveBuilder(False, basedir)
        s = ShellCommand(b, stdoutCommand('hello'), basedir, keepStdout=True)

        d = s.start()
        def check(ign):
            self.failUnless({'stdout': 'hello\n'} in b.updates)
            self.failUnless({'rc': 0} in b.updates)
            self.failUnlessEquals(s.stdout, 'hello\n')
        d.addCallback(check)
        return d

    def testStderr(self):
        basedir = "test_slave_commands_base.shellcommand.stderr"
        b = FakeSlaveBuilder(False, basedir)
        s = ShellCommand(b, [sys.executable, '-c', 'import sys; sys.stderr.write("hello\\n")'], basedir)

        d = s.start()
        def check(ign):
            self.failIf({'stderr': 'hello\n'} not in b.updates)
            self.failUnless({'rc': 0} in b.updates)
        d.addCallback(check)
        return d

    def testNoStderr(self):
        basedir = "test_slave_commands_base.shellcommand.nostderr"
        b = FakeSlaveBuilder(False, basedir)
        s = ShellCommand(b, [sys.executable, '-c', 'import sys; sys.stderr.write("hello\\n")'], basedir, sendStderr=False)

        d = s.start()
        def check(ign):
            self.failIf({'stderr': 'hello\n'} in b.updates)
            self.failUnless({'rc': 0} in b.updates)
        d.addCallback(check)
        return d

    def testKeepStderr(self):
        basedir = "test_slave_commands_base.shellcommand.keepstderr"
        b = FakeSlaveBuilder(False, basedir)
        s = ShellCommand(b, [sys.executable, '-c', 'import sys; sys.stderr.write("hello\\n")'], basedir, keepStderr=True)

        d = s.start()
        def check(ign):
            self.failUnless({'stderr': 'hello\n'} in b.updates)
            self.failUnless({'rc': 0} in b.updates)
            self.failUnlessEquals(s.stderr, 'hello\n')
        d.addCallback(check)
        return d

    def testKeepStdout(self):
        basedir = "test_slave_commands_base.shellcommand.keepstdout"
        b = FakeSlaveBuilder(False, basedir)
        s = ShellCommand(b, stdoutCommand('hello'), basedir, keepStdout=True)

        d = s.start()
        def check(ign):
            self.failUnless({'stdout': 'hello\n'} in b.updates)
            self.failUnless({'rc': 0} in b.updates)
            self.failUnlessEquals(s.stdout, 'hello\n')
        d.addCallback(check)
        return d

    def testStringCommand(self):
        basedir = "test_slave_commands_base.shellcommand.string"
        b = FakeSlaveBuilder(False, basedir)
        s = ShellCommand(b, 'echo hello', basedir)

        d = s.start()
        def check(ign):
            self.failUnless({'stdout': 'hello\n'} in b.updates)
            self.failUnless({'rc': 0} in b.updates)
        d.addCallback(check)
        return d

    def testCommandTimeout(self):
        basedir = "test_slave_commands_base.shellcommand.timeout"
        b = FakeSlaveBuilder(False, basedir)
        s = ShellCommand(b, 'sleep 10; echo hello', basedir, timeout=5)
        clock = task.Clock()
        s._reactor = clock
        d = s.start()
        def check(ign):
            self.failUnless({'stdout': 'hello\n'} not in b.updates)
            self.failUnless({'rc': -1} in b.updates, b.updates)
        d.addCallback(check)
        clock.advance(6)
        return d

    def testCommandMaxTime(self):
        basedir = "test_slave_commands_base.shellcommand.maxtime"
        b = FakeSlaveBuilder(False, basedir)
        s = ShellCommand(b, 'sleep 10; echo hello', basedir, maxTime=5)
        clock = task.Clock()
        s._reactor = clock
        d = s.start()
        def check(ign):
            self.failUnless({'stdout': 'hello\n'} not in b.updates)
            self.failUnless({'rc': -1} in b.updates, b.updates)
        d.addCallback(check)
        clock.advance(6)
        return d

    def testBadCommand(self):
        basedir = "test_slave_commands_base.shellcommand.badcommand"
        b = FakeSlaveBuilder(False, basedir)
        s = ShellCommand(b, ['command_that_doesnt_exist.exe'], basedir)
        s.workdir = 1
        d = s.start()
        def check(err):
            self.flushLoggedErrors()
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
        return d

    def testLogEnviron(self):
        basedir = "test_slave_commands_base.shellcommand.start"
        b = FakeSlaveBuilder(False, basedir)
        s = ShellCommand(b, stdoutCommand('hello'), basedir, environ={"FOO": "BAR"})

        d = s.start()
        def check(ign):
            headers = "".join([update.values()[0] for update in b.updates if update.keys() == ["header"] ])
            self.failUnless("FOO=BAR\n" in headers)
        d.addCallback(check)
        return d

    def testNoLogEnviron(self):
        basedir = "test_slave_commands_base.shellcommand.start"
        b = FakeSlaveBuilder(False, basedir)
        s = ShellCommand(b, stdoutCommand('hello'), basedir, environ={"FOO": "BAR"}, logEnviron=False)

        d = s.start()
        def check(ign):
            headers = "".join([update.values()[0] for update in b.updates if update.keys() == ["header"] ])
            self.failUnless("FOO=BAR\n" not in headers)
        d.addCallback(check)
        return d

    def testEnvironExpandVar(self):
        basedir = "test_slave_commands_base.shellcommand.start"
        b = FakeSlaveBuilder(False, basedir)
        environ = {"EXPND": "-${PATH}-",
                   "DOESNT_EXPAND": "-${---}-",
                   "DOESNT_FIND": "-${DOESNT_EXISTS}-"}
        s = ShellCommand(b, stdoutCommand('hello'), basedir, environ=environ)

        d = s.start()
        def check(ign):
            headers = "".join([update.values()[0] for update in b.updates if update.keys() == ["header"] ])
            self.failUnless("EXPND=-$" not in headers)
            self.failUnless("DOESNT_FIND=--\n" in headers)
            self.failUnless("DOESNT_EXPAND=-${---}-\n"  in headers)
        d.addCallback(check)
        return d

    def testUnsetEnvironVar(self):
        basedir = "test_slave_commands_base.shellcommand.start"
        b = FakeSlaveBuilder(False, basedir)
        s = ShellCommand(b, stdoutCommand('hello'), basedir, environ={"PATH":None})

        d = s.start()
        def check(ign):
            headers = "".join([update.values()[0] for update in b.updates if update.keys() == ["header"] ])
            self.failUnless(not re.match('\bPATH=',headers))
        d.addCallback(check)
        return d

class TestLogging(unittest.TestCase):
    def testSendStatus(self):
        basedir = "test_slave_commands_base.logging.sendStatus"
        b = FakeSlaveBuilder(False, basedir)
        s = ShellCommand(b, stdoutCommand('hello'), basedir)
        s.sendStatus({'stdout': 'hello\n'})
        self.failUnlessEqual(b.updates, [{'stdout': 'hello\n'}])

    def testSendBuffered(self):
        basedir = "test_slave_commands_base.logging.sendBuffered"
        b = FakeSlaveBuilder(False, basedir)
        s = ShellCommand(b, stdoutCommand('hello'), basedir)
        s._addToBuffers('stdout', 'hello ')
        s._addToBuffers('stdout', 'world')
        s._sendBuffers()
        self.failUnlessEqual(b.updates, [{'stdout': 'hello world'}])

    def testSendBufferedInterleaved(self):
        basedir = "test_slave_commands_base.logging.sendBufferedInterleaved"
        b = FakeSlaveBuilder(False, basedir)
        s = ShellCommand(b, stdoutCommand('hello'), basedir)
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
        s = ShellCommand(b, stdoutCommand('hello'), basedir)
        data = "x" * ShellCommand.CHUNK_LIMIT * 2
        s._addToBuffers('stdout', data)
        s._sendBuffers()
        self.failUnless(len(b.updates), 2)

    def testSendNotimeout(self):
        basedir = "test_slave_commands_base.logging.sendNotimeout"
        b = FakeSlaveBuilder(False, basedir)
        s = ShellCommand(b, stdoutCommand('hello'), basedir)
        data = "x" * (ShellCommand.BUFFER_SIZE + 1)
        s._addToBuffers('stdout', data)
        self.failUnless(len(b.updates), 1)

class TestObfuscated(unittest.TestCase):
    def testSimple(self):
        c = Obfuscated('real', '****')
        self.failUnlessEqual(str(c), '****')
        self.failUnlessEqual(repr(c), "'****'")

    def testObfuscatedCommand(self):
        cmd = ['echo', Obfuscated('password', '*******')]

        self.failUnlessEqual(['echo', 'password'], Obfuscated.get_real(cmd))
        self.failUnlessEqual(['echo', '*******'], Obfuscated.get_fake(cmd))

    def testObfuscatedNonString(self):
        cmd = ['echo', 1]
        self.failUnlessEqual(['echo', '1'], Obfuscated.get_real(cmd))
        self.failUnlessEqual(['echo', '1'], Obfuscated.get_fake(cmd))

    def testObfuscatedNonList(self):
        cmd = 1
        self.failUnlessEqual(1, Obfuscated.get_real(cmd))
        self.failUnlessEqual(1, Obfuscated.get_fake(cmd))

class TestUtils(unittest.TestCase):
    def testGetCommand(self):
        self.failUnlessEqual(sys.executable, getCommand(sys.executable))

    def testGetBadCommand(self):
        self.failUnlessRaises(RuntimeError, getCommand, "bad_command_that_really_would_never_exist.bat")

class TestDummy(unittest.TestCase):
    def testDummy(self):
        basedir = "test_slave_commands_base.dummy.dummy"
        b = FakeSlaveBuilder(False, basedir)
        c = DummyCommand(b, 1, {})
        c._reactor = task.Clock()
        d = c.doStart()
        def _check(ign):
            self.failUnless({'rc': 0} in b.updates, b.updates)
            self.failUnless({'stdout': 'data'} in b.updates, b.updates)
        d.addCallback(_check)

        # Advance by 2 seconds so that doStatus gets fired
        c._reactor.advance(2)
        # Now advance by 5 seconds so that finished gets fired
        c._reactor.advance(5)

        return d

    def testDummyInterrupt(self):
        basedir = "test_slave_commands_base.dummy.interrupt"
        b = FakeSlaveBuilder(False, basedir)
        c = DummyCommand(b, 1, {})
        c._reactor = task.Clock()
        d = c.doStart()
        def _check(ign):
            self.failUnlessEqual(c.interrupted, True)
            self.failUnless({'rc': 1} in b.updates, b.updates)
            self.failUnless({'stdout': 'data'} in b.updates, b.updates)
        d.addCallback(_check)

        # Advance by 2 seconds so that doStatus gets fired
        c._reactor.advance(2)
        # Now interrupt it
        c.interrupt()

        return d

    def testDummyInterruptTwice(self):
        basedir = "test_slave_commands_base.dummy.interruptTwice"
        b = FakeSlaveBuilder(False, basedir)
        c = DummyCommand(b, 1, {})
        c._reactor = task.Clock()
        d = c.doStart()
        def _check(ign):
            self.failUnlessEqual(c.interrupted, True)
            self.failUnless({'rc': 1} in b.updates, b.updates)
            self.failUnless({'stdout': 'data'} not in b.updates, b.updates)
        d.addCallback(_check)

        # Don't advance the clock to precent doStatus from being fired

        # Now interrupt it, twice!
        c.interrupt()
        c._reactor.advance(1)
        c.interrupt()

        return d

class TestWait(unittest.TestCase):
    def testWait(self):
        basedir = "test_slave_commands_base.wait.wait"
        b = FakeSlaveBuilder(False, basedir)
        clock = task.Clock()

        def cb():
            d = defer.Deferred()
            clock.callLater(1, d.callback, None)
            return d

        waitCommandRegistry['foo'] = cb

        w = WaitCommand(b, 1, {'handle': 'foo'})
        w._reactor = clock

        d1 = w.doStart()

        def _check(ign):
            self.failUnless({'rc': 0} in b.updates, b.updates)
            self.failUnlessEqual(w.interrupted, False)
        d1.addCallback(_check)
        # Advance 1 second to get our callback called
        clock.advance(1)
        # Advance 1 second to call the callback's deferred (the d returned by
        # cb)
        clock.advance(1)
        return d1

    def testWaitInterrupt(self):
        basedir = "test_slave_commands_base.wait.interrupt"
        b = FakeSlaveBuilder(False, basedir)
        clock = task.Clock()

        def cb():
            d = defer.Deferred()
            clock.callLater(1, d.callback, None)
            return d

        waitCommandRegistry['foo'] = cb

        w = WaitCommand(b, 1, {'handle': 'foo'})
        w._reactor = clock

        d1 = w.doStart()

        def _check(ign):
            self.failUnless({'rc': 2} in b.updates, b.updates)
            self.failUnlessEqual(w.interrupted, True)
        d1.addCallback(_check)
        # Advance 1 second to get our callback called
        clock.advance(1)

        # Now interrupt it
        w.interrupt()
        # And again, to make sure nothing bad happened
        clock.advance(0.1)
        w.interrupt()
        return d1

    def testWaitFailed(self):
        basedir = "test_slave_commands_base.wait.failed"
        b = FakeSlaveBuilder(False, basedir)
        clock = task.Clock()

        def cb():
            d = defer.Deferred()
            clock.callLater(1, d.errback, AssertionError())
            return d

        waitCommandRegistry['foo'] = cb

        w = WaitCommand(b, 1, {'handle': 'foo'})
        w._reactor = clock

        d1 = w.doStart()

        def _check(ign):
            self.failUnless({'rc': 1} in b.updates, b.updates)
            self.failUnlessEqual(w.interrupted, False)
        d1.addCallback(_check)
        # Advance 1 second to get our callback called
        clock.advance(1)

        # Advance 1 second to call the callback's deferred (the d returned by
        # cb)
        clock.advance(1)
        return d1
