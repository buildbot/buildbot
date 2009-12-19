import sys
import re
import exceptions
from twisted.python import log
from twisted.internet import defer
from twisted.enterprise import adbapi
from buildbot.process.buildstep import LogLineObserver
from buildbot.steps.shell import Test

class EqConnectionPool(adbapi.ConnectionPool):
    """This class works the same way as
twisted.enterprise.adbapi.ConnectionPool. But it adds the ability to
compare connection pools for equality (by comparing the arguments
passed to the constructor).

This is useful when passing the ConnectionPool to a BuildStep, as
otherwise Buildbot will consider the buildstep (and hence the
containing buildfactory) to have changed every time the configuration
is reloaded.

It also sets some defaults differently from adbapi.ConnectionPool that
are more suitable for use in MTR.
"""
    def __init__(self, *args, **kwargs):
        self._eqKey = (args, kwargs)
        return adbapi.ConnectionPool.__init__(self,
                                              cp_reconnect=True, cp_min=1, cp_max=3,
                                              *args, **kwargs)

    def __eq__(self, other):
        if isinstance(other, EqConnectionPool):
            return self._eqKey == other._eqKey
        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)


class MtrTestFailData:
    def __init__(self, testname, variant, result, info, text, callback):
        self.testname = testname
        self.variant = variant
        self.result = result
        self.info = info
        self.text = text
        self.callback = callback

    def add(self, line):
        self.text+= line

    def fireCallback(self):
        return self.callback(self.testname, self.variant, self.result, self.info, self.text)


class MtrLogObserver(LogLineObserver):
    """
    Class implementing a log observer (can be passed to
    BuildStep.addLogObserver().

    It parses the output of mysql-test-run.pl as used in MySQL,
    MariaDB, Drizzle, etc.

    It counts number of tests run and uses it to provide more accurate
    completion estimates.

    It parses out test failures from the output and summarises the results on
    the Waterfall page. It also passes the information to methods that can be
    overridden in a subclass to do further processing on the information."""

    _line_re = re.compile(r"^([-._0-9a-zA-z]+)( '[a-z]+')?\s+(w[0-9]+\s+)?\[ (fail|pass) \]\s*(.*)$")
    _line_re2 = re.compile(r"^[-._0-9a-zA-z]+( '[a-z]+')?\s+(w[0-9]+\s+)?\[ [-a-z]+ \]")
    _line_re3 = re.compile(r"^\*\*\*Warnings generated in error logs during shutdown after running tests: (.*)")
    _line_re4 = re.compile(r"^The servers were restarted [0-9]+ times$")
    _line_re5 = re.compile(r"^Only\s+[0-9]+\s+of\s+[0-9]+\s+completed.$")

    def __init__(self, textLimit=5, testNameLimit=16):
        self.textLimit = textLimit
        self.testNameLimit = testNameLimit
        self.numTests = 0
        self.testFail = None
        self.failList = []
        self.warnList = []
        LogLineObserver.__init__(self)

    def setLog(self, loog):
        LogLineObserver.setLog(self, loog)
        d= loog.waitUntilFinished()
        d.addCallback(lambda l: self.closeTestFail())

    def outLineReceived(self, line):
        stripLine = line.strip("\r\n")
        m = self._line_re.search(stripLine)
        if m:
            testname, variant, worker, result, info = m.groups()
            self.closeTestFail()
            self.numTests += 1
            self.step.setProgress('tests', self.numTests)

            if result == "fail":
                if variant == None:
                    variant = ""
                else:
                    variant = variant[2:-1]
                self.openTestFail(testname, variant, result, info, stripLine + "\n")

        else:
            m = self._line_re3.search(stripLine)
            if m:
                stuff = m.group(1)
                self.closeTestFail()
                testList = stuff.split(" ")
                self.doCollectWarningTests(testList)

            elif (self._line_re2.search(stripLine) or
                  self._line_re4.search(stripLine) or
                  self._line_re5.search(stripLine) or
                  stripLine == "Test suite timeout! Terminating..." or
                  stripLine.startswith("mysql-test-run: *** ERROR: Not all tests completed") or
                  (stripLine.startswith("------------------------------------------------------------")
                   and self.testFail != None)):
                self.closeTestFail()

            else:
                self.addTestFailOutput(stripLine + "\n")

    def openTestFail(self, testname, variant, result, info, line):
        self.testFail = MtrTestFailData(testname, variant, result, info, line, self.doCollectTestFail)

    def addTestFailOutput(self, line):
        if self.testFail != None:
            self.testFail.add(line)

    def closeTestFail(self):
        if self.testFail != None:
            self.testFail.fireCallback()
            self.testFail = None

    def addToText(self, src, dst):
        lastOne = None
        count = 0
        for t in src:
            if t != lastOne:
                dst.append(t)
                count += 1
                if count >= self.textLimit:
                    break

    def makeText(self, done):
        if done:
            text = ["test"]
        else:
            text = ["testing"]
        fails = self.failList[:]
        fails.sort()
        self.addToText(fails, text)
        warns = self.warnList[:]
        warns.sort()
        self.addToText(warns, text)
        return text

    # Update waterfall status.
    def updateText(self):
        self.step.step_status.setText(self.makeText(False))

    strip_re = re.compile(r"^[a-z]+\.")

    def displayTestName(self, testname):

        displayTestName = self.strip_re.sub("", testname)

        if len(displayTestName) > self.testNameLimit:
            displayTestName = displayTestName[:(self.testNameLimit-2)] + "..."
        return displayTestName

    def doCollectTestFail(self, testname, variant, result, info, text):
        self.failList.append("F:" + self.displayTestName(testname))
        self.updateText()
        self.collectTestFail(testname, variant, result, info, text)

    def doCollectWarningTests(self, testList):
        for t in testList:
            self.warnList.append("W:" + self.displayTestName(t))
        self.updateText()
        self.collectWarningTests(testList)

    # These two methods are overridden to actually do something with the data.
    def collectTestFail(self, testname, variant, result, info, text):
        pass
    def collectWarningTests(self, testList):
        pass

class MTR(Test):
    """
    Build step that runs mysql-test-run.pl, as used in MySQL, Drizzle,
    MariaDB, etc.

    It uses class MtrLogObserver to parse test results out from the
    output of mysql-test-run.pl, providing better completion time
    estimates and summarising test failures on the waterfall page.

    It also provides access to mysqld server error logs from the test
    run to help debugging any problems.

    Optionally, it can insert into a database data about the test run,
    including details of any test failures.

    Parameters:

    textLimit
        Maximum number of test failures to show on the waterfall page
        (to not flood the page in case of a large number of test
        failures. Defaults to 5.

    testNameLimit
        Maximum length of test names to show unabbreviated in the
        waterfall page, to avoid excessive column width. Defaults to 16.

    parallel
        Value of --parallel option used for mysql-test-run.pl (number
        of processes used to run the test suite in parallel). Defaults
        to 4. This is used to determine the number of server error log
        files to download from the slave. Specifying a too high value
        does not hurt (as nonexisting error logs will be ignored),
        however if using --parallel value greater than the default it
        needs to be specified, or some server error logs will be
        missing.

    dbpool
        An instance of twisted.enterprise.adbapi.ConnectionPool, or None.
        Defaults to None. If specified, results are inserted into the database
        using the ConnectionPool.

        The class process.mtrlogobserver.EqConnectionPool subclass of
        ConnectionPool can be useful to pass as value for dbpool, to
        avoid having config reloads think the Buildstep is changed
        just because it gets a new ConnectionPool instance (even
        though connection parameters are unchanged).

    autoCreateTables
        Boolean, defaults to False. If True (and dbpool is specified), the
        necessary database tables will be created automatically if they do
        not exist already. Alternatively, the tables can be created manually
        from the SQL statements found in the mtrlogobserver.py source file.

    test_type
    test_info
        Two descriptive strings that will be inserted in the database tables if
        dbpool is specified."""

    def __init__(self, dbpool=None, test_type="mysql-test-run", test_info="",
                 autoCreateTables=False, textLimit=5, testNameLimit=16,
                 parallel=4, logfiles = {}, lazylogfiles = True, **kwargs):

        # Add mysql server logfiles.
        for mtr in range(0, parallel+1):
            for mysqld in range(1, 4+1):
                if mtr == 0:
                    logname = "mysqld.%d.err" % mysqld
                    filename = "mysql-test/var/log/mysqld.%d.err" % mysqld
                else:
                    logname = "mysqld.%d.err.%d" % (mysqld, mtr)
                    filename = "mysql-test/var/%d/log/mysqld.%d.err" % (mtr, mysqld)
                logfiles[logname] = filename
        Test.__init__(self, logfiles=logfiles, lazylogfiles=lazylogfiles, **kwargs)
        self.dbpool = dbpool
        self.test_type = test_type
        self.test_info = test_info
        self.autoCreateTables = autoCreateTables
        self.textLimit = textLimit
        self.testNameLimit = testNameLimit
        self.parallel = parallel
        self.progressMetrics += ('tests',)

        self.addFactoryArguments(dbpool=self.dbpool,
                                 test_type=self.test_type,
                                 test_info=self.test_info,
                                 autoCreateTables=self.autoCreateTables,
                                 textLimit=self.textLimit,
                                 testNameLimit=self.testNameLimit,
                                 parallel=self.parallel)

    def start(self):
        self.myMtr = self.MyMtrLogObserver(textLimit=self.textLimit,
                                           testNameLimit=self.testNameLimit)
        self.addLogObserver("stdio", self.myMtr)
        # Insert a row for this test run into the database and set up
        # build properties, then start the command proper.
        d = self.registerInDB()
        d.addCallback(self.afterRegisterInDB)
        d.addErrback(self.failed)

    def getText(self, command, results):
        return self.myMtr.makeText(True)

    def runInteractionWithRetry(self, actionFn, *args, **kw):
        """
        Run a database transaction with dbpool.runInteraction, but retry the
        transaction in case of a temporary error (like connection lost).

        This is needed to be robust against things like database connection
        idle timeouts.

        The passed callable that implements the transaction must be retryable,
        ie. it must not have any destructive side effects in the case where
        an exception is thrown and/or rollback occurs that would prevent it
        from functioning correctly when called again."""

        def runWithRetry(txn, *args, **kw):
            retryCount = 0
            while(True):
                try:
                    return actionFn(txn, *args, **kw)
                except txn.OperationalError:
                    retryCount += 1
                    if retryCount >= 5:
                        raise
                    excType, excValue, excTraceback = sys.exc_info()
                    log.msg("Database transaction failed (caught exception %s(%s)), retrying ..." % (excType, excValue))
                    txn.close()
                    txn.reconnect()
                    txn.reopen()

        return self.dbpool.runInteraction(runWithRetry, *args, **kw)

    def runQueryWithRetry(self, *args, **kw):
        """
        Run a database query, like with dbpool.runQuery, but retry the query in
        case of a temporary error (like connection lost).

        This is needed to be robust against things like database connection
        idle timeouts."""

        def runQuery(txn, *args, **kw):
            txn.execute(*args, **kw)
            return txn.fetchall()

        return self.runInteractionWithRetry(runQuery, *args, **kw)

    def registerInDB(self):
        if self.dbpool:
            return self.runInteractionWithRetry(self.doRegisterInDB)
        else:
            return defer.succeed(0)

    # The real database work is done in a thread in a synchronous way.
    def doRegisterInDB(self, txn):
        # Auto create tables.
        # This is off by default, as it gives warnings in log file
        # about tables already existing (and I did not find the issue
        # important enough to find a better fix).
        if self.autoCreateTables:
            txn.execute("""
CREATE TABLE IF NOT EXISTS test_run(
    id INT PRIMARY KEY AUTO_INCREMENT,
    branch VARCHAR(100),
    revision VARCHAR(32) NOT NULL,
    platform VARCHAR(100) NOT NULL,
    dt TIMESTAMP NOT NULL,
    bbnum INT NOT NULL,
    typ VARCHAR(32) NOT NULL,
    info VARCHAR(255),
    KEY (branch, revision),
    KEY (dt),
    KEY (platform, bbnum)
) ENGINE=innodb
""")
            txn.execute("""
CREATE TABLE IF NOT EXISTS test_failure(
    test_run_id INT NOT NULL,
    test_name VARCHAR(100) NOT NULL,
    test_variant VARCHAR(16) NOT NULL,
    info_text VARCHAR(255),
    failure_text TEXT,
    PRIMARY KEY (test_run_id, test_name, test_variant)
) ENGINE=innodb
""")
            txn.execute("""
CREATE TABLE IF NOT EXISTS test_warnings(
    test_run_id INT NOT NULL,
    list_id INT NOT NULL,
    list_idx INT NOT NULL,
    test_name VARCHAR(100) NOT NULL,
    PRIMARY KEY (test_run_id, list_id, list_idx)
) ENGINE=innodb
""")

        revision = None
        try:
            revision = self.getProperty("got_revision")
        except exceptions.KeyError:
            revision = self.getProperty("revision")
        txn.execute("""
INSERT INTO test_run(branch, revision, platform, dt, bbnum, typ, info)
VALUES (%s, %s, %s, CURRENT_TIMESTAMP(), %s, %s, %s)
""", (self.getProperty("branch"), revision,
      self.getProperty("buildername"), self.getProperty("buildnumber"),
      self.test_type, self.test_info))

        return txn.lastrowid

    def afterRegisterInDB(self, insert_id):
        self.setProperty("mtr_id", insert_id)
        self.setProperty("mtr_warn_id", 0)

        Test.start(self)

    def reportError(self, err):
        log.msg("Error in async insert into database: %s" % err)

    class MyMtrLogObserver(MtrLogObserver):
        def collectTestFail(self, testname, variant, result, info, text):
            # Insert asynchronously into database.
            dbpool = self.step.dbpool
            run_id = self.step.getProperty("mtr_id")
            if dbpool == None:
                return defer.succeed(None)
            if variant == None:
                variant = ""
            d = self.step.runQueryWithRetry("""
INSERT INTO test_failure(test_run_id, test_name, test_variant, info_text, failure_text)
VALUES (%s, %s, %s, %s, %s)
""", (run_id, testname, variant, info, text))

            d.addErrback(self.step.reportError)
            return d

        def collectWarningTests(self, testList):
            # Insert asynchronously into database.
            dbpool = self.step.dbpool
            if dbpool == None:
                return defer.succeed(None)
            run_id = self.step.getProperty("mtr_id")
            warn_id = self.step.getProperty("mtr_warn_id")
            self.step.setProperty("mtr_warn_id", warn_id + 1)
            q = ("INSERT INTO test_warnings(test_run_id, list_id, list_idx, test_name) " +
                 "VALUES " + ", ".join(map(lambda x: "(%s, %s, %s, %s)", testList)))
            v = []
            idx = 0
            for t in testList:
                v.extend([run_id, warn_id, idx, t])
                idx = idx + 1
            d = self.step.runQueryWithRetry(q, tuple(v))
            d.addErrback(self.step.reportError)
            return d
