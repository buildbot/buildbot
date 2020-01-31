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

import re

from buildbot.process import logobserver
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.steps.shell import Test


class CTestTestCounter(logobserver.LogLineObserver):
    _summary_line_re = re.compile(r'[0-9]+% tests passed, ([0-9]+) tests failed out of ([0-9]+)')
    _progress_line_re = re.compile(r'^([0-9]+)/([0-9]+) Test')

    def __init__(self):
        super().__init__()
        self._num_tests = 0
        self._finished = False
        self._counts = {
            'total': 0,
            'failures': 0,
        }

    def failed_count(self):
        return self._counts['failures']

    def total_count(self):
        return self._counts['total']

    def outLineReceived(self, line):
        if not self._finished:
            m = self._progress_line_re.search(line.strip())
            if m:
                cur_test, total_tests = m.groups()
                self._num_tests += 1
                self.step.setProgress('tests', self._num_tests)
                if cur_test == total_tests:
                    self._finished = True

        if self._finished:
            out = self._summary_line_re.search(line.strip())
            if out:
                failed, total = out.groups()
                self._counts['total'] = int(total)
                self._counts['failures'] = int(failed)


class CTest(Test):
    """
    Run CTest default command is:
     ctest --output-on-failure
    """
    name = 'ctest'
    description = ['unit', 'testing']
    descriptionDone = ['unit', 'test']
    command = ['ctest', '--output-on-failure']
    haltOnFailure = True
    flunkOnFailure = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._observer = CTestTestCounter()
        self.addLogObserver('stdio', self._observer)
        self.progressMetrics += ('tests',)

    def evaluateCommand(self, cmd):

        tests_failed_count = self._observer.failed_count()
        total_tests = self._observer.total_count()

        self.setTestResults(failed=tests_failed_count, total=total_tests, passed=total_tests - tests_failed_count)

        if not tests_failed_count and total_tests > 0:
            rc = SUCCESS
        else:
            rc = FAILURE

        return rc
