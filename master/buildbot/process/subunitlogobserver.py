# -*- test-case-name: buildbot.test.test_buildstep -*-

from unittest import TestResult
from buildbot.process import buildstep

class DiscardStream:
    """A trivial thunk used to discard passthrough content."""

    def write(self, bytes):
        pass


class SubunitLogObserver(buildstep.LogLineObserver, TestResult):
    """Observe a log that may contain subunit output.

    This class extends TestResult to receive the callbacks from the subunit
    parser in the most direct fashion.
    """

    def __init__(self):
        buildstep.LogLineObserver.__init__(self)
        TestResult.__init__(self)
        try:
            from subunit import TestProtocolServer
        except ImportError:
            raise ImportError("subunit is not importable, but is required for "
                "SubunitLogObserver support.")
        self.protocol = TestProtocolServer(self, DiscardStream())

    def outLineReceived(self, line):
        """Process a received line."""
        # Impedance mismatch: subunit wants lines, observers get lines-no\n
        self.protocol.lineReceived(line + '\n')

    def startTest(self, test):
        TestResult.startTest(self, test)
        self.step.setProgress('tests', self.testsRun)

    def addError(self, test, err):
        TestResult.addError(self, test, err)
        self.issue()

    def addFailure(self, test, err):
        TestResult.addFailure(self, test, err)
        self.issue()

    def issue(self):
        """An issue - failing, erroring etc test."""
        self.step.setProgress('tests failed', len(self.failures) + len(self.errors))

# this used to be referenced here, so we keep a link for old time's sake
import buildbot.steps.subunit
SubunitShellCommand = buildbot.steps.subunit.SubunitShellCommand
