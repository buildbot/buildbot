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


class TestResultSet(Row):
    table = 'test_result_sets'

    id_column = 'id'

    def __init__(
        self,
        id=None,
        builderid=None,
        buildid=None,
        stepid=None,
        description=None,
        category='cat',
        value_unit='unit',
        tests_passed=None,
        tests_failed=None,
        complete=1,
    ):
        super().__init__(
            id=id,
            builderid=builderid,
            buildid=buildid,
            stepid=stepid,
            description=description,
            category=category,
            value_unit=value_unit,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            complete=complete,
        )
