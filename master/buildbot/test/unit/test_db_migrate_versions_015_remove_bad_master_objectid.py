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
from buildbot.test.util import migration

class Migration(migration.MigrateTestMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpMigrateTest()

    def tearDown(self):
        return self.tearDownMigrateTest()

    def create_tables_thd(self, conn):
        self.db.model.objects.create(bind=conn)
        self.db.model.object_state.create(bind=conn)

    def insert_old_obj(self, conn):
        conn.execute(self.db.model.objects.insert(),
                id=21,
                name='master',
                class_name='buildbot.master.BuildMaster')
        conn.execute(self.db.model.object_state.insert(),
                objectid=21,
                name='last_processed_change',
                value_json='938')

    def insert_new_objs(self, conn, count):
        for id in range(50, 50+count):
            conn.execute(self.db.model.objects.insert(),
                    id=id,
                    name='some_hostname:/base/dir/%d' % id,
                    class_name='BuildMaster')
            # (this id would be referenced from buildrequests, but that table
            # doesn't change)

    def assertObjectState_thd(self, conn, exp_objects=[],
                            exp_object_state=[]):
        tbl = self.db.model.objects
        res = conn.execute(tbl.select(order_by=tbl.c.id))
        got_objects = res.fetchall()

        tbl = self.db.model.object_state
        res = conn.execute(tbl.select(
            order_by=[tbl.c.objectid, tbl.c.name]))
        got_object_state = res.fetchall()

        self.assertEqual(
                dict(objects=exp_objects, object_state=exp_object_state),
                dict(objects=got_objects, object_state=got_object_state))

    # tests

    def test_empty(self):
        def setup_thd(conn):
            self.create_tables_thd(conn)
        def verify_thd(conn):
            self.assertObjectState_thd(conn, [], [])
        return self.do_test_migration(14, 15, setup_thd, verify_thd)

    def test_no_new_id(self):
        def setup_thd(conn):
            self.create_tables_thd(conn)
            self.insert_old_obj(conn)

        def verify_thd(conn):
            self.assertObjectState_thd(conn, [], [])

        return self.do_test_migration(14, 15, setup_thd, verify_thd)

    def test_one_new_id(self):
        def setup_thd(conn):
            self.create_tables_thd(conn)
            self.insert_old_obj(conn)
            self.insert_new_objs(conn, 1)

        def verify_thd(conn):
            self.assertObjectState_thd(conn, [
                (50, 'some_hostname:/base/dir/50',
                    'buildbot.master.BuildMaster'),
            ], [
                (50, 'last_processed_change', '938'),
            ])

        return self.do_test_migration(14, 15, setup_thd, verify_thd)

    def test_two_new_ids(self):
        def setup_thd(conn):
            self.create_tables_thd(conn)
            self.insert_old_obj(conn)
            self.insert_new_objs(conn, 2)

        def verify_thd(conn):
            self.assertObjectState_thd(conn, [
                (50, 'some_hostname:/base/dir/50',
                    'buildbot.master.BuildMaster'),
                (51, 'some_hostname:/base/dir/51',
                    'buildbot.master.BuildMaster'),
            ], [
                # last_processed_change is just deleted
            ])

        return self.do_test_migration(14, 15, setup_thd, verify_thd)

