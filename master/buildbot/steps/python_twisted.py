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


from twisted.python import log

from buildbot.process.buildstep import LogLineObserver
from buildbot.process.buildstep import OutputProgressObserver
from buildbot.status import testresult
from buildbot.status.results import FAILURE
from buildbot.status.results import SKIPPED
from buildbot.status.results import SUCCESS
from buildbot.status.results import WARNINGS
from buildbot.steps.shell import ShellCommand

try:
    import cStringIO
    StringIO = cStringIO
except ImportError:
    import StringIO
import re

# BuildSteps that are specific to the Twisted source tree


class HLint(ShellCommand):

    """I run a 'lint' checker over a set of .xhtml files. Any deviations
    from recommended style is flagged and put in the output log.

    This step looks at .changes in the parent Build to extract a list of
    Lore XHTML files to check."""

    name = "hlint"
    description = ["running", "hlint"]
    descriptionDone = ["hlint"]
    warnOnWarnings = True
    warnOnFailure = True
    # TODO: track time, but not output
    warnings = 0

    def __init__(self, python=None, **kwargs):
        ShellCommand.__init__(self, **kwargs)
        self.python = python

    def start(self):
        # create the command
        htmlFiles = {}
        for f in self.build.allFiles():
            if f.endswith(".xhtml") and not f.startswith("sandbox/"):
                htmlFiles[f] = 1
        # remove duplicates
        hlintTargets = sorted(htmlFiles.keys())
        if not hlintTargets:
            return SKIPPED
        self.hlintFiles = hlintTargets
        c = []
        if self.python:
            c.append(self.python)
        c += ["bin/lore", "-p", "--output", "lint"] + self.hlintFiles
        self.setCommand(c)

        # add an extra log file to show the .html files we're checking
        self.addCompleteLog("files", "\n".join(self.hlintFiles) + "\n")

        ShellCommand.start(self)

    def commandComplete(self, cmd):
        # TODO: remove the 'files' file (a list of .xhtml files that were
        # submitted to hlint) because it is available in the logfile and
        # mostly exists to give the user an idea of how long the step will
        # take anyway).
        lines = cmd.logs['stdio'].getText().split("\n")
        warningLines = filter(lambda line: ':' in line, lines)
        if warningLines:
            self.addCompleteLog("warnings", "".join(warningLines))
        warnings = len(warningLines)
        self.warnings = warnings

    def evaluateCommand(self, cmd):
        # warnings are in stdout, rc is always 0, unless the tools break
        if cmd.didFail():
            return FAILURE
        if self.warnings:
            return WARNINGS
        return SUCCESS

    def getText2(self, cmd, results):
        if cmd.didFail():
            return ["hlint"]
        return ["%d hlin%s" % (self.warnings,
                               self.warnings == 1 and 't' or 'ts')]


def countFailedTests(output):
    # start scanning 10kb from the end, because there might be a few kb of
    # import exception tracebacks between the total/time line and the errors
    # line
    chunk = output[-10000:]
    lines = chunk.split("\n")
    lines.pop()  # blank line at end
    # lines[-3] is "Ran NN tests in 0.242s"
    # lines[-2] is blank
    # lines[-1] is 'OK' or 'FAILED (failures=1, errors=12)'
    #  or 'FAILED (failures=1)'
    #  or "PASSED (skips=N, successes=N)"  (for Twisted-2.0)
    # there might be other lines dumped here. Scan all the lines.
    res = {'total': None,
           'failures': 0,
           'errors': 0,
           'skips': 0,
           'expectedFailures': 0,
           'unexpectedSuccesses': 0,
           }
    for l in lines:
        out = re.search(r'Ran (\d+) tests', l)
        if out:
            res['total'] = int(out.group(1))
        if (l.startswith("OK") or
            l.startswith("FAILED ") or
                l.startswith("PASSED")):
            # the extra space on FAILED_ is to distinguish the overall
            # status from an individual test which failed. The lack of a
            # space on the OK is because it may be printed without any
            # additional text (if there are no skips,etc)
            out = re.search(r'failures=(\d+)', l)
            if out:
                res['failures'] = int(out.group(1))
            out = re.search(r'errors=(\d+)', l)
            if out:
                res['errors'] = int(out.group(1))
            out = re.search(r'skips=(\d+)', l)
            if out:
                res['skips'] = int(out.group(1))
            out = re.search(r'expectedFailures=(\d+)', l)
            if out:
                res['expectedFailures'] = int(out.group(1))
            out = re.search(r'unexpectedSuccesses=(\d+)', l)
            if out:
                res['unexpectedSuccesses'] = int(out.group(1))
            # successes= is a Twisted-2.0 addition, and is not currently used
            out = re.search(r'successes=(\d+)', l)
            if out:
                res['successes'] = int(out.group(1))

    return res


class TrialTestCaseCounter(LogLineObserver):
    _line_re = re.compile(r'^(?:Doctest: )?([\w\.]+) \.\.\. \[([^\]]+)\]$')
    numTests = 0
    finished = False

    def outLineReceived(self, line):
        # different versions of Twisted emit different per-test lines with
        # the bwverbose reporter.
        #  2.0.0: testSlave (buildbot.test.test_runner.Create) ... [OK]
        #  2.1.0: buildbot.test.test_runner.Create.testSlave ... [OK]
        #  2.4.0: buildbot.test.test_runner.Create.testSlave ... [OK]
        # Let's just handle the most recent version, since it's the easiest.
        # Note that doctests create lines line this:
        #  Doctest: viff.field.GF ... [OK]

        if self.finished:
            return
        if line.startswith("=" * 40):
            self.finished = True
            return

        m = self._line_re.search(line.strip())
        if m:
            testname, result = m.groups()
            self.numTests += 1
            self.step.setProgress('tests', self.numTests)


UNSPECIFIED = ()  # since None is a valid choice


class Trial(ShellCommand):

    """
    There are some class attributes which may be usefully overridden
    by subclasses. 'trialMode' and 'trialArgs' can influence the trial
    command line.
    """

    name = "trial"
    progressMetrics = ('output', 'tests', 'test.log')
    # note: the slash only works on unix buildslaves, of course, but we have
    # no way to know what the buildslave uses as a separator.
    # TODO: figure out something clever.
    logfiles = {"test.log": "_trial_temp/test.log"}
    # we use test.log to track Progress at the end of __init__()

    renderables = ['tests', 'jobs']
    flunkOnFailure = True
    python = None
    trial = "trial"
    trialMode = ["--reporter=bwverbose"]  # requires Twisted-2.1.0 or newer
    # for Twisted-2.0.0 or 1.3.0, use ["-o"] instead
    trialArgs = []
    jobs = None
    testpath = UNSPECIFIED  # required (but can be None)
    testChanges = False  # TODO: needs better name
    recurse = False
    reactor = None
    randomly = False
    tests = None  # required

    def __init__(self, reactor=UNSPECIFIED, python=None, trial=None,
                 testpath=UNSPECIFIED,
                 tests=None, testChanges=None,
                 recurse=None, randomly=None,
                 trialMode=None, trialArgs=None, jobs=None,
                 **kwargs):
        """
        @type  testpath: string
        @param testpath: use in PYTHONPATH when running the tests. If
                         None, do not set PYTHONPATH. Setting this to '.' will
                         cause the source files to be used in-place.

        @type  python: string (without spaces) or list
        @param python: which python executable to use. Will form the start of
                       the argv array that will launch trial. If you use this,
                       you should set 'trial' to an explicit path (like
                       /usr/bin/trial or ./bin/trial). Defaults to None, which
                       leaves it out entirely (running 'trial args' instead of
                       'python ./bin/trial args'). Likely values are 'python',
                       ['python2.2'], ['python', '-Wall'], etc.

        @type  trial: string
        @param trial: which 'trial' executable to run.
                      Defaults to 'trial', which will cause $PATH to be
                      searched and probably find /usr/bin/trial . If you set
                      'python', this should be set to an explicit path (because
                      'python2.3 trial' will not work).

        @type trialMode: list of strings
        @param trialMode: a list of arguments to pass to trial, specifically
                          to set the reporting mode. This defaults to ['-to']
                          which means 'verbose colorless output' to the trial
                          that comes with Twisted-2.0.x and at least -2.1.0 .
                          Newer versions of Twisted may come with a trial
                          that prefers ['--reporter=bwverbose'].

        @type trialArgs: list of strings
        @param trialArgs: a list of arguments to pass to trial, available to
                          turn on any extra flags you like. Defaults to [].

        @type jobs: integer
        @param jobs: integer to be used as trial -j/--jobs option (for
                     running tests on several workers).  Only supported
                     since Twisted-12.3.0.

        @type  tests: list of strings
        @param tests: a list of test modules to run, like
                      ['twisted.test.test_defer', 'twisted.test.test_process'].
                      If this is a string, it will be converted into a one-item
                      list.

        @type  testChanges: boolean
        @param testChanges: if True, ignore the 'tests' parameter and instead
                            ask the Build for all the files that make up the
                            Changes going into this build. Pass these filenames
                            to trial and ask it to look for test-case-name
                            tags, running just the tests necessary to cover the
                            changes.

        @type  recurse: boolean
        @param recurse: If True, pass the --recurse option to trial, allowing
                        test cases to be found in deeper subdirectories of the
                        modules listed in 'tests'. This does not appear to be
                        necessary when using testChanges.

        @type  reactor: string
        @param reactor: which reactor to use, like 'gtk' or 'java'. If not
                        provided, the Twisted's usual platform-dependent
                        default is used.

        @type  randomly: boolean
        @param randomly: if True, add the --random=0 argument, which instructs
                         trial to run the unit tests in a random order each
                         time. This occasionally catches problems that might be
                         masked when one module always runs before another
                         (like failing to make registerAdapter calls before
                         lookups are done).

        @type  kwargs: dict
        @param kwargs: parameters. The following parameters are inherited from
                       L{ShellCommand} and may be useful to set: workdir,
                       haltOnFailure, flunkOnWarnings, flunkOnFailure,
                       warnOnWarnings, warnOnFailure, want_stdout, want_stderr,
                       timeout.
        """
        ShellCommand.__init__(self, **kwargs)

        if python:
            self.python = python
        if self.python is not None:
            if isinstance(self.python, str):
                self.python = [self.python]
            for s in self.python:
                if " " in s:
                    # this is not strictly an error, but I suspect more
                    # people will accidentally try to use python="python2.3
                    # -Wall" than will use embedded spaces in a python flag
                    log.msg("python= component '%s' has spaces")
                    log.msg("To add -Wall, use python=['python', '-Wall']")
                    why = "python= value has spaces, probably an error"
                    raise ValueError(why)

        if trial:
            self.trial = trial
        if " " in self.trial:
            raise ValueError("trial= value has spaces")
        if trialMode is not None:
            self.trialMode = trialMode
        if trialArgs is not None:
            self.trialArgs = trialArgs
        if jobs is not None:
            self.jobs = jobs

        if testpath is not UNSPECIFIED:
            self.testpath = testpath
        if self.testpath is UNSPECIFIED:
            raise ValueError("You must specify testpath= (it can be None)")
        assert isinstance(self.testpath, str) or self.testpath is None

        if reactor is not UNSPECIFIED:
            self.reactor = reactor

        if tests is not None:
            self.tests = tests
        if isinstance(self.tests, str):
            self.tests = [self.tests]
        if testChanges is not None:
            self.testChanges = testChanges
            # self.recurse = True  # not sure this is necessary

        if not self.testChanges and self.tests is None:
            raise ValueError("Must either set testChanges= or provide tests=")

        if recurse is not None:
            self.recurse = recurse
        if randomly is not None:
            self.randomly = randomly

        # build up most of the command, then stash it until start()
        command = []
        if self.python:
            command.extend(self.python)
        command.append(self.trial)
        command.extend(self.trialMode)
        if self.recurse:
            command.append("--recurse")
        if self.reactor:
            command.append("--reactor=%s" % reactor)
        if self.randomly:
            command.append("--random=0")
        command.extend(self.trialArgs)
        self.command = command

        if self.reactor:
            self.description = ["testing", "(%s)" % self.reactor]
            self.descriptionDone = ["tests"]
            # commandComplete adds (reactorname) to self.text
        else:
            self.description = ["testing"]
            self.descriptionDone = ["tests"]

        # this counter will feed Progress along the 'test cases' metric
        self.addLogObserver('stdio', TrialTestCaseCounter())

    def setupEnvironment(self, cmd):
        ShellCommand.setupEnvironment(self, cmd)
        if self.testpath is not None:
            e = cmd.args['env']
            if e is None:
                cmd.args['env'] = {'PYTHONPATH': self.testpath}
            else:
                # this bit produces a list, which can be used
                # by buildslave.runprocess.RunProcess
                ppath = e.get('PYTHONPATH', self.testpath)
                if isinstance(ppath, str):
                    ppath = [ppath]
                if self.testpath not in ppath:
                    ppath.insert(0, self.testpath)
                e['PYTHONPATH'] = ppath

    def start(self):
        # choose progressMetrics and logfiles based on whether trial is being
        # run with multiple workers or not.
        output_observer = OutputProgressObserver('test.log')

        if self.jobs is not None:
            self.jobs = int(self.jobs)
            self.command.append("--jobs=%d" % self.jobs)

            # using -j/--jobs flag produces more than one test log.
            self.logfiles = {}
            for i in xrange(self.jobs):
                self.logfiles['test.%d.log' % i] = '_trial_temp/%d/test.log' % i
                self.logfiles['err.%d.log' % i] = '_trial_temp/%d/err.log' % i
                self.logfiles['out.%d.log' % i] = '_trial_temp/%d/out.log' % i
                self.addLogObserver('test.%d.log' % i, output_observer)
        else:
            # this one just measures bytes of output in _trial_temp/test.log
            self.addLogObserver('test.log', output_observer)

        # now that self.build.allFiles() is nailed down, finish building the
        # command
        if self.testChanges:
            for f in self.build.allFiles():
                if f.endswith(".py"):
                    self.command.append("--testmodule=%s" % f)
        else:
            self.command.extend(self.tests)
        log.msg("Trial.start: command is", self.command)

        ShellCommand.start(self)

    def commandComplete(self, cmd):
        # figure out all status, then let the various hook functions return
        # different pieces of it

        # 'cmd' is the original trial command, so cmd.logs['stdio'] is the
        # trial output. We don't have access to test.log from here.
        output = cmd.logs['stdio'].getText()
        counts = countFailedTests(output)

        total = counts['total']
        failures, errors = counts['failures'], counts['errors']
        parsed = (total is not None)
        text = []
        text2 = ""

        if not cmd.didFail():
            if parsed:
                results = SUCCESS
                if total:
                    text += ["%d %s" %
                             (total,
                              total == 1 and "test" or "tests"),
                             "passed"]
                else:
                    text += ["no tests", "run"]
            else:
                results = FAILURE
                text += ["testlog", "unparseable"]
                text2 = "tests"
        else:
            # something failed
            results = FAILURE
            if parsed:
                text.append("tests")
                if failures:
                    text.append("%d %s" %
                                (failures,
                                 failures == 1 and "failure" or "failures"))
                if errors:
                    text.append("%d %s" %
                                (errors,
                                 errors == 1 and "error" or "errors"))
                count = failures + errors
                text2 = "%d tes%s" % (count, (count == 1 and 't' or 'ts'))
            else:
                text += ["tests", "failed"]
                text2 = "tests"

        if counts['skips']:
            text.append("%d %s" %
                        (counts['skips'],
                         counts['skips'] == 1 and "skip" or "skips"))
        if counts['expectedFailures']:
            text.append("%d %s" %
                        (counts['expectedFailures'],
                         counts['expectedFailures'] == 1 and "todo"
                         or "todos"))
            if 0:  # TODO
                results = WARNINGS
                if not text2:
                    text2 = "todo"

        if 0:
            # ignore unexpectedSuccesses for now, but it should really mark
            # the build WARNING
            if counts['unexpectedSuccesses']:
                text.append("%d surprises" % counts['unexpectedSuccesses'])
                results = WARNINGS
                if not text2:
                    text2 = "tests"

        if self.reactor:
            text.append(self.rtext('(%s)'))
            if text2:
                text2 = "%s %s" % (text2, self.rtext('(%s)'))

        self.results = results
        self.text = text
        self.text2 = [text2]

    def rtext(self, fmt='%s'):
        if self.reactor:
            rtext = fmt % self.reactor
            return rtext.replace("reactor", "")
        return ""

    def addTestResult(self, testname, results, text, tlog):
        if self.reactor is not None:
            testname = (self.reactor,) + testname
        tr = testresult.TestResult(testname, results, text, logs={'log': tlog})
        # self.step_status.build.addTestResult(tr)
        self.build.build_status.addTestResult(tr)

    def createSummary(self, loog):
        output = loog.getText()
        problems = ""
        sio = StringIO.StringIO(output)
        warnings = {}
        while True:
            line = sio.readline()
            if line == "":
                break
            if line.find(" exceptions.DeprecationWarning: ") != -1:
                # no source
                warning = line  # TODO: consider stripping basedir prefix here
                warnings[warning] = warnings.get(warning, 0) + 1
            elif (line.find(" DeprecationWarning: ") != -1 or
                  line.find(" UserWarning: ") != -1):
                # next line is the source
                warning = line + sio.readline()
                warnings[warning] = warnings.get(warning, 0) + 1
            elif line.find("Warning: ") != -1:
                warning = line
                warnings[warning] = warnings.get(warning, 0) + 1

            if line.find("=" * 60) == 0 or line.find("-" * 60) == 0:
                problems += line
                problems += sio.read()
                break

        if problems:
            self.addCompleteLog("problems", problems)
            # now parse the problems for per-test results
            pio = StringIO.StringIO(problems)
            pio.readline()  # eat the first separator line
            testname = None
            done = False
            while not done:
                while True:
                    line = pio.readline()
                    if line == "":
                        done = True
                        break
                    if line.find("=" * 60) == 0:
                        break
                    if line.find("-" * 60) == 0:
                        # the last case has --- as a separator before the
                        # summary counts are printed
                        done = True
                        break
                    if testname is None:
                        # the first line after the === is like:
                        # EXPECTED FAILURE: testLackOfTB (twisted.test.test_failure.FailureTestCase)
                        # SKIPPED: testRETR (twisted.test.test_ftp.TestFTPServer)
                        # FAILURE: testBatchFile (twisted.conch.test.test_sftp.TestOurServerBatchFile)
                        r = re.search(r'^([^:]+): (\w+) \(([\w\.]+)\)', line)
                        if not r:
                            # TODO: cleanup, if there are no problems,
                            # we hit here
                            continue
                        result, name, case = r.groups()
                        testname = tuple(case.split(".") + [name])
                        results = {'SKIPPED': SKIPPED,
                                   'EXPECTED FAILURE': SUCCESS,
                                   'UNEXPECTED SUCCESS': WARNINGS,
                                   'FAILURE': FAILURE,
                                   'ERROR': FAILURE,
                                   'SUCCESS': SUCCESS,  # not reported
                                   }.get(result, WARNINGS)
                        text = result.lower().split()
                        loog = line
                        # the next line is all dashes
                        loog += pio.readline()
                    else:
                        # the rest goes into the log
                        loog += line
                if testname:
                    self.addTestResult(testname, results, text, loog)
                    testname = None

        if warnings:
            lines = sorted(warnings.keys())
            self.addCompleteLog("warnings", "".join(lines))

    def evaluateCommand(self, cmd):
        return self.results

    def getText(self, cmd, results):
        return self.text

    def getText2(self, cmd, results):
        return self.text2


class RemovePYCs(ShellCommand):
    name = "remove-.pyc"
    command = ['find', '.', '-name', '*.pyc', '-exec', 'rm', '{}', ';']
    description = ["removing", ".pyc", "files"]
    descriptionDone = ["remove", ".pycs"]
