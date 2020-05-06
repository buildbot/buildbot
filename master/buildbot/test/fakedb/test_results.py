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

from buildbot.test.fakedb.base import FakeDBComponent
from buildbot.test.fakedb.row import Row


class TestName(Row):
    table = 'test_names'

    defaults = {
        'id': None,
        'builderid': None,
        'name': 'nam'
    }

    id_column = 'id'
    foreignKeys = ('builderid',)
    required_columns = ('builderid', 'name')


class TestCodePath(Row):
    table = 'test_code_paths'

    defaults = {
        'id': None,
        'builderid': None,
        'path': 'path/to/file'
    }

    id_column = 'id'
    foreignKeys = ('builderid',)
    required_columns = ('builderid', 'path')


class TestResult(Row):
    table = 'test_results'

    defaults = {
        'id': None,
        'builderid': None,
        'test_result_setid': None,
        'test_nameid': None,
        'test_code_pathid': None,
        'line': None,
        'duration_ns': None,
        'value': None
    }

    id_column = 'id'
    foreignKeys = ('builderid', 'test_result_setid', 'test_nameid', 'test_code_pathid')
    required_columns = ('builderid', 'test_result_setid', 'value')


class FakeTestResultsComponent(FakeDBComponent):

    def setUp(self):
        self.results = {}
        self.code_paths = {}
        self.names = {}

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, TestName):
                self.names[row.id] = row.values.copy()

        for row in rows:
            if isinstance(row, TestCodePath):
                self.code_paths[row.id] = row.values.copy()

        for row in rows:
            if isinstance(row, TestResult):
                if row.test_nameid is not None:
                    assert row.test_nameid in self.names
                if row.test_code_pathid is not None:
                    assert row.test_code_pathid in self.code_paths

                self.results[row.id] = row.values.copy()

    def _add_code_paths(self, builderid, paths):
        path_to_id = {}

        for path in sorted(paths):
            id = self._get_code_path_id(builderid, path)
            if id is not None:
                path_to_id[path] = id
                continue

            id = Row.nextId()
            self.code_paths[id] = {
                'builderid': builderid,
                'path': path
            }
            path_to_id[path] = id

        return path_to_id

    def _get_code_path_id(self, builderid, path):
        for id, path_dict in self.code_paths.items():
            if path_dict['builderid'] == builderid and path_dict['path'] == path:
                return id
        return None

    def _add_names(self, builderid, names):
        name_to_id = {}

        for name in sorted(names):
            id = self._get_name_id(builderid, name)
            if id is not None:
                name_to_id[name] = id
                continue

            id = Row.nextId()
            self.names[id] = {
                'builderid': builderid,
                'name': name
            }
            name_to_id[name] = id

        return name_to_id

    def _get_name_id(self, builderid, name):
        for id, name_dict in self.names.items():
            if name_dict['builderid'] == builderid and name_dict['name'] == name:
                return id
        return None

    @defer.inlineCallbacks
    def addTestResults(self, builderid, test_result_setid, result_values):
        insert_code_paths = set()
        insert_names = set()
        for result_value in result_values:
            if 'value' not in result_value:
                raise KeyError('Each of result_values must contain \'value\' key')

            if 'test_name' not in result_value and 'test_code_path' not in result_value:
                raise KeyError('Each of result_values must contain at least one of '
                               '\'test_name\' or \'test_code_path\' keys')

            if 'test_name' in result_value:
                insert_names.add(result_value['test_name'])
            if 'test_code_path' in result_value:
                insert_code_paths.add(result_value['test_code_path'])

        code_path_to_id = yield self._add_code_paths(builderid, insert_code_paths)
        name_to_id = yield self._add_names(builderid, insert_names)

        for result_value in result_values:
            insert_value = {
                'value': result_value['value'],
                'builderid': builderid,
                'test_result_setid': test_result_setid,
                'test_nameid': None,
                'test_code_pathid': None,
                'duration_ns': None,
                'line': None,
            }

            if 'test_name' in result_value:
                insert_value['test_nameid'] = name_to_id[result_value['test_name']]
            if 'test_code_path' in result_value:
                insert_value['test_code_pathid'] = code_path_to_id[result_value['test_code_path']]
            if 'line' in result_value:
                insert_value['line'] = result_value['line']
            if 'duration_ns' in result_value:
                insert_value['duration_ns'] = result_value['duration_ns']

            self.results[Row.nextId()] = insert_value

    # returns a Deferred
    def getTestNames(self, builderid, name_prefix=None, result_spec=None):
        ret = []
        for id, row in sorted(self.names.items()):
            if row['builderid'] != builderid:
                continue
            if name_prefix is not None and not row['name'].startswith(name_prefix):
                continue
            ret.append(row['name'])

        if result_spec is not None:
            ret = self.applyResultSpec(ret, result_spec)

        return defer.succeed(ret)

    # returns a Deferred
    def getTestCodePaths(self, builderid, path_prefix=None, result_spec=None):
        ret = []
        for id, row in sorted(self.code_paths.items()):
            if row['builderid'] != builderid:
                continue
            if path_prefix is not None and not row['path'].startswith(path_prefix):
                continue
            ret.append(row['path'])

        if result_spec is not None:
            ret = self.applyResultSpec(ret, result_spec)

        return defer.succeed(ret)

    def _fill_extra_data(self, id, row):
        row = row.copy()
        row['id'] = id

        if row['test_nameid'] is not None:
            row['test_name'] = self.names[row['test_nameid']]['name']
        else:
            row['test_name'] = None
        del row['test_nameid']

        if row['test_code_pathid'] is not None:
            row['test_code_path'] = self.code_paths[row['test_code_pathid']]['path']
        else:
            row['test_code_path'] = None
        del row['test_code_pathid']

        return row

    # returns a Deferred
    def getTestResult(self, test_resultid):
        if test_resultid not in self.results:
            return defer.succeed(None)
        return defer.succeed(self._fill_extra_data(test_resultid, self.results[test_resultid]))

    # returns a Deferred
    def getTestResults(self, builderid, test_result_setid, result_spec=None):
        ret = []
        for id, row in sorted(self.results.items()):
            if row['builderid'] != builderid:
                continue
            if row['test_result_setid'] != test_result_setid:
                continue
            ret.append(self._fill_extra_data(id, row))

        if result_spec is not None:
            ret = self.applyResultSpec(ret, result_spec)

        return defer.succeed(ret)
