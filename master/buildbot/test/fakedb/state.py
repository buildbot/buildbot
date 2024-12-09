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


class Object(Row):
    table = "objects"

    id_column = 'id'

    def __init__(self, id=None, name='nam', class_name='cls'):
        super().__init__(id=id, name=name, class_name=class_name)


class ObjectState(Row):
    table = "object_state"

    def __init__(self, objectid=None, name='nam', value_json='{}'):
        super().__init__(objectid=objectid, name=name, value_json=value_json)
