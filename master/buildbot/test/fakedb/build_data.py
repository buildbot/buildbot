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

from __future__ import annotations

from twisted.internet import defer

from buildbot.db.build_data import BuildDataModel
from buildbot.test.fakedb.base import FakeDBComponent
from buildbot.test.fakedb.row import Row


class BuildData(Row):
    table = 'build_data'

    id_column = 'id'
    foreignKeys = ('buildid',)
    required_columns = ('buildid', 'name', 'value', 'length', 'source')
    binary_columns = ('value',)

    def __init__(self, id=None, buildid=None, name=None, value=None, source=None):
        super().__init__(
            id=id, buildid=buildid, name=name, value=value, source=source, length=len(value)
        )


class FakeBuildDataComponent(FakeDBComponent):
    def setUp(self):
        self.build_data = {}

    def insert_test_data(self, rows):
        for row in rows:
            if isinstance(row, BuildData):
                self.build_data[row.id] = row.values.copy()

    def _get_build_data_row(self, buildid, name):
        for row in self.build_data.values():
            if row['buildid'] == buildid and row['name'] == name:
                return row
        return None

    def setBuildData(self, buildid, name, value, source):
        assert isinstance(value, bytes)
        row = self._get_build_data_row(buildid, name)
        if row is not None:
            row['value'] = value
            row['length'] = len(value)
            row['source'] = source
            return

        id = Row.nextId()
        self.build_data[id] = {
            'id': id,
            'buildid': buildid,
            'name': name,
            'value': value,
            'length': len(value),
            'source': source,
        }

    # returns a Deferred
    def getBuildData(self, buildid, name) -> defer.Deferred[BuildDataModel | None]:
        row = self._get_build_data_row(buildid, name)
        if row is not None:
            return defer.succeed(self._model_from_row(row, value=row.get('value')))
        return defer.succeed(None)

    # returns a Deferred
    def getBuildDataNoValue(self, buildid, name) -> defer.Deferred[BuildDataModel | None]:
        row = self._get_build_data_row(buildid, name)
        if row is not None:
            return defer.succeed(self._model_from_row(row, value=None))
        return defer.succeed(None)

    # returns a Deferred
    def getAllBuildDataNoValues(self, buildid) -> defer.Deferred[list[BuildDataModel]]:
        ret = []
        for row in self.build_data.values():
            if row['buildid'] != buildid:
                continue
            ret.append(self._model_from_row(row, value=None))

        return defer.succeed(ret)

    # returns a Deferred
    def deleteOldBuildData(self, older_than_timestamp):
        buildids_to_keep = []
        for build_dict in self.db.builds.builds.values():
            if (
                build_dict['complete_at'] is None
                or build_dict['complete_at'] >= older_than_timestamp
            ):
                buildids_to_keep.append(build_dict['id'])

        count_before = len(self.build_data)

        build_dataids_to_remove = []
        for build_datadict in self.build_data.values():
            if build_datadict['buildid'] not in buildids_to_keep:
                build_dataids_to_remove.append(build_datadict['id'])

        for id in build_dataids_to_remove:
            self.build_data.pop(id)

        count_after = len(self.build_data)

        return defer.succeed(count_before - count_after)

    def _model_from_row(self, row, value: bytes | None):
        return BuildDataModel(
            buildid=row['buildid'],
            name=row['name'],
            length=row['length'],
            source=row['source'],
            value=value,
        )
