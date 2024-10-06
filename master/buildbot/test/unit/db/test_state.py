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


from buildbot.db import state
from buildbot.test import fakedb
from buildbot.test.util import connector_component
from buildbot.test.util import db


class TestStateConnectorComponent(connector_component.ConnectorComponentMixin, db.TestCase):
    async def setUp(self):
        await self.setUpConnectorComponent(table_names=['objects', 'object_state'])

        self.db.state = state.StateConnectorComponent(self.db)

    def tearDown(self):
        return self.tearDownConnectorComponent()

    async def test_getObjectId_new(self):
        objectid = await self.db.state.getObjectId('someobj', 'someclass')

        await self.assertNotEqual(objectid, None)

        def thd(conn):
            q = self.db.model.objects.select()
            rows = conn.execute(q).fetchall()
            self.assertEqual(
                [(r.id, r.name, r.class_name) for r in rows], [(objectid, 'someobj', 'someclass')]
            )

        await self.db.pool.do(thd)

    async def test_getObjectId_existing(self):
        await self.insert_test_data([fakedb.Object(id=19, name='someobj', class_name='someclass')])
        objectid = await self.db.state.getObjectId('someobj', 'someclass')

        self.assertEqual(objectid, 19)

    async def test_getObjectId_conflict(self):
        # set up to insert a row between looking for an existing object
        # and adding a new one, triggering the fallback to re-running
        # the select.
        def hook(conn):
            conn.execute(
                self.db.model.objects.insert().values(id=27, name='someobj', class_name='someclass')
            )
            conn.commit()

        self.db.state._test_timing_hook = hook

        objectid = await self.db.state.getObjectId('someobj', 'someclass')

        self.assertEqual(objectid, 27)

    async def test_getObjectId_new_big_name(self):
        objectid = await self.db.state.getObjectId('someobj' * 150, 'someclass')
        expn = 'someobj' * 9 + 's132bf9b89b0cdbc040d1ebc69e0dbee85dff720a'

        self.assertNotEqual(objectid, None)

        def thd(conn):
            q = self.db.model.objects.select()
            rows = conn.execute(q).fetchall()
            self.assertEqual(
                [(r.id, r.name, r.class_name) for r in rows], [(objectid, expn, 'someclass')]
            )

        await self.db.pool.do(thd)

    def test_getState_missing(self):
        d = self.db.state.getState(10, 'nosuch')
        return self.assertFailure(d, KeyError)

    async def test_getState_missing_default(self):
        val = await self.db.state.getState(10, 'nosuch', 'abc')

        self.assertEqual(val, 'abc')

    async def test_getState_missing_default_None(self):
        val = await self.db.state.getState(10, 'nosuch', None)

        self.assertEqual(val, None)

    async def test_getState_present(self):
        await self.insert_test_data([
            fakedb.Object(id=10, name='x', class_name='y'),
            fakedb.ObjectState(objectid=10, name='x', value_json='[1,2]'),
        ])
        val = await self.db.state.getState(10, 'x')

        self.assertEqual(val, [1, 2])

    def test_getState_badjson(self):
        d = self.insert_test_data([
            fakedb.Object(id=10, name='x', class_name='y'),
            fakedb.ObjectState(objectid=10, name='x', value_json='ff[1'),
        ])
        d.addCallback(lambda _: self.db.state.getState(10, 'x'))
        return self.assertFailure(d, TypeError)

    async def test_setState(self):
        await self.insert_test_data([
            fakedb.Object(id=10, name='-', class_name='-'),
        ])
        await self.db.state.setState(10, 'x', [1, 2])

        def thd(conn):
            q = self.db.model.object_state.select()
            rows = conn.execute(q).fetchall()
            self.assertEqual(
                [(r.objectid, r.name, r.value_json) for r in rows], [(10, 'x', '[1, 2]')]
            )

        await self.db.pool.do(thd)

    def test_setState_badjson(self):
        d = self.insert_test_data([
            fakedb.Object(id=10, name='x', class_name='y'),
        ])
        d.addCallback(lambda _: self.db.state.setState(10, 'x', self))  # self is not JSON-able..
        return self.assertFailure(d, TypeError)

    async def test_setState_existing(self):
        await self.insert_test_data([
            fakedb.Object(id=10, name='-', class_name='-'),
            fakedb.ObjectState(objectid=10, name='x', value_json='99'),
        ])
        await self.db.state.setState(10, 'x', [1, 2])

        def thd(conn):
            q = self.db.model.object_state.select()
            rows = conn.execute(q).fetchall()
            self.assertEqual(
                [(r.objectid, r.name, r.value_json) for r in rows], [(10, 'x', '[1, 2]')]
            )

        await self.db.pool.do(thd)

    async def test_setState_conflict(self):
        def hook(conn):
            conn.execute(
                self.db.model.object_state.insert().values(objectid=10, name='x', value_json='22')
            )
            conn.commit()

        self.db.state._test_timing_hook = hook

        await self.insert_test_data([
            fakedb.Object(id=10, name='-', class_name='-'),
        ])
        await self.db.state.setState(10, 'x', [1, 2])

        def thd(conn):
            q = self.db.model.object_state.select()
            rows = conn.execute(q).fetchall()
            self.assertEqual([(r.objectid, r.name, r.value_json) for r in rows], [(10, 'x', '22')])

        await self.db.pool.do(thd)

    async def test_atomicCreateState(self):
        await self.insert_test_data([
            fakedb.Object(id=10, name='-', class_name='-'),
        ])
        res = await self.db.state.atomicCreateState(10, 'x', lambda: [1, 2])
        self.assertEqual(res, [1, 2])
        res = await self.db.state.getState(10, 'x')
        self.assertEqual(res, [1, 2])

    async def test_atomicCreateState_conflict(self):
        await self.insert_test_data([
            fakedb.Object(id=10, name='-', class_name='-'),
        ])

        def hook(conn):
            conn.execute(
                self.db.model.object_state.insert().values(objectid=10, name='x', value_json='22')
            )
            conn.commit()

        self.db.state._test_timing_hook = hook

        res = await self.db.state.atomicCreateState(10, 'x', lambda: [1, 2])
        self.assertEqual(res, 22)
        res = await self.db.state.getState(10, 'x')
        self.assertEqual(res, 22)

    async def test_atomicCreateState_nojsonable(self):
        await self.insert_test_data([
            fakedb.Object(id=10, name='-', class_name='-'),
        ])

        d = self.db.state.atomicCreateState(10, 'x', object)
        await self.assertFailure(d, TypeError)
