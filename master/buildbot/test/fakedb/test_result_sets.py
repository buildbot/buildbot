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

from buildbot.db.test_result_sets import TestResultSetAlreadyCompleted
from buildbot.test.fakedb.base import FakeDBComponent
from buildbot.test.fakedb.row import Row


class TestResultSet(Row):
    table = 'test_result_sets'

    defaults = {
        'id': None,
        'builderid': None,
        'buildid': None,
        'stepid': None,
        'description': None,
        'category': None,
        'value_unit': None,
        'tests_passed': None,
        'tests_failed': None,
        'complete': None,
    }

    id_column = 'id'
    foreignKeys = ('builderid', 'buildid', 'stepid')
    required_columns = ('builderid', 'buildid', 'stepid', 'category', 'value_unit', 'complete')


class FakeTestResultSetsComponent(FakeDBComponent):

    def setUp(self):
        self.result_sets = {}

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, TestResultSet):
                self.result_sets[row.id] = row.values.copy()

    def addTestResultSet(self, builderid, buildid, stepid, description, category, value_unit):
        id = Row.nextId()
        self.result_sets[id] = {
            'id': id,
            'builderid': builderid,
            'buildid': buildid,
            'stepid': stepid,
            'description': description,
            'category': category,
            'value_unit': value_unit,
            'tests_failed': None,
            'tests_passed': None,
            'complete': False
        }
        return defer.succeed(id)

    def _row2dict(self, row):
        row = row.copy()
        row['complete'] = bool(row['complete'])
        return row

    # returns a Deferred
    def getTestResultSet(self, test_result_setid):
        if test_result_setid not in self.result_sets:
            return defer.succeed(None)
        return defer.succeed(self._row2dict(self.result_sets[test_result_setid]))

    # returns a Deferred
    def getTestResultSets(self, builderid, buildid=None, stepid=None, complete=None,
                          result_spec=None):
        ret = []
        for id, row in self.result_sets.items():
            if row['builderid'] != builderid:
                continue
            if buildid is not None and row['buildid'] != buildid:
                continue
            if stepid is not None and row['stepid'] != stepid:
                continue
            if complete is not None and row['complete'] != complete:
                continue
            ret.append(self._row2dict(row))

        if result_spec is not None:
            ret = self.applyResultSpec(ret, result_spec)

        return defer.succeed(ret)

    # returns a Deferred
    def completeTestResultSet(self, test_result_setid, tests_passed=None, tests_failed=None):
        if test_result_setid not in self.result_sets:
            raise TestResultSetAlreadyCompleted(('Test result set {} is already completed '
                                                 'or does not exist').format(test_result_setid))
        row = self.result_sets[test_result_setid]
        if row['complete'] != 0:
            raise TestResultSetAlreadyCompleted(('Test result set {} is already completed '
                                                 'or does not exist').format(test_result_setid))
        row['complete'] = 1
        if tests_passed is not None:
            row['tests_passed'] = tests_passed
        if tests_failed is not None:
            row['tests_failed'] = tests_failed
        return defer.succeed(None)
