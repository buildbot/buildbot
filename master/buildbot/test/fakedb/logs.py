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


from buildbot.test.fakedb.row import Row


class Log(Row):
    table = "logs"

    id_column = 'id'

    def __init__(
        self, id=None, name='log29', slug=None, stepid=None, complete=0, num_lines=0, type='s'
    ):
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

    def __init__(self, logid=None, first_line=0, last_line=0, content='', compressed=0):
        super().__init__(
            logid=logid,
            first_line=first_line,
            last_line=last_line,
            content=content,
            compressed=compressed,
        )
