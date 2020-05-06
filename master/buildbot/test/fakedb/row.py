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

import hashlib

from twisted.internet import defer

from buildbot.util import unicode2bytes


class Row:

    """
    Parent class for row classes, which are used to specify test data for
    database-related tests.

    @cvar defaults: the column names and their default values
    @type defaults: dictionary

    @cvar table: the table name

    @cvar id_column: specify a column that should be assigned an
    auto-incremented id.  Auto-assigned id's begin at 1000, so any explicitly
    specified ID's should be less than 1000.

    @cvar required_columns: a tuple of columns that must be given in the
    constructor

    @cvar hashedColumns: a tuple of hash column and source columns designating
    a hash to work around MySQL's inability to do indexing.

    @ivar values: the values to be inserted into this row
    """

    id_column = ()
    required_columns = ()
    lists = ()
    dicts = ()
    hashedColumns = []
    foreignKeys = []
    # Columns that content is represented as sa.Binary-like type in DB model.
    # They value is bytestring (in contrast to text-like columns, which are
    # unicode).
    binary_columns = ()

    _next_id = None

    def __init__(self, **kwargs):
        self.values = self.defaults.copy()
        self.values.update(kwargs)
        if self.id_column:
            if self.values[self.id_column] is None:
                self.values[self.id_column] = self.nextId()
        for col in self.required_columns:
            assert col in kwargs, "{} not specified: {}".format(col, kwargs)
        for col in self.lists:
            setattr(self, col, [])
        for col in self.dicts:
            setattr(self, col, {})
        for col in kwargs:
            assert col in self.defaults, "{} is not a valid column".format(col)
        # cast to unicode
        for k, v in self.values.items():
            if isinstance(v, str):
                self.values[k] = str(v)
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
            self.values[hash_col] = self.hashColumns(
                *(self.values[c] for c in src_cols))

        # make the values appear as attributes
        self.__dict__.update(self.values)

    def __eq__(self, other):
        if self.__class__ != other.__class__:
            return False
        return self.values == other.values

    def __ne__(self, other):
        if self.__class__ != other.__class__:
            return True
        return self.values != other.values

    def __lt__(self, other):
        if self.__class__ != other.__class__:
            raise TypeError("Cannot compare {} and {}".format(
                self.__class__, other.__class__))
        return self.values < other.values

    def __le__(self, other):
        if self.__class__ != other.__class__:
            raise TypeError("Cannot compare {} and {}".format(
                self.__class__, other.__class__))
        return self.values <= other.values

    def __gt__(self, other):
        if self.__class__ != other.__class__:
            raise TypeError("Cannot compare {} and {}".format(
                self.__class__, other.__class__))
        return self.values > other.values

    def __ge__(self, other):
        if self.__class__ != other.__class__:
            raise TypeError("Cannot compare {} and {}".format(
                self.__class__, other.__class__))
        return self.values >= other.values

    def __repr__(self):
        return '{}(**{})'.format(self.__class__.__name__, repr(self.values))

    @staticmethod
    def nextId():
        id = Row._next_id if Row._next_id is not None else 1
        Row._next_id = id + 1
        return id

    def hashColumns(self, *args):
        # copied from master/buildbot/db/base.py
        def encode(x):
            if x is None:
                return b'\xf5'
            elif isinstance(x, str):
                return x.encode('utf-8')
            return str(x).encode('utf-8')

        return hashlib.sha1(b'\0'.join(map(encode, args))).hexdigest()

    @defer.inlineCallbacks
    def checkForeignKeys(self, db, t):
        accessors = dict(
            buildsetid=db.buildsets.getBuildset,
            workerid=db.workers.getWorker,
            builderid=db.builders.getBuilder,
            buildid=db.builds.getBuild,
            changesourceid=db.changesources.getChangeSource,
            changeid=db.changes.getChange,
            buildrequestid=db.buildrequests.getBuildRequest,
            sourcestampid=db.sourcestamps.getSourceStamp,
            schedulerid=db.schedulers.getScheduler,
            brid=db.buildrequests.getBuildRequest,
            stepid=db.steps.getStep,
            masterid=db.masters.getMaster)
        for foreign_key in self.foreignKeys:
            if foreign_key in accessors:
                key = getattr(self, foreign_key)
                if key is not None:
                    val = yield accessors[foreign_key](key)
                    t.assertTrue(val is not None,
                                 "foreign key {}:{} does not exit".format(foreign_key, repr(key)))
            else:
                raise ValueError(
                    "warning, unsupported foreign key", foreign_key, self.table)
