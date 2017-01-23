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

import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.db.types.json import JsonObject
from buildbot.test.util import migration
from buildbot.util import sautils


class Migration(migration.MigrateTestMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpMigrateTest()

    def tearDown(self):
        return self.tearDownMigrateTest()

    def _define_old_tables(self, metadata):
        self.buildrequests = sautils.Table(
            'buildrequests', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('buildsetid', sa.Integer, sa.ForeignKey('buildsets.id'),
                      nullable=False),
            # ...
        )

        self.buildsets = sautils.Table(
            'buildsets', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('parent_buildid', sa.Integer,
                      sa.ForeignKey('builds.id', use_alter=True, name='parent_buildid')),
            # ...
        )

        self.builders = sautils.Table(
            'builders', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            # ...
        )

        self.builder_masters = sautils.Table(
            'builder_masters', metadata,
            sa.Column('id', sa.Integer, primary_key=True, nullable=False),
            # ...
        )

        self.masters = sautils.Table(
            "masters", metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            # ...
        )

        self.builds = sautils.Table(
            'builds', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('number', sa.Integer, nullable=False),
            sa.Column('builderid', sa.Integer, sa.ForeignKey('builders.id')),
            sa.Column('buildrequestid', sa.Integer, sa.ForeignKey('buildrequests.id'),
                      nullable=False),
            sa.Column('buildslaveid', sa.Integer),
            sa.Column('masterid', sa.Integer, sa.ForeignKey('masters.id'),
                      nullable=False),
            sa.Column('started_at', sa.Integer, nullable=False),
            sa.Column('complete_at', sa.Integer),
            sa.Column(
                'state_string', sa.Text, nullable=False),
            sa.Column('results', sa.Integer),
        )

        self.buildslaves = sautils.Table(
            "buildslaves", metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String(50), nullable=False),
            sa.Column("info", JsonObject, nullable=False),
        )

        self.configured_buildslaves = sautils.Table(
            'configured_buildslaves', metadata,
            sa.Column('id', sa.Integer, primary_key=True, nullable=False),
            sa.Column('buildermasterid', sa.Integer,
                      sa.ForeignKey('builder_masters.id'), nullable=False),
            sa.Column('buildslaveid', sa.Integer, sa.ForeignKey('buildslaves.id'),
                      nullable=False),
        )

        self.connected_buildslaves = sautils.Table(
            'connected_buildslaves', metadata,
            sa.Column('id', sa.Integer, primary_key=True, nullable=False),
            sa.Column('masterid', sa.Integer,
                      sa.ForeignKey('masters.id'), nullable=False),
            sa.Column('buildslaveid', sa.Integer, sa.ForeignKey('buildslaves.id'),
                      nullable=False),
        )

    def _create_tables_thd(self, conn):
        metadata = sa.MetaData()
        metadata.bind = conn

        self._define_old_tables(metadata)

        metadata.create_all()

        sa.Index(
            'builds_buildrequestid', self.builds.c.buildrequestid).create()
        sa.Index('builds_number',
                 self.builds.c.builderid, self.builds.c.number,
                 unique=True).create()
        sa.Index('builds_buildslaveid', self.builds.c.buildslaveid).create()
        sa.Index('builds_masterid', self.builds.c.masterid).create()

        sa.Index(
            'buildslaves_name', self.buildslaves.c.name, unique=True).create()

        sa.Index('configured_slaves_buildmasterid',
                 self.configured_buildslaves.c.buildermasterid).create()
        sa.Index('configured_slaves_slaves',
                 self.configured_buildslaves.c.buildslaveid).create()
        sa.Index('configured_slaves_identity',
                 self.configured_buildslaves.c.buildermasterid,
                 self.configured_buildslaves.c.buildslaveid, unique=True).create()

        sa.Index('connected_slaves_masterid',
                 self.connected_buildslaves.c.masterid).create()
        sa.Index('connected_slaves_slaves',
                 self.connected_buildslaves.c.buildslaveid).create()
        sa.Index('connected_slaves_identity',
                 self.connected_buildslaves.c.masterid,
                 self.connected_buildslaves.c.buildslaveid, unique=True).create()

    @defer.inlineCallbacks
    def test_update_inconsistent_builds_buildslaves(self):
        def setup_thd(conn):
            self._create_tables_thd(conn)

            conn.execute(self.masters.insert(), [
                dict(id=1),
                dict(id=2),
            ])
            conn.execute(self.buildsets.insert(), [dict(id=5)])
            conn.execute(self.buildrequests.insert(), [
                dict(id=3, buildsetid=5),
                dict(id=4, buildsetid=5),

            ])
            conn.execute(self.buildslaves.insert(), [
                dict(id=30,
                     name='worker-1',
                     info={}),
                dict(id=31,
                     name='worker-2',
                     info={"a": 1}),
            ])
            conn.execute(self.builds.insert(), [
                dict(id=10,
                     number=2,
                     buildrequestid=3,
                     buildslaveid=123,
                     masterid=1,
                     started_at=0,
                     state_string='state'),
                dict(id=11,
                     number=1,
                     buildrequestid=4,
                     buildslaveid=31,
                     masterid=2,
                     started_at=1000,
                     state_string='state2'),
            ])

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            # Verify database contents.

            # 'workers' table contents.
            workers = sautils.Table('workers', metadata, autoload=True)
            c = workers.c
            q = sa.select(
                [c.id, c.name, c.info]
            ).order_by(c.id)
            self.assertEqual(
                q.execute().fetchall(), [
                    (30, u'worker-1', u'{}'),
                    (31, u'worker-2', u'{"a": 1}'),
                ])

            # 'builds' table contents.
            builds = sautils.Table('builds', metadata, autoload=True)
            c = builds.c
            q = sa.select(
                [c.id, c.number, c.builderid, c.buildrequestid, c.workerid,
                 c.masterid, c.started_at, c.complete_at, c.state_string,
                 c.results]
            ).order_by(c.id)
            # Check that build with invalid reference to buildslaves now
            # have no reference to it.
            self.assertEqual(
                q.execute().fetchall(), [
                    (10, 2, None, 3, None, 1, 0, None, u'state', None),
                    (11, 1, None, 4, 31, 2, 1000, None, u'state2', None),
                ])

        yield self.do_test_migration(44, 45, setup_thd, verify_thd)

    def test_update(self):
        def setup_thd(conn):
            self._create_tables_thd(conn)

            conn.execute(self.masters.insert(), [
                dict(id=10),
                dict(id=11),
            ])
            conn.execute(self.buildsets.insert(), [
                dict(id=90),
                dict(id=91),
            ])
            conn.execute(self.buildrequests.insert(), [
                dict(id=20, buildsetid=90),
                dict(id=21, buildsetid=91),
            ])
            conn.execute(self.builders.insert(), [
                dict(id=50)
            ])
            conn.execute(self.buildslaves.insert(), [
                dict(id=30,
                     name='worker-1',
                     info={}),
                dict(id=31,
                     name='worker-2',
                     info={"a": 1}),
            ])
            conn.execute(self.builds.insert(), [
                dict(id=40,
                     number=1,
                     buildrequestid=20,
                     buildslaveid=30,
                     masterid=10,
                     started_at=1000,
                     state_string='state'),
            ])
            conn.execute(self.builds.insert(), [
                dict(id=41,
                     number=2,
                     builderid=50,
                     buildrequestid=21,
                     masterid=11,
                     started_at=2000,
                     complete_at=3000,
                     state_string='state 2',
                     results=9),
            ])

            conn.execute(self.builder_masters.insert(), [
                dict(id=70),
                dict(id=71),
            ])

            conn.execute(self.configured_buildslaves.insert(), [
                dict(id=60,
                     buildermasterid=70,
                     buildslaveid=30),
                dict(id=61,
                     buildermasterid=71,
                     buildslaveid=31),
            ])

            conn.execute(self.connected_buildslaves.insert(), [
                dict(id=80,
                     masterid=10,
                     buildslaveid=30),
                dict(id=81,
                     masterid=11,
                     buildslaveid=31),
            ])

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            # Verify database contents.

            # 'workers' table contents.
            workers = sautils.Table('workers', metadata, autoload=True)
            c = workers.c
            q = sa.select(
                [c.id, c.name, c.info]
            ).order_by(c.id)
            self.assertEqual(
                q.execute().fetchall(), [
                    (30, u'worker-1', u'{}'),
                    (31, u'worker-2', u'{"a": 1}'),
                ])

            # 'builds' table contents.
            builds = sautils.Table('builds', metadata, autoload=True)
            c = builds.c
            q = sa.select(
                [c.id, c.number, c.builderid, c.buildrequestid, c.workerid,
                 c.masterid, c.started_at, c.complete_at, c.state_string,
                 c.results]
            ).order_by(c.id)
            self.assertEqual(
                q.execute().fetchall(), [
                    (40, 1, None, 20, 30, 10, 1000, None, u'state', None),
                    (41, 2, 50, 21, None, 11, 2000, 3000, u'state 2', 9),
                ])

            # 'configured_workers' table contents.
            configured_workers = sautils.Table(
                'configured_workers', metadata, autoload=True)
            c = configured_workers.c
            q = sa.select(
                [c.id, c.buildermasterid, c.workerid]
            ).order_by(c.id)
            self.assertEqual(
                q.execute().fetchall(), [
                    (60, 70, 30),
                    (61, 71, 31),
                ])

            # 'connected_workers' table contents.
            connected_workers = sautils.Table(
                'connected_workers', metadata, autoload=True)
            c = connected_workers.c
            q = sa.select(
                [c.id, c.masterid, c.workerid]
            ).order_by(c.id)
            self.assertEqual(
                q.execute().fetchall(), [
                    (80, 10, 30),
                    (81, 11, 31),
                ])

            # Verify that there is no "slave"-named items in schema.
            inspector = Inspector(conn)

            def check_name(name, table_name, item_type):
                if not name:
                    return
                self.assertTrue(
                    u"slave" not in name.lower(),
                    msg=u"'slave'-named {type} in table '{table}': "
                        u"'{name}'".format(
                        type=item_type, table=table_name,
                        name=name))

            # Check every table.
            for table_name in inspector.get_table_names():
                # Check table name.
                check_name(table_name, table_name, u"table name")

                # Check column names.
                for column_info in inspector.get_columns(table_name):
                    check_name(column_info['name'], table_name, u"column")

                # Check foreign key names.
                for fk_info in inspector.get_foreign_keys(table_name):
                    check_name(fk_info['name'], table_name, u"foreign key")

                # Check indexes names.
                for index_info in inspector.get_indexes(table_name):
                    check_name(index_info['name'], table_name, u"index")

                # Check primary keys constraints names.
                pk_info = inspector.get_pk_constraint(table_name)
                check_name(pk_info.get('name'), table_name, u"primary key")

            # Test that no "slave"-named items present in schema
            for name in inspector.get_schema_names():
                self.assertTrue(u"slave" not in name.lower())

        return self.do_test_migration(44, 45, setup_thd, verify_thd)
