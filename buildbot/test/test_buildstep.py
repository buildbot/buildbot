# -*- test-case-name: buildbot.test.test_buildstep -*-

# test cases for buildbot.process.buildstep

from twisted.trial import unittest

from buildbot import interfaces
from buildbot.process import buildstep

# have to subclass LogObserver in order to test it, since the default
# implementations of outReceived() and errReceived() do nothing
class MyLogObserver(buildstep.LogObserver):
    def __init__(self):
        self._out = []                  # list of chunks
        self._err = []

    def outReceived(self, data):
        self._out.append(data)

    def errReceived(self, data):
        self._err.append(data)

class ObserverTestCase(unittest.TestCase):
    observer_cls = None                 # must be set by subclass

    def setUp(self):
        self.observer = self.observer_cls()

    def _logStdout(self, chunk):
        # why does LogObserver.logChunk() take 'build', 'step', and
        # 'log' arguments when it clearly doesn't use them for anything?
        self.observer.logChunk(None, None, None, interfaces.LOG_CHANNEL_STDOUT, chunk)

    def _logStderr(self, chunk):
        self.observer.logChunk(None, None, None, interfaces.LOG_CHANNEL_STDERR, chunk)

    def _assertStdout(self, expect_lines):
        self.assertEqual(self.observer._out, expect_lines)

    def _assertStderr(self, expect_lines):
        self.assertEqual(self.observer._err, expect_lines)

class LogObserver(ObserverTestCase):

    observer_cls = MyLogObserver

    def testLogChunk(self):
        self._logStdout("foo")
        self._logStderr("argh")
        self._logStdout(" wubba\n")
        self._logStderr("!!!\n")

        self._assertStdout(["foo", " wubba\n"])
        self._assertStderr(["argh", "!!!\n"])

# again, have to subclass LogLineObserver in order to test it, because the
# default implementations of data-receiving methods are empty
class MyLogLineObserver(buildstep.LogLineObserver):
    def __init__(self):
        #super(MyLogLineObserver, self).__init__()
        buildstep.LogLineObserver.__init__(self)

        self._out = []                  # list of lines
        self._err = []

    def outLineReceived(self, line):
        self._out.append(line)

    def errLineReceived(self, line):
        self._err.append(line)

class LogLineObserver(ObserverTestCase):
    observer_cls = MyLogLineObserver

    def testLineBuffered(self):
        # no challenge here: we feed it chunks that are already lines
        # (like a program writing to stdout in line-buffered mode)
        self._logStdout("stdout line 1\n")
        self._logStdout("stdout line 2\n")
        self._logStderr("stderr line 1\n")
        self._logStdout("stdout line 3\n")

        self._assertStdout(["stdout line 1",
                            "stdout line 2",
                            "stdout line 3"])
        self._assertStderr(["stderr line 1"])
        
    def testShortBrokenLines(self):
        self._logStdout("stdout line 1 starts ")
        self._logStderr("an intervening line of error\n")
        self._logStdout("and continues ")
        self._logStdout("but finishes here\n")
        self._logStderr("more error\n")
        self._logStdout("and another line of stdout\n")

        self._assertStdout(["stdout line 1 starts and continues but finishes here",
                            "and another line of stdout"])
        self._assertStderr(["an intervening line of error",
                            "more error"])

    def testLongLine(self):
        chunk = "." * 1024
        self._logStdout(chunk)
        self._logStdout(chunk)
        self._logStdout(chunk)
        self._logStdout(chunk)
        self._logStdout(chunk)
        self._logStdout("\n")

        self._assertStdout([chunk * 5])
        self._assertStderr([])

    def testBigChunk(self):
        chunk = "." * 5000
        self._logStdout(chunk)
        self._logStdout("\n")

        self._assertStdout([chunk])
        self._assertStderr([])

    def testReallyLongLine(self):
        # A single line of > 16384 bytes is dropped on the floor (bug #201).
        # In real life, I observed such a line being broken into chunks of
        # 4095 bytes, so that's how I'm breaking it here.
        self.observer.setMaxLineLength(65536)
        chunk = "." * 4095
        self._logStdout(chunk)
        self._logStdout(chunk)
        self._logStdout(chunk)
        self._logStdout(chunk)          # now we're up to 16380 bytes
        self._logStdout("12345\n")

        self._assertStdout([chunk*4 + "12345"])
        self._assertStderr([])
