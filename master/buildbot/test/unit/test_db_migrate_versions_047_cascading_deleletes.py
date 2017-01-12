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

from twisted.trial import unittest

from buildbot.test.util import migration
from buildbot.util import sautils


class Migration(migration.MigrateTestMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpMigrateTest()

    def tearDown(self):
        return self.tearDownMigrateTest()

    def create_tables_thd(self, conn):
        metadata = sa.MetaData()
        metadata.bind = conn

        builders = sautils.Table(
            'builders', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('name', sa.String(50), nullable=False),
        )
        builders.create()

        masters = sautils.Table(
            'masters', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('name', sa.String(50), nullable=False),
        )
        masters.create()

        workers = sautils.Table(
            'workers', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('name', sa.String(50), nullable=False),
        )
        workers.create()

        builder_masters = sautils.Table(
            'builder_masters', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('builderid', sa.Integer, sa.ForeignKey('builders.id'),
                      nullable=False),
            sa.Column('masterid', sa.Integer, sa.ForeignKey('masters.id'),
                      nullable=False),
        )
        builder_masters.create()

        configured_workers = sautils.Table(
            'configured_workers', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('workerid', sa.Integer, sa.ForeignKey('workers.id'),
                      nullable=False),
            sa.Column('buildermasterid', sa.Integer,
                      sa.ForeignKey('builder_masters.id'),
                      nullable=False),
        )
        configured_workers.create()

        conn.execute(builders.insert(), [
            dict(id=3, name='echo'),
            dict(id=4, name='tests'),
        ])

        conn.execute(masters.insert(), [
            dict(id=1, name='bm1'),
            dict(id=2, name='bm2'),
        ])

        conn.execute(builder_masters.insert(), [
            dict(id=1, builderid=4, masterid=1),
            dict(id=2, builderid=3, masterid=2),
        ])

        conn.execute(workers.insert(), [
            dict(id=1, name="powerful"),
            dict(id=2, name="limited"),
        ])

        conn.execute(configured_workers.insert(), [
            dict(id=1, buildermasterid=1, workerid=2),
        ])

    def test_update(self):
        def setup_thd(conn):
            self.create_tables_thd(conn)

        def verify_thd(conn):
            """Can't verify much under SQLite

            Even with PRAGMA foreign_keys=ON, the cascading deletes are
            actually ignored with SQLite, so we can't really test the behaviour
            in that environment.

            On the other hand, SQLite's FKs apparently don't prevent removals.
            The cascading behaviour is really needed for other DBs right now,
            and only in reconfigs.
            """
            metadata = sa.MetaData()
            metadata.bind = conn
            masters = sautils.Table('masters', metadata,
                                    autoload=True)
            conn.execute(masters.delete().where(masters.c.name == 'bm1'))
            q = sa.select([masters.c.id, masters.c.name])
            self.assertEqual(conn.execute(q).fetchall(),
                             [(2, 'bm2')])

        return self.do_test_migration(46, 47, setup_thd, verify_thd)
