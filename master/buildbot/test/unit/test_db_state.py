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


from twisted.internet import defer

from buildbot.db import state
from buildbot.test.fake import fakedb
from buildbot.test.util import connector_component
from buildbot.test.util import db


class TestStateConnectorComponent(
    connector_component.ConnectorComponentMixin,
        db.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        yield self.setUpConnectorComponent(
            table_names=['objects', 'object_state'])

        self.db.state = state.StateConnectorComponent(self.db)

    def tearDown(self):
        return self.tearDownConnectorComponent()

    @defer.inlineCallbacks
    def test_getObjectId_new(self):
        objectid = yield self.db.state.getObjectId('someobj', 'someclass')

        yield self.assertNotEqual(objectid, None)

        def thd(conn):
            q = self.db.model.objects.select()
            rows = conn.execute(q).fetchall()
            self.assertEqual(
                [(r.id, r.name, r.class_name) for r in rows],
                [(objectid, 'someobj', 'someclass')])
        yield self.db.pool.do(thd)

    @defer.inlineCallbacks
    def test_getObjectId_existing(self):
        yield self.insertTestData([
            fakedb.Object(id=19, name='someobj',
                          class_name='someclass')])
        objectid = yield self.db.state.getObjectId('someobj', 'someclass')

        self.assertEqual(objectid, 19)

    @defer.inlineCallbacks
    def test_getObjectId_conflict(self):
        # set up to insert a row between looking for an existing object
        # and adding a new one, triggering the fallback to re-running
        # the select.
        def hook(conn):
            conn.execute(self.db.model.objects.insert(),
                         id=27, name='someobj', class_name='someclass')
        self.db.state._test_timing_hook = hook

        objectid = yield self.db.state.getObjectId('someobj', 'someclass')

        self.assertEqual(objectid, 27)

    @defer.inlineCallbacks
    def test_getObjectId_new_big_name(self):
        objectid = yield self.db.state.getObjectId('someobj' * 150, 'someclass')
        expn = 'someobj' * 9 + 's132bf9b89b0cdbc040d1ebc69e0dbee85dff720a'

        self.assertNotEqual(objectid, None)

        def thd(conn):
            q = self.db.model.objects.select()
            rows = conn.execute(q).fetchall()
            self.assertEqual(
                [(r.id, r.name, r.class_name) for r in rows],
                [(objectid, expn, 'someclass')])
        yield self.db.pool.do(thd)

    def test_getState_missing(self):
        d = self.db.state.getState(10, 'nosuch')
        return self.assertFailure(d, KeyError)

    @defer.inlineCallbacks
    def test_getState_missing_default(self):
        val = yield self.db.state.getState(10, 'nosuch', 'abc')

        self.assertEqual(val, 'abc')

    @defer.inlineCallbacks
    def test_getState_missing_default_None(self):
        val = yield self.db.state.getState(10, 'nosuch', None)

        self.assertEqual(val, None)

    @defer.inlineCallbacks
    def test_getState_present(self):
        yield self.insertTestData([
            fakedb.Object(id=10, name='x', class_name='y'),
            fakedb.ObjectState(objectid=10, name='x', value_json='[1,2]'),
        ])
        val = yield self.db.state.getState(10, 'x')

        self.assertEqual(val, [1, 2])

    def test_getState_badjson(self):
        d = self.insertTestData([
            fakedb.Object(id=10, name='x', class_name='y'),
            fakedb.ObjectState(objectid=10, name='x', value_json='ff[1'),
        ])
        d.addCallback(lambda _:
                      self.db.state.getState(10, 'x'))
        return self.assertFailure(d, TypeError)

    @defer.inlineCallbacks
    def test_setState(self):
        yield self.insertTestData([
            fakedb.Object(id=10, name='-', class_name='-'),
        ])
        yield self.db.state.setState(10, 'x', [1, 2])

        def thd(conn):
            q = self.db.model.object_state.select()
            rows = conn.execute(q).fetchall()
            self.assertEqual(
                [(r.objectid, r.name, r.value_json) for r in rows],
                [(10, 'x', '[1, 2]')])
        yield self.db.pool.do(thd)

    def test_setState_badjson(self):
        d = self.insertTestData([
            fakedb.Object(id=10, name='x', class_name='y'),
        ])
        d.addCallback(lambda _:
                      self.db.state.setState(10, 'x', self))  # self is not JSON-able..
        return self.assertFailure(d, TypeError)

    @defer.inlineCallbacks
    def test_setState_existing(self):
        yield self.insertTestData([
            fakedb.Object(id=10, name='-', class_name='-'),
            fakedb.ObjectState(objectid=10, name='x', value_json='99'),
        ])
        yield self.db.state.setState(10, 'x', [1, 2])

        def thd(conn):
            q = self.db.model.object_state.select()
            rows = conn.execute(q).fetchall()
            self.assertEqual(
                [(r.objectid, r.name, r.value_json) for r in rows],
                [(10, 'x', '[1, 2]')])
        yield self.db.pool.do(thd)

    @defer.inlineCallbacks
    def test_setState_conflict(self):
        def hook(conn):
            conn.execute(self.db.model.object_state.insert(),
                         objectid=10, name='x', value_json='22')
        self.db.state._test_timing_hook = hook

        yield self.insertTestData([
            fakedb.Object(id=10, name='-', class_name='-'),
        ])
        yield self.db.state.setState(10, 'x', [1, 2])

        def thd(conn):
            q = self.db.model.object_state.select()
            rows = conn.execute(q).fetchall()
            self.assertEqual(
                [(r.objectid, r.name, r.value_json) for r in rows],
                [(10, 'x', '22')])
        yield self.db.pool.do(thd)

    @defer.inlineCallbacks
    def test_atomicCreateState(self):
        yield self.insertTestData([
            fakedb.Object(id=10, name='-', class_name='-'),
        ])
        res = yield self.db.state.atomicCreateState(10, 'x', lambda: [1, 2])
        self.assertEqual(res, [1, 2])
        res = yield self.db.state.getState(10, 'x')
        self.assertEqual(res, [1, 2])

    @defer.inlineCallbacks
    def test_atomicCreateState_conflict(self):
        yield self.insertTestData([
            fakedb.Object(id=10, name='-', class_name='-'),
        ])

        def hook(conn):
            conn.execute(self.db.model.object_state.insert(),
                         objectid=10, name='x', value_json='22')
        self.db.state._test_timing_hook = hook

        res = yield self.db.state.atomicCreateState(10, 'x', lambda: [1, 2])
        self.assertEqual(res, 22)
        res = yield self.db.state.getState(10, 'x')
        self.assertEqual(res, 22)

    @defer.inlineCallbacks
    def test_atomicCreateState_nojsonable(self):
        yield self.insertTestData([
            fakedb.Object(id=10, name='-', class_name='-'),
        ])

        d = self.db.state.atomicCreateState(10, 'x', object)
        yield self.assertFailure(d, TypeError)
