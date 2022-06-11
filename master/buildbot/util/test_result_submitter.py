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

from twisted.internet import defer
from twisted.python import log

from buildbot.util import deferwaiter


class TestResultSubmitter:

    def __init__(self, batch_n=3000):
        self._batch_n = batch_n
        self._curr_batch = []
        self._pending_batches = []
        self._waiter = deferwaiter.DeferWaiter()
        self._master = None
        self._builderid = None

        self._add_pass_fail_result = None  # will be set to a callable if enabled
        self._tests_passed = None
        self._tests_failed = None

    @defer.inlineCallbacks
    def setup(self, step, description, category, value_unit):
        builderid = yield step.build.getBuilderId()
        yield self.setup_by_ids(step.master, builderid, step.build.buildid, step.stepid,
                                description, category, value_unit)

    @defer.inlineCallbacks
    def setup_by_ids(self, master, builderid, buildid, stepid, description, category, value_unit):
        self._master = master
        self._category = category
        self._value_unit = value_unit

        self._initialize_pass_fail_recording_if_needed()

        self._builderid = builderid
        self._setid = yield self._master.data.updates.addTestResultSet(builderid, buildid, stepid,
                                                                       description, category,
                                                                       value_unit)

    @defer.inlineCallbacks
    def finish(self):
        self._submit_batch()
        yield self._waiter.wait()
        yield self._master.data.updates.completeTestResultSet(self._setid,
                                                              tests_passed=self._tests_passed,
                                                              tests_failed=self._tests_failed)

    def get_test_result_set_id(self):
        return self._setid

    def _submit_batch(self):
        batch = self._curr_batch
        self._curr_batch = []

        if not batch:
            return

        self._pending_batches.append(batch)
        if self._waiter.has_waited():
            return

        self._waiter.add(self._process_batches())

    @defer.inlineCallbacks
    def _process_batches(self):
        # at most one instance of this function may be running at the same time
        while self._pending_batches:
            batch = self._pending_batches.pop(0)
            yield self._master.data.updates.addTestResults(self._builderid, self._setid, batch)

    def _initialize_pass_fail_recording(self, function):
        self._add_pass_fail_result = function
        self._compute_pass_fail = True
        self._tests_passed = 0
        self._tests_failed = 0

    def _initialize_pass_fail_recording_if_needed(self):
        if self._category == 'pass_fail' and self._value_unit == 'boolean':
            self._initialize_pass_fail_recording(self._add_pass_fail_result_category_pass_fail)
            return
        if self._category == 'pass_only':
            self._initialize_pass_fail_recording(self._add_pass_fail_result_category_pass_only)
            return
        if self._category in ('fail_only', 'code_issue'):
            self._initialize_pass_fail_recording(self._add_pass_fail_result_category_fail_only)
            return

    def _add_pass_fail_result_category_fail_only(self, value):
        self._tests_failed += 1

    def _add_pass_fail_result_category_pass_only(self, value):
        self._tests_passed += 1

    def _add_pass_fail_result_category_pass_fail(self, value):
        try:
            is_success = bool(int(value))
            if is_success:
                self._tests_passed += 1
            else:
                self._tests_failed += 1

        except Exception as e:
            log.err(e, 'When parsing test result success status')

    def add_test_result(self, value, test_name=None, test_code_path=None, line=None,
                        duration_ns=None):
        if not isinstance(value, str):
            raise TypeError('value must be a string')
        result = {'value': value}

        if test_name is not None:
            if not isinstance(test_name, str):
                raise TypeError('test_name must be a string')
            result['test_name'] = test_name

        if test_code_path is not None:
            if not isinstance(test_code_path, str):
                raise TypeError('test_code_path must be a string')
            result['test_code_path'] = test_code_path

        if line is not None:
            if not isinstance(line, int):
                raise TypeError('line must be an integer')
            result['line'] = line

        if duration_ns is not None:
            if not isinstance(duration_ns, int):
                raise TypeError('duration_ns must be an integer')
            result['duration_ns'] = duration_ns

        if self._add_pass_fail_result is not None:
            self._add_pass_fail_result(value)

        self._curr_batch.append(result)
        if len(self._curr_batch) >= self._batch_n:
            self._submit_batch()
