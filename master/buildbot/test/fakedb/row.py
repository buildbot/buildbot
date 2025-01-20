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

from typing import Sequence

from buildbot.util import unicode2bytes
from buildbot.util.sautils import hash_columns


class Row:
    """
    Parent class for row classes, which are used to specify test data for
    database-related tests.

    @cvar table: the table name

    @cvar id_column: specify a column that should be assigned an
    auto-incremented id.  Auto-assigned id's begin at 1000, so any explicitly
    specified ID's should be less than 1000.

    @cvar hashedColumns: a tuple of hash column and source columns designating
    a hash to work around MySQL's inability to do indexing.

    @ivar values: the values to be inserted into this row
    """

    id_column: tuple[()] | str = ()

    hashedColumns: Sequence[tuple[str, Sequence[str]]] = ()
    # Columns that content is represented as sa.Binary-like type in DB model.
    # They value is bytestring (in contrast to text-like columns, which are
    # unicode).
    binary_columns: Sequence[str] = ()

    _next_id = None

    def __init__(self, **kwargs):
        if self.__init__.__func__ is Row.__init__:
            raise RuntimeError(
                'Row.__init__ must be overridden to supply default values for columns'
            )

        self.values = kwargs.copy()
        if self.id_column:
            if self.values[self.id_column] is None:
                self.values[self.id_column] = self.nextId()
        # Binary columns stores either (compressed) binary data or encoded
        # with utf-8 unicode string. We assume that Row constructor receives
        # only unicode strings and encode them to utf-8 here.
        # At this moment there is only one such column: logchunks.contents,
        # which stores either utf-8 encoded string, or gzip-compressed
        # utf-8 encoded string.
        for col in self.binary_columns:
            self.values[col] = unicode2bytes(self.values[col])
        # calculate any necessary hashes
        for hash_col, src_cols in self.hashedColumns:
            self.values[hash_col] = hash_columns(*(self.values[c] for c in src_cols))

        # make the values appear as attributes
        self.__dict__.update(self.values)

    def __repr__(self):
        values_str = ''.join(f'{k}={v!r}, ' for k, v in self.values.items())
        return f'{self.__class__.__name__}({values_str})'

    @staticmethod
    def nextId():
        id = Row._next_id if Row._next_id is not None else 1
        Row._next_id = id + 1
        return id
