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


from unittest import TestResult
from StringIO import StringIO

from buildbot.process import buildstep
from buildbot.status.testresult import TestResult as aTestResult
from buildbot.status.results import SUCCESS, FAILURE, SKIPPED

class SubunitLogObserver(buildstep.LogLineObserver, TestResult):
    """Observe a log that may contain subunit output.

    This class extends TestResult to receive the callbacks from the subunit
    parser in the most direct fashion.
    """

    def __init__(self):
        buildstep.LogLineObserver.__init__(self)
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
        self.warningio = StringIO()
        self.protocol = TestProtocolServer(self, self.warningio)
        self.skips = []
        self.seen_tags = set() #don't yet know what tags does in subunit

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
        self.addAResult(test, SUCCESS, 'SUCCESS')

    def addSkip(self, test, detail):
        if hasattr(TestResult,'addSkip'):
            TestResult.addSkip(self, test, detail)
        else:
            self.skips.append((test, detail))
        self.addAResult(test, SKIPPED, 'SKIPPED', detail)

    def addError(self, test, err):
        TestResult.addError(self, test, err)
        self.issue(test, err)

    def addFailure(self, test, err):
        TestResult.addFailure(self, test, err)
        self.issue(test, err)

    def addAResult(self, test, result, text, log=""):
        tr = aTestResult(tuple(test.id().split('.')), result, text, log)
        self.step.build.build_status.addTestResult(tr)

    def issue(self, test, err):
        """An issue - failing, erroring etc test."""
        self.addAResult(test, FAILURE, 'FAILURE', err)
        self.step.setProgress('tests failed', len(self.failures) + 
            len(self.errors))

    expectedTests = 0
    contextLevel = 0
    def progress(self, offset, whence):
        if not self.contextLevel:
            if whence == self.PROGRESS_CUR:
                self.expectedTests += offset
            elif whence == self.PROGRESS_SET:
                self.expectedTests = offset
            self.step.progress.setExpectations({'tests': self.expectedTests})
        #TODO: properly support PUSH/POP
        if whence == self.PROGRESS_PUSH:
            self.contextLevel += 1
        elif whence == self.PROGRESS_POP:
            self.contextLevel -= 1

    def tags(self, new_tags, gone_tags):
        """Accumulate the seen tags."""
        self.seen_tags.update(new_tags)

# this used to be referenced here, so we keep a link for old time's sake
import buildbot.steps.subunit
SubunitShellCommand = buildbot.steps.subunit.SubunitShellCommand
