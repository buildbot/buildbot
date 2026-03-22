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


class Log(Row):
    table = "logs"

    id_column = 'id'

    def __init__(
        self,
        id: int | None = None,
        name: str = 'log29',
        slug: str | None = None,
        stepid: int | None = None,
        complete: int = 0,
        num_lines: int = 0,
        type: str = 's',
    ) -> None:
        if slug is None:
            slug = name
        super().__init__(
            id=id,
            name=name,
            slug=slug,
            stepid=stepid,
            complete=complete,
            num_lines=num_lines,
            type=type,
        )


class LogChunk(Row):
    table = "logchunks"

    # 'content' column is sa.LargeBinary, it's bytestring.
    binary_columns = ('content',)

    def __init__(
        self,
        logid: int | None = None,
        first_line: int = 0,
        last_line: int = 0,
        content: str | bytes = '',
        compressed: int = 0,
    ) -> None:
        super().__init__(
            logid=logid,
            first_line=first_line,
            last_line=last_line,
            content=content,
            compressed=compressed,
        )
