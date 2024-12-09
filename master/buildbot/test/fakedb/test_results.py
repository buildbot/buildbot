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

from buildbot.test.fakedb.row import Row


class TestName(Row):
    table = 'test_names'

    id_column = 'id'

    def __init__(self, id=None, builderid=None, name='nam'):
        super().__init__(id=id, builderid=builderid, name=name)


class TestCodePath(Row):
    table = 'test_code_paths'

    id_column = 'id'

    def __init__(self, id=None, builderid=None, path='path/to/file'):
        super().__init__(id=id, builderid=builderid, path=path)


class TestResult(Row):
    table = 'test_results'

    id_column = 'id'

    def __init__(
        self,
        id=None,
        builderid=None,
        test_result_setid=None,
        test_nameid=None,
        test_code_pathid=None,
        line=None,
        duration_ns=None,
        value=None,
    ):
        super().__init__(
            id=id,
            builderid=builderid,
            test_result_setid=test_result_setid,
            test_nameid=test_nameid,
            test_code_pathid=test_code_pathid,
            line=line,
            duration_ns=duration_ns,
            value=value,
        )
