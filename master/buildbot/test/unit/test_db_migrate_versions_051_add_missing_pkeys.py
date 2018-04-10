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
from __future__ import unicode_literals

import sqlalchemy as sa

from twisted.trial import unittest

from buildbot.test.util import migration
from buildbot.util import sautils


class Migration(migration.MigrateTestMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpMigrateTest()

    def tearDown(self):
        return self.tearDownMigrateTest()

    def create_tables(self, conn):
        metadata = sa.MetaData()
        metadata.bind = conn

        # create tables (prior to schema migration)
        masters = sautils.Table(
            "masters", metadata,
            sa.Column('id', sa.Integer, primary_key=True),
        )
        masters.create()

        users = sautils.Table(
            "users", metadata,
            sa.Column("uid", sa.Integer, primary_key=True),
        )
        users.create()

        workers = sautils.Table(
            "workers", metadata,
            sa.Column("id", sa.Integer, primary_key=True),
        )
        workers.create()

        sourcestamps = sautils.Table(
            'sourcestamps', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
        )
        sourcestamps.create()

        schedulers = sautils.Table(
            'schedulers', metadata,
            sa.Column("id", sa.Integer, primary_key=True),
        )
        schedulers.create()

        buildsets = sautils.Table(
            'buildsets', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
        )
        buildsets.create()

        builders = sautils.Table(
            'builders', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
        )
        builders.create()

        buildrequests = sautils.Table(
            'buildrequests', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('buildsetid', sa.Integer,
                      sa.ForeignKey('buildsets.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('builderid', sa.Integer,
                      sa.ForeignKey('builders.id', ondelete='CASCADE'),
                      nullable=False),
        )
        buildrequests.create()

        builds = sautils.Table(
            'builds', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('builderid', sa.Integer,
                      sa.ForeignKey('builders.id', ondelete='CASCADE')),
            sa.Column('buildrequestid', sa.Integer,
                      sa.ForeignKey(
                          'buildrequests.id', use_alter=True,
                          name='buildrequestid', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('workerid', sa.Integer,
                      sa.ForeignKey('workers.id', ondelete='CASCADE')),
            sa.Column('masterid', sa.Integer,
                      sa.ForeignKey('masters.id', ondelete='CASCADE'),
                      nullable=False),
        )
        builds.create()

        buildrequest_claims = sautils.Table(
            'buildrequest_claims', metadata,
            sa.Column('brid', sa.Integer,
                      sa.ForeignKey('buildrequests.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('masterid', sa.Integer,
                      sa.ForeignKey('masters.id', ondelete='CASCADE'),
                      index=True, nullable=True),
        )
        buildrequest_claims.create()

        build_properties = sautils.Table(
            'build_properties', metadata,
            sa.Column('buildid', sa.Integer,
                      sa.ForeignKey('builds.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('name', sa.String(256), nullable=False),
        )
        build_properties.create()

        steps = sautils.Table(
            'steps', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('buildid', sa.Integer,
                      sa.ForeignKey('builds.id', ondelete='CASCADE')),
        )
        steps.create()

        logs = sautils.Table(
            'logs', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('stepid', sa.Integer,
                      sa.ForeignKey('steps.id', ondelete='CASCADE')),
        )
        logs.create()

        logchunks = sautils.Table(
            'logchunks', metadata,
            sa.Column('logid', sa.Integer,
                      sa.ForeignKey('logs.id', ondelete='CASCADE')),
            sa.Column('first_line', sa.Integer, nullable=False),
            sa.Column('last_line', sa.Integer, nullable=False),
        )
        logchunks.create()

        buildset_properties = sautils.Table(
            'buildset_properties', metadata,
            sa.Column('buildsetid', sa.Integer,
                      sa.ForeignKey('buildsets.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('property_name', sa.String(256), nullable=False),
        )
        buildset_properties.create()

        changes = sautils.Table(
            'changes', metadata,
            sa.Column('changeid', sa.Integer, primary_key=True),
            sa.Column('sourcestampid', sa.Integer,
                      sa.ForeignKey('sourcestamps.id', ondelete='CASCADE')),
            sa.Column('parent_changeids', sa.Integer,
                      sa.ForeignKey('changes.changeid', ondelete='CASCADE'),
                      nullable=True),
        )
        changes.create()

        change_files = sautils.Table(
            'change_files', metadata,
            sa.Column('changeid', sa.Integer,
                      sa.ForeignKey('changes.changeid', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('filename', sa.String(1024), nullable=False),
        )
        change_files.create()

        change_properties = sautils.Table(
            'change_properties', metadata,
            sa.Column('changeid', sa.Integer,
                      sa.ForeignKey('changes.changeid', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('property_name', sa.String(256), nullable=False),
        )
        change_properties.create()

        change_users = sautils.Table(
            "change_users", metadata,
            sa.Column('changeid', sa.Integer,
                      sa.ForeignKey('changes.changeid', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('uid', sa.Integer,
                      sa.ForeignKey('users.uid', ondelete='CASCADE'),
                      nullable=False),
        )
        change_users.create()

        patches = sautils.Table(
            'patches', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
        )
        patches.create()

        scheduler_changes = sautils.Table(
            'scheduler_changes', metadata,
            sa.Column('schedulerid', sa.Integer,
                      sa.ForeignKey('schedulers.id', ondelete='CASCADE')),
            sa.Column('changeid', sa.Integer,
                      sa.ForeignKey('changes.changeid', ondelete='CASCADE')),
        )
        scheduler_changes.create()

        objects = sautils.Table(
            "objects", metadata,
            sa.Column("id", sa.Integer, primary_key=True),
        )
        objects.create()

        object_state = sautils.Table(
            "object_state", metadata,
            sa.Column('objectid', sa.Integer,
                      sa.ForeignKey('objects.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
        )
        object_state.create()

        users_info = sautils.Table(
            "users_info", metadata,
            sa.Column('uid', sa.Integer,
                      sa.ForeignKey('users.uid', ondelete='CASCADE'),
                      nullable=False),
            sa.Column("attr_type", sa.String(128), nullable=False),
        )
        users_info.create()

    TABLE_NAMES = (
        'buildrequest_claims',
        'build_properties',
        'logchunks',
        'buildset_properties',
        'change_files',
        'change_properties',
        'change_users',
        'scheduler_changes',
        'object_state',
        'users_info',
    )

    def test_update(self):
        def setup_thd(conn):
            self.create_tables(conn)

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn
            for t in self.TABLE_NAMES:
                table = sautils.Table(t, metadata, autoload=True)
                found_pkey = False
                for cons in table.constraints:
                    if isinstance(cons, sa.PrimaryKeyConstraint):
                        found_pkey = True
                        break
                self.assertTrue(found_pkey,
                                'missing primary key in table %s' % table)

        return self.do_test_migration(50, 51, setup_thd, verify_thd)
