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


class Builder(Row):
    table = "builders"

    id_column = 'id'
    hashedColumns = [('name_hash', ('name',))]

    def __init__(
        self,
        id: int | None = None,
        name: str | None = None,
        name_hash: str | None = None,
        projectid: int | None = None,
        description: str | None = None,
        description_format: str | None = None,
        description_html: str | None = None,
    ) -> None:
        if name is None:
            name = f'builder-{id}'
        super().__init__(
            id=id,
            name=name,
            name_hash=name_hash,
            projectid=projectid,
            description=description,
            description_format=description_format,
            description_html=description_html,
        )


class BuilderMaster(Row):
    table = "builder_masters"
    id_column = 'id'

    def __init__(
        self, id: int | None = None, builderid: int | None = None, masterid: int | None = None
    ) -> None:
        super().__init__(id=id, builderid=builderid, masterid=masterid)


class BuildersTags(Row):
    table = "builders_tags"
    id_column = 'id'

    def __init__(
        self, id: int | None = None, builderid: int | None = None, tagid: int | None = None
    ) -> None:
        super().__init__(id=id, builderid=builderid, tagid=tagid)
