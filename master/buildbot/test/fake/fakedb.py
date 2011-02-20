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

"""
A complete re-implementation of the database connector components, but without
using a database.  These classes should pass the same tests as are applied to
the real connector components.
"""

# Fake DB Rows

class Row(object):
    """
    Parent class for row classes, which are used to specify test data for
    database-related tests.

    @cvar defaults: default values for columns
    @type defaults: dictionary

    @cvar table: the table name

    @cvar id_column: specify a column that should be assigned an
    auto-incremented id.  Auto-assigned id's begin at 1000, so any explicitly
    specified ID's should be less than 1000.

    @cvar id_column: a tuple of columns that must be given in the constructor

    @ivar values: the values to be inserted into this row
    """

    id_column = ()
    required_columns = ()

    def __init__(self, **kwargs):
        self.values = self.defaults.copy()
        self.values.update(kwargs)
        if self.id_column:
            if self.values[self.id_column] is None:
                self.values[self.id_column] = self.nextId()
        for col in self.required_columns:
            assert col in kwargs, "%s not specified" % col

    def nextId(self):
        if not hasattr(self.__class__, '_next_id'):
            self.__class__._next_id = 1000
        else:
            self.__class__._next_id += 1
        return self.__class__._next_id

class Change(Row):
    table = "changes"

    defaults = dict(
        changeid = None,
        author = 'frank',
        comments = 'test change',
        is_dir = 0,
        branch = 'master',
        revision = 'abcd',
        revlink = 'http://vc/abcd',
        when_timestamp = 1200000,
        category = 'cat',
        repository = 'repo',
        project = 'proj',
    )

    id_column = 'changeid'

class ChangeFile(Row):
    table = "change_files"

    defaults = dict(
        changeid = None,
        filename = None,
    )

    required_columns = ('changeid',)

class ChangeLink(Row):
    table = "change_links"

    defaults = dict(
        changeid = None,
        link = None,
    )

    required_columns = ('changeid',)

class ChangeProperty(Row):
    table = "change_properties"

    defaults = dict(
        changeid = None,
        property_name = None,
        property_value = None,
    )

    required_columns = ('changeid',)

class SourceStamp(Row):
    table = "sourcestamps"

    defaults = dict(
        id = None,
        branch = 'master',
        revision = 'abcd',
        patchid = None,
        repository = 'repo',
        project = 'proj',
    )

    id_column = 'id'

class Scheduler(Row):
    table = "schedulers"

    defaults = dict(
        schedulerid = None,
        name = 'testsched',
        state = '{}',
        class_name = 'TestScheduler',
    )

    id_column = 'schedulerid'

class Object(Row):
    table = "objects"

    defaults = dict(
        id = None,
        name = 'nam',
        class_name = 'cls',
    )

    id_column = 'id'

class ObjectState(Row):
    table = "object_state"

    defaults = dict(
        objectid = None,
        name = 'nam',
        value_json = '{}',
    )

    required_columns = ( 'objectid', )

# Fake DB Components
