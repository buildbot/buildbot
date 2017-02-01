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

from __future__ import absolute_import
from __future__ import print_function

from twisted.internet import defer

from buildbot.db import state
from buildbot.test.fake import fakedb
from buildbot.test.util import connector_component
from buildbot.test.util import db


class TestStateConnectorComponent(
    connector_component.ConnectorComponentMixin,
        db.TestCase):

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['objects', 'object_state'])

        def finish_setup(_):
            self.db.state = \
                state.StateConnectorComponent(self.db)
        d.addCallback(finish_setup)

        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()

    def test_getObjectId_new(self):
        d = self.db.state.getObjectId('someobj', 'someclass')

        def check(objectid):
            self.assertNotEqual(objectid, None)

            def thd(conn):
                q = self.db.model.objects.select()
                rows = conn.execute(q).fetchall()
                self.assertEqual(
                    [(r.id, r.name, r.class_name) for r in rows],
                    [(objectid, 'someobj', 'someclass')])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_getObjectId_existing(self):
        d = self.insertTestData([
            fakedb.Object(id=19, name='someobj',
                          class_name='someclass')])
        d.addCallback(lambda _:
                      self.db.state.getObjectId('someobj', 'someclass'))

        def check(objectid):
            self.assertEqual(objectid, 19)
        d.addCallback(check)
        return d

    def test_getObjectId_conflict(self):
        # set up to insert a row between looking for an existing object
        # and adding a new one, triggering the fallback to re-running
        # the select.
        def hook(conn):
            conn.execute(self.db.model.objects.insert(),
                         id=27, name='someobj', class_name='someclass')
        self.db.state._test_timing_hook = hook

        d = self.db.state.getObjectId('someobj', 'someclass')

        def check(objectid):
            self.assertEqual(objectid, 27)
        d.addCallback(check)
        return d

    def test_getState_missing(self):
        d = self.db.state.getState(10, 'nosuch')
        return self.assertFailure(d, KeyError)

    def test_getState_missing_default(self):
        d = self.db.state.getState(10, 'nosuch', 'abc')

        def check(val):
            self.assertEqual(val, 'abc')
        d.addCallback(check)
        return d

    def test_getState_missing_default_None(self):
        d = self.db.state.getState(10, 'nosuch', None)

        def check(val):
            self.assertEqual(val, None)
        d.addCallback(check)
        return d

    def test_getState_present(self):
        d = self.insertTestData([
            fakedb.Object(id=10, name='x', class_name='y'),
            fakedb.ObjectState(objectid=10, name='x', value_json='[1,2]'),
        ])
        d.addCallback(lambda _:
                      self.db.state.getState(10, 'x'))

        def check(val):
            self.assertEqual(val, [1, 2])
        d.addCallback(check)
        return d

    def test_getState_badjson(self):
        d = self.insertTestData([
            fakedb.Object(id=10, name='x', class_name='y'),
            fakedb.ObjectState(objectid=10, name='x', value_json='ff[1'),
        ])
        d.addCallback(lambda _:
                      self.db.state.getState(10, 'x'))
        return self.assertFailure(d, TypeError)

    def test_setState(self):
        d = self.insertTestData([
            fakedb.Object(id=10, name='-', class_name='-'),
        ])
        d.addCallback(lambda _:
                      self.db.state.setState(10, 'x', [1, 2]))

        def check(_):
            def thd(conn):
                q = self.db.model.object_state.select()
                rows = conn.execute(q).fetchall()
                self.assertEqual(
                    [(r.objectid, r.name, r.value_json) for r in rows],
                    [(10, 'x', '[1, 2]')])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_setState_badjson(self):
        d = self.insertTestData([
            fakedb.Object(id=10, name='x', class_name='y'),
        ])
        d.addCallback(lambda _:
                      self.db.state.setState(10, 'x', self))  # self is not JSON-able..
        return self.assertFailure(d, TypeError)

    def test_setState_existing(self):
        d = self.insertTestData([
            fakedb.Object(id=10, name='-', class_name='-'),
            fakedb.ObjectState(objectid=10, name='x', value_json='99'),
        ])
        d.addCallback(lambda _:
                      self.db.state.setState(10, 'x', [1, 2]))

        def check(_):
            def thd(conn):
                q = self.db.model.object_state.select()
                rows = conn.execute(q).fetchall()
                self.assertEqual(
                    [(r.objectid, r.name, r.value_json) for r in rows],
                    [(10, 'x', '[1, 2]')])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_setState_conflict(self):
        d = self.insertTestData([
            fakedb.Object(id=10, name='-', class_name='-'),
        ])

        def hook(conn):
            conn.execute(self.db.model.object_state.insert(),
                         objectid=10, name='x', value_json='22')
        self.db.state._test_timing_hook = hook
        d.addCallback(lambda _:
                      self.db.state.setState(10, 'x', [1, 2]))

        def check(_):
            def thd(conn):
                q = self.db.model.object_state.select()
                rows = conn.execute(q).fetchall()
                self.assertEqual(
                    [(r.objectid, r.name, r.value_json) for r in rows],
                    [(10, 'x', '22')])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

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

        d = self.db.state.atomicCreateState(10, 'x', lambda: object())
        yield self.assertFailure(d, TypeError)
