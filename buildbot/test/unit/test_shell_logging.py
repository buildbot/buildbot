from twisted.trial import unittest

from buildbot.slave.commands import SlaveShellCommand, ShellCommand

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

class TestLogging(unittest.TestCase):
    def testSendStatus(self):
        basedir = "test_shell_logging.logging.sendStatus"
        b = FakeSlaveBuilder(False, basedir)
        s = ShellCommand(b, ['echo', 'hello'], basedir)
        s.sendStatus({'stdout': 'hello\n'})
        self.failUnlessEqual(b.updates, [{'stdout': 'hello\n'}])

    def testSendBuffered(self):
        basedir = "test_shell_logging.logging.sendBuffered"
        b = FakeSlaveBuilder(False, basedir)
        s = ShellCommand(b, ['echo', 'hello'], basedir)
        s._addToBuffers('stdout', 'hello ')
        s._addToBuffers('stdout', 'world')
        s._sendBuffers()
        self.failUnlessEqual(b.updates, [{'stdout': 'hello world'}])

    def testSendBufferedInterleaved(self):
        basedir = "test_shell_logging.logging.sendBufferedInterleaved"
        b = FakeSlaveBuilder(False, basedir)
        s = ShellCommand(b, ['echo', 'hello'], basedir)
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
        basedir = "test_shell_logging.logging.sendBufferedChunked"
        b = FakeSlaveBuilder(False, basedir)
        s = ShellCommand(b, ['echo', 'hello'], basedir)
        data = "x" * ShellCommand.CHUNK_LIMIT * 2
        s._addToBuffers('stdout', data)
        s._sendBuffers()
        self.failUnless(len(b.updates), 2)

    def testSendNotimeout(self):
        basedir = "test_shell_logging.logging.sendNotimeout"
        b = FakeSlaveBuilder(False, basedir)
        s = ShellCommand(b, ['echo', 'hello'], basedir)
        data = "x" * (ShellCommand.BUFFER_SIZE + 1)
        s._addToBuffers('stdout', data)
        self.failUnless(len(b.updates), 1)
