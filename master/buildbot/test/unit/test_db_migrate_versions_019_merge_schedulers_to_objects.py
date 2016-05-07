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

        changes = sautils.Table(
            'changes', metadata,
            sa.Column('changeid', sa.Integer, primary_key=True),
            # the rest is unimportant
        )
        changes.create()

        buildsets = sautils.Table(
            'buildsets', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            # the rest is unimportant
        )
        buildsets.create()

        self.schedulers = sautils.Table(
            "schedulers", metadata,
            sa.Column('schedulerid', sa.Integer, primary_key=True),
            sa.Column('name', sa.String(128), nullable=False),
            sa.Column('class_name', sa.String(128), nullable=False),
        )
        self.schedulers.create(bind=conn)
        sa.Index('name_and_class', self.schedulers.c.name,
                 self.schedulers.c.class_name).create()

        self.scheduler_changes = sautils.Table(
            'scheduler_changes', metadata,
            sa.Column('schedulerid', sa.Integer,
                      sa.ForeignKey('schedulers.schedulerid')),
            sa.Column('changeid', sa.Integer,
                      sa.ForeignKey('changes.changeid')),
            sa.Column('important', sa.SmallInteger),
        )
        self.scheduler_changes.create()
        sa.Index('scheduler_changes_schedulerid',
                 self.scheduler_changes.c.schedulerid).create()
        sa.Index('scheduler_changes_changeid',
                 self.scheduler_changes.c.changeid).create()
        sa.Index('scheduler_changes_unique',
                 self.scheduler_changes.c.schedulerid,
                 self.scheduler_changes.c.changeid, unique=True).create()

        self.scheduler_upstream_buildsets = sautils.Table(
            'scheduler_upstream_buildsets', metadata,
            sa.Column('buildsetid', sa.Integer, sa.ForeignKey('buildsets.id')),
            sa.Column('schedulerid', sa.Integer,
                      sa.ForeignKey('schedulers.schedulerid')),
        )
        self.scheduler_upstream_buildsets.create()

        sa.Index('scheduler_upstream_buildsets_buildsetid',
                 self.scheduler_upstream_buildsets.c.buildsetid).create()
        sa.Index('scheduler_upstream_buildsets_schedulerid',
                 self.scheduler_upstream_buildsets.c.schedulerid).create()

        self.objects = sautils.Table(
            "objects", metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column('name', sa.String(128), nullable=False),
            sa.Column('class_name', sa.String(128), nullable=False),
        )
        self.objects.create(bind=conn)

        sa.Index('object_identity', self.objects.c.name,
                 self.objects.c.class_name, unique=True).create()

    # tests

    def test_update(self):
        # this upgrade script really just drops a bunch of tables, so
        # there's not much to test!
        def setup_thd(conn):
            self.create_tables_thd(conn)

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            # these tables are gone
            for tbl in 'schedulers', 'scheduler_upstream_buildsets':
                try:
                    conn.execute("select * from %s" % tbl)
                except Exception:
                    pass
                else:
                    self.fail("%s table still exists" % tbl)

            # but scheduler_changes is not
            s_c_tbl = sautils.Table("scheduler_changes", metadata,
                                    autoload=True)
            q = sa.select(
                [s_c_tbl.c.objectid, s_c_tbl.c.changeid, s_c_tbl.c.important])
            self.assertEqual(conn.execute(q).fetchall(), [])

        return self.do_test_migration(18, 19, setup_thd, verify_thd)
