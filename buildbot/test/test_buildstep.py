# -*- test-case-name: buildbot.test.test_buildstep -*-

# test cases for buildbot.process.buildstep

from twisted.trial import unittest

from buildbot import interfaces
from buildbot.process import buildstep
from buildbot.process import mtrlogobserver
from buildbot.process import subunitlogobserver

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

class MyMtrLogObserver(mtrlogobserver.MtrLogObserver):
    def __init__(self):
        mtrlogobserver.MtrLogObserver.__init__(self, textLimit=3, testNameLimit=15)
        self.testFails = []
        self.testWarnLists = []
        # We don't have a buildstep in self.step.
        # So we'll just install ourself there, so we can check the call of
        # setProgress().
        # Same for self.step.step_status.setText()
        self.step = self
        self.step_status = self
        self.progresses = []
        self.text = []

    def setProgress(self, type, value):
        self.progresses.append((type, value))

    def setText(self, text):
        self.text = text

    def collectTestFail(self, testname, variant, result, info, text):
        self.testFails.append((testname, variant, result, info, text))

    def collectWarningTests(self, testList):
        self.testWarnLists.append(testList)

class MtrLogObserver(ObserverTestCase):
    observer_cls = MyMtrLogObserver

    def test1(self):
        self._logStdout("""
MySQL Version 5.1.35
==============================================================================
TEST                                      RESULT   TIME (ms)
------------------------------------------------------------
worker[3] Using MTR_BUILD_THREAD 252, with reserved ports 12520..12529
binlog.binlog_multi_engine               [ skipped ]  No ndbcluster tests(--skip-ndbcluster)
rpl.rpl_ssl 'row'                        [ pass ]  13976
***Warnings generated in error logs during shutdown after running tests: rpl.rpl_ssl
rpl.rpl_ssl 'mix'                        [ pass ]  13308
main.pool_of_threads                     w1 [ skipped ]  Test requires: 'have_pool_of_threads'
------------------------------------------------------------
The servers were restarted 613 times
mysql-test-run: *** ERROR: There were errors/warnings in server logs after running test cases.
All 1002 tests were successful.

Errors/warnings were found in logfiles during server shutdown after running the
following sequence(s) of tests:
    rpl.rpl_ssl
""")
        self.assertEqual(self.observer.progresses,
                         map((lambda (x): ('tests', x)), [1,2]))
        self.assertEqual(self.observer.testWarnLists, [["rpl.rpl_ssl"]])
        self.assertEqual(self.observer.testFails, [])
        self.assertEqual(self.observer.text[1:], ["W:rpl_ssl"])

    def test2(self):
        self._logStdout("""
Logging: mysql-test-run.pl  --force --skip-ndb
==============================================================================
TEST                                      RESULT   TIME (ms)
------------------------------------------------------------
binlog.binlog_multi_engine               [ skipped ]  No ndbcluster tests(--skip-ndbcluster)
rpl.rpl_sp 'mix'                         [ pass ]   8117

MTR's internal check of the test case 'rpl.rpl_sp' failed.
This is the diff of the states of the servers before and after the
test case was executed:
mysqltest: Logging to '/home/archivist/archivist-cnc/archivist-cnc/build/mysql-test/var/tmp/check-mysqld_2.log'.
--- /home/archivist/archivist-cnc/archivist-cnc/build/mysql-test/var/tmp/check-mysqld_2.result	2009-06-18 16:49:19.000000000 +0300
+++ /home/archivist/archivist-cnc/archivist-cnc/build/mysql-test/var/tmp/check-mysqld_2.reject	2009-06-18 16:49:29.000000000 +0300
@@ -523,7 +523,7 @@
 mysql.help_keyword	864336512
 mysql.help_relation	2554468794
 mysql.host	0
-mysql.proc	3342691386
+mysql.proc	3520745907

not ok

rpl.rpl_sp_effects 'row'                 [ pass ]   3789
rpl.rpl_temporary_errors 'mix'        w2 [ fail ]
        Test ended at 2009-06-18 16:21:28

CURRENT_TEST: rpl.rpl_temporary_errors
Retrying test, attempt(2/3)...

***Warnings generated in error logs during shutdown after running tests: rpl.rpl_temporary_errors
rpl.rpl_temporary_errors 'mix'           [ retry-pass ]   2108
rpl.rpl_trunc_temp 'stmt'                [ pass ]   2576
main.information_schema                  [ pass ]  106092
timer 5953: expired after 900 seconds
worker[1] Trying to dump core for [mysqltest - pid: 5975, winpid: 5975]
main.information_schema_all_engines      [ fail ]  timeout after 900 seconds
        Test ended at 2009-06-18 18:37:25
Retrying test, attempt(2/3)...

***Warnings generated in error logs during shutdown after running tests: main.handler_myisam main.ctype_ujis_ucs2 main.ctype_recoding
main.information_schema_chmod            [ pass ]     84
rpl.rpl_circular_for_4_hosts 'stmt'      [ pass ]  344547
timer 21612: expired after 21600 seconds
Test suite timeout! Terminating...
mysql-test-run: *** ERROR: Not all tests completed
""")
        self.assertEqual(self.observer.progresses,
                         map((lambda (x): ('tests', x)), [1,2,3,4,5,6,7,8]))
        self.assertEqual(self.observer.testWarnLists,
                         [["rpl.rpl_temporary_errors"],
                          ["main.handler_myisam", "main.ctype_ujis_ucs2", "main.ctype_recoding"]])
        failtext1 = """rpl.rpl_temporary_errors 'mix'        w2 [ fail ]
        Test ended at 2009-06-18 16:21:28

CURRENT_TEST: rpl.rpl_temporary_errors
Retrying test, attempt(2/3)...

"""
        failtext2 = """main.information_schema_all_engines      [ fail ]  timeout after 900 seconds
        Test ended at 2009-06-18 18:37:25
Retrying test, attempt(2/3)...

"""
        self.assertEqual(self.observer.testFails,
                         [ ("rpl.rpl_temporary_errors", "mix", "fail", "", failtext1),
                           ("main.information_schema_all_engines", "", "fail", "timeout after 900 seconds", failtext2)
                           ])
        self.assertEqual(self.observer.text[1:], ["F:information_s...", "F:rpl_temporary...", "W:ctype_recoding", "W:ctype_ujis_ucs2", "W:handler_myisam"])

class RemoteShellTest(unittest.TestCase):
    def testRepr(self):
        # Test for #352
        rsc = buildstep.RemoteShellCommand('.', ('sh', 'make'))
        testval = repr(rsc)
        rsc = buildstep.RemoteShellCommand('.', ['sh', 'make'])
        testval = repr(rsc)
        rsc = buildstep.RemoteShellCommand('.', 'make')
        testval = repr(rsc)


class SubunitLogObserver(subunitlogobserver.SubunitLogObserver):
    """Subclassed to allow testing behaviour without a real buildstep."""

    def __init__(self):
        # Skip this test if subunit is not installed.
        try:
            from subunit import TestProtocolServer
        except ImportError:
            raise unittest.SkipTest("subunit.TestProtocolServer not available")
        subunitlogobserver.SubunitLogObserver.__init__(self)
        self.testFails = []
        self.testWarnLists = []
        # We don't have a buildstep in self.step.
        # So we'll just install ourself there, so we can check the call of
        # setProgress().
        # Same for self.step.step_status.setText()
        self.step = self
        self.step_status = self
        self.progresses = []
        self.text = []

    def setProgress(self, type, value):
        self.progresses.append((type, value))

    def setText(self, text):
        self.text = text


class SubunitLogObserverTests(ObserverTestCase):
    observer_cls = SubunitLogObserver

    def test1(self):
        self._logStdout("""
test: foo
success: foo
test: bar
failure: bar [
string
]
test: gam
skip: gam
test: quux
xfail: quux
""")
        self.assertEqual(self.observer.progresses,
            [('tests', 1), ('tests', 2), ('tests failed', 1), ('tests', 3),
             ('tests failed', 2), ('tests', 4)])
