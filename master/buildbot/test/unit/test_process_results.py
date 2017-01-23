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
from future.utils import lrange

from twisted.python import log
from twisted.trial import unittest

from buildbot.process import results


class TestResults(unittest.TestCase):

    def test_Results(self):
        for r in results.Results:
            i = getattr(results, r.upper())
            self.assertEqual(results.Results[i], r)

    def test_worst_status(self):
        self.assertEqual(results.WARNINGS,
                         results.worst_status(results.SUCCESS, results.WARNINGS))
        self.assertEqual(results.CANCELLED,
                         results.worst_status(results.SKIPPED, results.CANCELLED))

    def test_sort_worst_status(self):
        res = lrange(len(results.Results))
        res.sort(
            key=lambda a: a if a != results.SKIPPED else -1)
        self.assertEqual(res, [
            results.SKIPPED,
            results.SUCCESS,
            results.WARNINGS,
            results.FAILURE,
            results.EXCEPTION,
            results.RETRY,
            results.CANCELLED,
        ])

    def do_test_carc(self, result, previousResult, newResult, terminate,
                     haltOnFailure=[True, False], flunkOnWarnings=[
                         True, False],
                     flunkOnFailure=[True, False], warnOnWarnings=[
                         True, False],
                     warnOnFailure=[True, False]):
        for hof in haltOnFailure:
            for fow in flunkOnWarnings:
                for fof in flunkOnFailure:
                    for wow in warnOnWarnings:
                        for wof in warnOnFailure:
                            self.haltOnFailure = hof
                            self.flunkOnWarnings = fow
                            self.flunkOnFailure = fof
                            self.warnOnWarnings = wow
                            self.warnOnFailure = wof
                            nr, term = results.computeResultAndTermination(
                                self, result, previousResult)
                            log.msg("res=%r prevRes=%r hof=%r fow=%r fof=%r "
                                    "wow=%r wof=%r => %r %r" %
                                    (results.Results[result],
                                     results.Results[previousResult],
                                     hof, fow, fof, wow, wof,
                                     results.Results[nr], term))
                            self.assertEqual((nr, term),
                                             (newResult, terminate),
                                             "see test.log for details")

    def test_carc_success_after_success(self):
        self.do_test_carc(results.SUCCESS, results.SUCCESS,
                          results.SUCCESS, False)

    def test_carc_success_after_warnings(self):
        self.do_test_carc(results.SUCCESS, results.WARNINGS,
                          results.WARNINGS, False)

    def test_carc_success_after_failure(self):
        self.do_test_carc(results.SUCCESS, results.FAILURE,
                          results.FAILURE, False)

    def test_carc_warnings_after_success(self):
        self.do_test_carc(results.WARNINGS, results.SUCCESS,
                          results.WARNINGS, False,
                          flunkOnWarnings=[False], warnOnWarnings=[True])
        self.do_test_carc(results.WARNINGS, results.SUCCESS,
                          results.SUCCESS, False,
                          flunkOnWarnings=[False], warnOnWarnings=[False])
        self.do_test_carc(results.WARNINGS, results.SUCCESS,
                          results.FAILURE, False,
                          flunkOnWarnings=[True], warnOnWarnings=[True])
        self.do_test_carc(results.WARNINGS, results.SUCCESS,
                          results.FAILURE, False,
                          flunkOnWarnings=[True], warnOnWarnings=[False])

    def test_carc_warnings_after_warnings(self):
        self.do_test_carc(results.WARNINGS, results.WARNINGS,
                          results.WARNINGS, False,
                          flunkOnWarnings=[False])
        self.do_test_carc(results.WARNINGS, results.WARNINGS,
                          results.FAILURE, False,
                          flunkOnWarnings=[True])

    def test_carc_warnings_after_failure(self):
        self.do_test_carc(results.WARNINGS, results.FAILURE,
                          results.FAILURE, False,
                          flunkOnWarnings=[False])
        self.do_test_carc(results.WARNINGS, results.FAILURE,
                          results.FAILURE, False,
                          flunkOnWarnings=[True])

    def test_carc_failure_after_success(self):
        for hof in False, True:
            self.do_test_carc(results.FAILURE, results.SUCCESS,
                              results.FAILURE, hof,
                              haltOnFailure=[hof],
                              flunkOnFailure=[True], warnOnFailure=[False])
            self.do_test_carc(results.FAILURE, results.SUCCESS,
                              results.FAILURE, hof,
                              haltOnFailure=[hof],
                              flunkOnFailure=[True], warnOnFailure=[True])
            self.do_test_carc(results.FAILURE, results.SUCCESS,
                              results.SUCCESS, hof,
                              haltOnFailure=[hof],
                              flunkOnFailure=[False], warnOnFailure=[False])
            self.do_test_carc(results.FAILURE, results.SUCCESS,
                              results.WARNINGS, hof,
                              haltOnFailure=[hof],
                              flunkOnFailure=[False], warnOnFailure=[True])

    def test_carc_failure_after_warnings(self):
        for hof in False, True:
            self.do_test_carc(results.FAILURE, results.WARNINGS,
                              results.FAILURE, hof,
                              haltOnFailure=[hof],
                              flunkOnFailure=[True])
            self.do_test_carc(results.FAILURE, results.WARNINGS,
                              results.WARNINGS, hof,
                              haltOnFailure=[hof],
                              flunkOnFailure=[False])

    def test_carc_failure_after_failure(self):
        for hof in False, True:
            self.do_test_carc(results.FAILURE, results.FAILURE,
                              results.FAILURE, hof,
                              haltOnFailure=[hof])

    def test_carc_exception(self):
        for prev in results.FAILURE, results.WARNINGS, results.SUCCESS:
            self.do_test_carc(results.EXCEPTION, prev,
                              results.EXCEPTION, True)

    def test_carc_retry(self):
        for prev in results.FAILURE, results.WARNINGS, results.SUCCESS:
            self.do_test_carc(results.RETRY, prev,
                              results.RETRY, True)

    def test_carc_cancelled(self):
        for prev in results.FAILURE, results.WARNINGS, results.SUCCESS:
            self.do_test_carc(results.CANCELLED, prev,
                              results.CANCELLED, True)

    def test_carc_skipped(self):
        for prev in results.FAILURE, results.WARNINGS, results.SUCCESS:
            self.do_test_carc(results.SKIPPED, prev,
                              prev, False)
