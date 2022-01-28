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

import json

from twisted.internet import defer

from buildbot.test.fakedb.base import FakeDBComponent
from buildbot.test.fakedb.row import Row
from buildbot.util import bytes2unicode


class Object(Row):
    table = "objects"

    id_column = 'id'

    def __init__(self, id=None, name='nam', class_name='cls'):
        super().__init__(id=id, name=name, class_name=class_name)


class ObjectState(Row):
    table = "object_state"

    required_columns = ('objectid', )

    def __init__(self, objectid=None, name='nam', value_json='{}'):
        super().__init__(objectid=objectid, name=name, value_json=value_json)


class FakeStateComponent(FakeDBComponent):

    def setUp(self):
        self.objects = {}
        self.states = {}

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, Object):
                self.objects[(row.name, row.class_name)] = row.id
                self.states[row.id] = {}

        for row in rows:
            if isinstance(row, ObjectState):
                assert row.objectid in list(self.objects.values())
                self.states[row.objectid][row.name] = row.value_json

    # component methods

    def _newId(self):
        id = 100
        while id in self.states:
            id += 1
        return id

    def getObjectId(self, name, class_name):
        try:
            id = self.objects[(name, class_name)]
        except KeyError:
            # invent a new id and add it
            id = self.objects[(name, class_name)] = self._newId()
            self.states[id] = {}
        return defer.succeed(id)

    def getState(self, objectid, name, default=object):
        try:
            json_value = self.states[objectid][name]
        except KeyError:
            if default is not object:
                return defer.succeed(default)
            raise
        return defer.succeed(json.loads(json_value))

    def setState(self, objectid, name, value):
        self.states[objectid][name] = json.dumps(value)
        return defer.succeed(None)

    def atomicCreateState(self, objectid, name, thd_create_callback):
        value = thd_create_callback()
        self.states[objectid][name] = json.dumps(bytes2unicode(value))
        return defer.succeed(value)

    # fake methods

    def set_fake_state(self, object, **kwargs):
        state_key = (object.name, object.__class__.__name__)
        if state_key in self.objects:
            id = self.objects[state_key]
        else:
            id = self.objects[state_key] = self._newId()

        self.states[id] = dict((k, json.dumps(v))
                               for k, v in kwargs.items())
        return id

    # assertions

    def assertState(self, objectid, missing_keys=None, **kwargs):
        if missing_keys is None:
            missing_keys = []
        state = self.states[objectid]
        for k in missing_keys:
            self.t.assertFalse(k in state, f"{k} in {state}")
        for k, v in kwargs.items():
            self.t.assertIn(k, state)
            self.t.assertEqual(json.loads(state[k]), v,
                               f"state is {repr(state)}")

    def assertStateByClass(self, name, class_name, **kwargs):
        objectid = self.objects[(name, class_name)]
        state = self.states[objectid]
        for k, v in kwargs.items():
            self.t.assertIn(k, state)
            self.t.assertEqual(json.loads(state[k]), v,
                               f"state is {repr(state)}")
