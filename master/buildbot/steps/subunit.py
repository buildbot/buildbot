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
from __future__ import print_function

from unittest import TestResult

from twisted.python.compat import NativeStringIO

from buildbot.process import logobserver
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.steps.shell import ShellCommand


class SubunitLogObserver(logobserver.LogLineObserver, TestResult):

    """Observe a log that may contain subunit output.

    This class extends TestResult to receive the callbacks from the subunit
    parser in the most direct fashion.
    """

    def __init__(self):
        logobserver.LogLineObserver.__init__(self)
        TestResult.__init__(self)
        try:
            from subunit import TestProtocolServer, PROGRESS_CUR, PROGRESS_SET
            from subunit import PROGRESS_PUSH, PROGRESS_POP
        except ImportError:
            raise ImportError("subunit is not importable, but is required for "
                              "SubunitLogObserver support.")
        self.PROGRESS_CUR = PROGRESS_CUR
        self.PROGRESS_SET = PROGRESS_SET
        self.PROGRESS_PUSH = PROGRESS_PUSH
        self.PROGRESS_POP = PROGRESS_POP
        self.warningio = NativeStringIO()
        self.protocol = TestProtocolServer(self, self.warningio)
        self.skips = []
        self.seen_tags = set()  # don't yet know what tags does in subunit

    def outLineReceived(self, line):
        """Process a received stdout line."""
        # Impedance mismatch: subunit wants lines, observers get lines-no\n
        self.protocol.lineReceived(line + '\n')

    def errLineReceived(self, line):
        """same for stderr line."""
        self.protocol.lineReceived(line + '\n')

    def stopTest(self, test):
        TestResult.stopTest(self, test)
        self.step.setProgress('tests', self.testsRun)

    def addSuccess(self, test):
        TestResult.addSuccess(self, test)

    def addSkip(self, test, detail):
        if hasattr(TestResult, 'addSkip'):
            TestResult.addSkip(self, test, detail)
        else:
            self.skips.append((test, detail))

    def addError(self, test, err):
        TestResult.addError(self, test, err)
        self.issue(test, err)

    def addFailure(self, test, err):
        TestResult.addFailure(self, test, err)
        self.issue(test, err)

    def issue(self, test, err):
        """An issue - failing, erroring etc test."""
        self.step.setProgress('tests failed', len(self.failures) +
                              len(self.errors))

    def tags(self, new_tags, gone_tags):
        """Accumulate the seen tags."""
        self.seen_tags.update(new_tags)


class SubunitShellCommand(ShellCommand):

    """A ShellCommand that sniffs subunit output.
    """

    def __init__(self, failureOnNoTests=False, *args, **kwargs):
        ShellCommand.__init__(self, *args, **kwargs)
        self.failureOnNoTests = failureOnNoTests

        self.ioObserver = SubunitLogObserver()
        self.addLogObserver('stdio', self.ioObserver)
        self.progressMetrics = self.progressMetrics + ('tests', 'tests failed')

    def commandComplete(self, cmd):
        # figure out all statistics about the run
        ob = self.ioObserver
        failures = len(ob.failures)
        errors = len(ob.errors)
        skips = len(ob.skips)
        total = ob.testsRun

        count = failures + errors

        text = [self.name]
        text2 = ""

        if not count:
            results = SUCCESS
            if total:
                text += ["%d %s" %
                         (total,
                          total == 1 and "test" or "tests"),
                         "passed"]
            else:
                if self.failureOnNoTests:
                    results = FAILURE
                text += ["no tests", "run"]
        else:
            results = FAILURE
            text.append("Total %d test(s)" % total)
            if failures:
                text.append("%d %s" %
                            (failures,
                             failures == 1 and "failure" or "failures"))
            if errors:
                text.append("%d %s" %
                            (errors,
                             errors == 1 and "error" or "errors"))
            text2 = "%d %s" % (count, (count == 1 and 'test' or 'tests'))

        if skips:
            text.append("%d %s" % (skips,
                                   skips == 1 and "skip" or "skips"))

        # TODO: expectedFailures/unexpectedSuccesses

        self.results = results
        self.text = text
        self.text2 = [text2]

    def evaluateCommand(self, cmd):
        if cmd.didFail():
            return FAILURE
        return self.results

    def createSummary(self, loog):
        ob = self.ioObserver
        problems = ""
        for test, err in ob.errors + ob.failures:
            problems += "%s\n%s" % (test.id(), err)
        if problems:
            self.addCompleteLog("problems", problems)
        warnings = ob.warningio.getvalue()
        if warnings:
            self.addCompleteLog("warnings", warnings)

    def _describe(self, done):
        return self.text
