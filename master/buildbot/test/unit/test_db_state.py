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

from twisted.trial import unittest
from buildbot.db import state
from buildbot.test.util import connector_component
from buildbot.test.fake import fakedb

class TestStateConnectorComponent(
            connector_component.ConnectorComponentMixin,
            unittest.TestCase):

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['objects', 'object_state' ])

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
                    [ (r.id, r.name, r.class_name) for r in rows ],
                    [ (objectid, 'someobj', 'someclass') ])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_getObjectId_existing(self):
        d = self.insertTestData([
                        fakedb.Object(id=19, name='someobj',
                                    class_name='someclass') ])
        d.addCallback(lambda _ :
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
        d.addCallback(lambda _ :
            self.db.state.getState(10, 'x'))
        def check(val):
            self.assertEqual(val, [1,2])
        d.addCallback(check)
        return d

    def test_getState_badjson(self):
        d = self.insertTestData([
            fakedb.Object(id=10, name='x', class_name='y'),
            fakedb.ObjectState(objectid=10, name='x', value_json='ff[1'),
        ])
        d.addCallback(lambda _ :
            self.db.state.getState(10, 'x'))
        return self.assertFailure(d, TypeError)

    def test_setState(self):
        d = self.insertTestData([
            fakedb.Object(id=10, name='-', class_name='-'),
        ])
        d.addCallback(lambda _ :
            self.db.state.setState(10, 'x', [1,2]))
        def check(_):
            def thd(conn):
                q = self.db.model.object_state.select()
                rows = conn.execute(q).fetchall()
                self.assertEqual(
                    [ (r.objectid, r.name, r.value_json) for r in rows ],
                    [ (10, 'x', '[1, 2]') ])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_setState_badjson(self):
        d = self.insertTestData([
            fakedb.Object(id=10, name='x', class_name='y'),
        ])
        d.addCallback(lambda _ :
            self.db.state.setState(10, 'x', self)) # self is not JSON-able..
        return self.assertFailure(d, TypeError)

    def test_setState_existing(self):
        d = self.insertTestData([
            fakedb.Object(id=10, name='-', class_name='-'),
            fakedb.ObjectState(objectid=10, name='x', value_json='99'),
        ])
        d.addCallback(lambda _ :
            self.db.state.setState(10, 'x', [1,2]))
        def check(_):
            def thd(conn):
                q = self.db.model.object_state.select()
                rows = conn.execute(q).fetchall()
                self.assertEqual(
                    [ (r.objectid, r.name, r.value_json) for r in rows ],
                    [ (10, 'x', '[1, 2]') ])
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
        d.addCallback(lambda _ :
            self.db.state.setState(10, 'x', [1,2]))
        def check(_):
            def thd(conn):
                q = self.db.model.object_state.select()
                rows = conn.execute(q).fetchall()
                self.assertEqual(
                    [ (r.objectid, r.name, r.value_json) for r in rows ],
                    [ (10, 'x', '22') ])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_getObjectStateByKey(self):
        d = self.insertTestData(
            [fakedb.Object(id=1, name='https://github.com/Unity-Technologies/buildbot.git', class_name='GitPoller'),
             fakedb.ObjectState(objectid='1', name='lastRev',
                                value_json='{"staging": "97ae8b254839aad207ae841765a645c4247fac57",'+
                                           ' "master": "5384a30f2f774258647fdf6cbb387e7a385776dc",'+
                                           ' "katana": "3fdf2ccbb97cb662ab1f9a6bf6c59482ebabe60b",'+
                                           ' "buildbot-0.8.6": "2719db681f1fc812ce0e8bdea899cd43cd3d9f68",'+
                                           ' "buildbot-0.8.7": "4ed9634056182dc3825165dc6a71b2ba98b08e5e",'+
                                           ' "buildbot-0.8.4": "c8bcb29d2a240087a3db2bee42abf986989887a1",'+
                                           ' "buildbot-0.8.5": "80a524bb75ccac88894a22827d7df2fddcd81557",'+
                                           ' "buildbot-0.8.2": "9561ca2d7062e2727d338c87aab6430dce2dc81e"}')])
        selection = {'https://github.com/Unity-Technologies/buildbot.git':
                         {'codebase': 'katana-buildbot',
                          'display_repository': 'https://github.com/Unity-Technologies/buildbot.git',
                          'branch': 'katana', 'revision': ''}}


        def check(result):
            expected_result = {'https://github.com/Unity-Technologies/buildbot.git':
                                   {'codebase': 'katana-buildbot',
                                    'revision': u'3fdf2ccbb97cb662ab1f9a6bf6c59482ebabe60b',
                                    'branch': 'katana',
                                    'display_repository':'https://github.com/Unity-Technologies/buildbot.git'}}

            self.assertEqual(result, expected_result)

        d.addCallback(lambda _: self.db.state.getObjectStateByKey(selection, 'branch', 'revision'))
        d.addCallback(check)
        return d
