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


import io
from unittest import TestResult

from twisted.internet import defer

from buildbot.process import buildstep
from buildbot.process import logobserver
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import Results


class SubunitLogObserver(logobserver.LogLineObserver, TestResult):

    """Observe a log that may contain subunit output.

    This class extends TestResult to receive the callbacks from the subunit
    parser in the most direct fashion.
    """

    def __init__(self):
        super().__init__()
        try:
            from subunit import TestProtocolServer, PROGRESS_CUR, PROGRESS_SET
            from subunit import PROGRESS_PUSH, PROGRESS_POP
        except ImportError as e:
            raise ImportError("subunit is not importable, but is required for "
                              "SubunitLogObserver support.") from e
        self.PROGRESS_CUR = PROGRESS_CUR
        self.PROGRESS_SET = PROGRESS_SET
        self.PROGRESS_PUSH = PROGRESS_PUSH
        self.PROGRESS_POP = PROGRESS_POP
        self.warningio = io.BytesIO()
        self.protocol = TestProtocolServer(self, self.warningio)
        self.skips = []
        self.seen_tags = set()  # don't yet know what tags does in subunit

    def outLineReceived(self, line):
        # Impedance mismatch: subunit wants lines, observers get lines-no\n
        # Note that observers get already decoded lines whereas protocol wants bytes
        self.protocol.lineReceived(line.encode('utf-8') + b'\n')

    def errLineReceived(self, line):
        # Same note as in outLineReceived applies
        self.protocol.lineReceived(line.encode('utf-8') + b'\n')

    def stopTest(self, test):
        super().stopTest(test)
        self.step.setProgress('tests', self.testsRun)

    def addSkip(self, test, detail):
        if hasattr(TestResult, 'addSkip'):
            super().addSkip(test, detail)
        else:
            self.skips.append((test, detail))

    def addError(self, test, err):
        super().addError(test, err)
        self.issue(test, err)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.issue(test, err)

    def issue(self, test, err):
        """An issue - failing, erroring etc test."""
        self.step.setProgress('tests failed', len(self.failures) +
                              len(self.errors))

    def tags(self, new_tags, gone_tags):
        """Accumulate the seen tags."""
        self.seen_tags.update(new_tags)


class SubunitShellCommand(buildstep.ShellMixin, buildstep.BuildStep):
    name = 'shell'

    """A ShellCommand that sniffs subunit output.
    """

    def __init__(self, failureOnNoTests=False, *args, **kwargs):
        kwargs = self.setupShellMixin(kwargs)
        super().__init__(*args, **kwargs)

        self.failureOnNoTests = failureOnNoTests

        self._observer = SubunitLogObserver()
        self.addLogObserver('stdio', self._observer)
        self.progressMetrics = self.progressMetrics + ('tests', 'tests failed')

    @defer.inlineCallbacks
    def run(self):
        cmd = yield self.makeRemoteShellCommand()
        yield self.runCommand(cmd)

        stdio_log = yield self.getLog('stdio')
        yield stdio_log.finish()

        problems = ""
        for test, err in self._observer.errors + self._observer.failures:
            problems += f"{test.id()}\n{err}"
        if problems:
            yield self.addCompleteLog("problems", problems)

        warnings = self._observer.warningio.getvalue()
        if warnings:
            yield self.addCompleteLog("warnings", warnings)

        failures = len(self._observer.failures)
        errors = len(self._observer.errors)
        total = self._observer.testsRun

        if cmd.didFail():
            return FAILURE

        if failures + errors > 0:
            return FAILURE

        if not total and self.failureOnNoTests:
            return FAILURE
        return SUCCESS

    def getResultSummary(self):
        failures = len(self._observer.failures)
        errors = len(self._observer.errors)
        skips = len(self._observer.skips)
        total = self._observer.testsRun

        count = failures + errors

        summary = self.name

        if not count:
            if total:
                summary += f' {total} {total == 1 and "test" or "tests"} passed'
            else:
                summary += " no tests run"
        else:
            summary += f" Total {total} test(s)"
            if failures:
                summary += f' {failures} {failures == 1 and "failure" or "failures"}'
            if errors:
                summary += f' {errors} {errors == 1 and "error" or "errors"}'

        if skips:
            summary += f' {skips} {skips == 1 and "skip" or "skips"}'

        # TODO: expectedFailures/unexpectedSuccesses

        if self.results != SUCCESS:
            summary += f' ({Results[self.results]})'

        return {'step': summary}
