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

from typing import Any

from buildbot.test.fakedb.row import Row


class Build(Row):
    table = "builds"

    id_column = 'id'

    def __init__(
        self,
        id: int | None = None,
        number: int | None = None,
        buildrequestid: int | None = None,
        builderid: int | None = None,
        workerid: int = -1,
        masterid: int | None = None,
        started_at: int = 1304262222,
        complete_at: int | None = None,
        state_string: str = "test",
        results: int | None = None,
    ) -> None:
        if number is None:
            number = id
        super().__init__(
            id=id,
            number=number,
            buildrequestid=buildrequestid,
            builderid=builderid,
            workerid=workerid,
            masterid=masterid,
            started_at=started_at,
            complete_at=complete_at,
            locks_duration_s=0,
            state_string=state_string,
            results=results,
        )


class BuildProperty(Row):
    table = "build_properties"

    def __init__(
        self,
        buildid: int | None = None,
        name: str = 'prop',
        value: Any = 42,
        source: str = 'fakedb',
    ) -> None:
        super().__init__(buildid=buildid, name=name, value=value, source=source)
