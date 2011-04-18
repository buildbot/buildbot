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

from twisted.trial import unittest

from buildbot.process.buildstep import LoggingBuildStep, regex_log_evaluator
from buildbot.status.results import FAILURE, SUCCESS, WARNINGS, EXCEPTION

class FakeLogFile:
    def __init__(self, text):
        self.text = text

    def getText(self):
        return self.text

class FakeCmd:
    def __init__(self, stdout, stderr, rc=0):
        self.logs = {'stdout': FakeLogFile(stdout),
                     'stderr': FakeLogFile(stderr)}
        self.rc = rc

class FakeStepStatus:
    pass

class TestRegexLogEvaluator(unittest.TestCase):
    def test_find_worse_status(self):
        cmd = FakeCmd("This is log text", "")
        step_status = FakeStepStatus()
        r = [(re.compile("This is"), FAILURE)]
        new_status = regex_log_evaluator(cmd, step_status, r)
        self.assertEqual(new_status, FAILURE, "regex_log_evaluator returned %d, should've returned %d" % (new_status, FAILURE))

    def test_multiple_regexes(self):
        cmd = FakeCmd("Normal stdout text\nan error", "")
        step_status = FakeStepStatus()
        r = [(re.compile("Normal stdout"), SUCCESS),
             (re.compile("error"), FAILURE)]
        new_status = regex_log_evaluator(cmd, step_status, r)
        self.assertEqual(new_status, FAILURE, "regex_log_evaluator returned %d, should've returned %d" % (new_status, FAILURE))

    def test_exception_not_in_stdout(self):
        cmd = FakeCmd("Completely normal output", "exception output")
        step_status = FakeStepStatus()
        r = [(re.compile("exception"), EXCEPTION)]
        new_status = regex_log_evaluator(cmd, step_status, r)
        self.assertEqual(new_status, EXCEPTION, "regex_log_evaluator returned %d, should've returned %d" % (new_status, EXCEPTION))

    def test_pass_a_string(self):
        cmd = FakeCmd("Output", "Some weird stuff on stderr")
        step_status = FakeStepStatus()
        r = [("weird stuff", WARNINGS)]
        new_status = regex_log_evaluator(cmd, step_status, r)
        self.assertEqual(new_status, WARNINGS, "regex_log_evaluator returned %d, should've returned %d" % (new_status, WARNINGS))


class TestLoggingBuildStep(unittest.TestCase):
    def test_evaluateCommand_success(self):
        cmd = FakeCmd("Log text", "Log text")
        lbs = LoggingBuildStep()
        status = lbs.evaluateCommand(cmd)
        self.assertEqual(status, SUCCESS, "evaluateCommand returned %d, should've returned %d" % (status, SUCCESS))

    def test_evaluateCommand_failed(self):
        cmd = FakeCmd("Log text", "", 23)
        lbs = LoggingBuildStep()
        status = lbs.evaluateCommand(cmd)
        self.assertEqual(status, FAILURE, "evaluateCommand returned %d, should've returned %d" % (status, FAILURE))

    def test_evaluateCommand_log_eval_func(self):
        cmd = FakeCmd("Log text", "")
        def eval(cmd, step_status):
            return WARNINGS
        lbs = LoggingBuildStep(log_eval_func=eval)
        status = lbs.evaluateCommand(cmd)
        self.assertEqual(status, WARNINGS, "evaluateCommand didn't call log_eval_func or overrode its results")
