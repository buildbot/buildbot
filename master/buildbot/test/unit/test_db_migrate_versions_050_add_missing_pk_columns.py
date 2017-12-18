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

        patches = sautils.Table(
            'patches', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('patchlevel', sa.Integer, nullable=False),
            sa.Column('patch_base64', sa.Text, nullable=False),
            sa.Column('patch_author', sa.Text, nullable=False),
            sa.Column('patch_comment', sa.Text, nullable=False),
            sa.Column('subdir', sa.Text),
        )
        patches.create()
        conn.execute(patches.insert(), [
            dict(id=0, patchlevel=0, patch_base64='dummy', patch_author='dummy', patch_comment='dummy')])

        sourcestamps = sautils.Table(
            'sourcestamps', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('ss_hash', sa.String(40), nullable=False),
            sa.Column('branch', sa.String(256)),
            sa.Column('revision', sa.String(256)),
            sa.Column('patchid', sa.Integer, sa.ForeignKey('patches.id')),
            sa.Column('repository', sa.String(length=512), nullable=False,
                      server_default=''),
            sa.Column('codebase', sa.String(256), nullable=False,
                      server_default=sa.DefaultClause("")),
            sa.Column('project', sa.String(length=512), nullable=False,
                      server_default=''),
            sa.Column('created_at', sa.Integer, nullable=False),
        )
        sourcestamps.create()
        conn.execute(sourcestamps.insert(), [
            dict(id=0, ss_hash='dummy', patchid=0, created_at=0)])

        changes = sautils.Table(
            'changes', metadata,
            sa.Column('changeid', sa.Integer, primary_key=True),
            sa.Column('author', sa.String(255), nullable=False),
            sa.Column('comments', sa.Text, nullable=False),
            sa.Column('branch', sa.String(255)),
            sa.Column('revision', sa.String(255)),  # CVS uses NULL
            sa.Column('revlink', sa.String(256)),
            sa.Column('when_timestamp', sa.Integer, nullable=False),
            sa.Column('category', sa.String(255)),
            sa.Column('repository', sa.String(length=512), nullable=False,
                      server_default=''),
            sa.Column('codebase', sa.String(256), nullable=False,
                      server_default=sa.DefaultClause("")),
            sa.Column('project', sa.String(length=512), nullable=False,
                      server_default=''),
            sa.Column('sourcestampid', sa.Integer,
                       sa.ForeignKey('sourcestamps.id')),
            sa.Column('parent_changeids', sa.Integer, sa.ForeignKey(
                      'changes.changeid'), nullable=True),
        )
        changes.create()
        conn.execute(changes.insert(), [
            dict(changeid=0, author='dummy', comments='dummy', when_timestamp=0, parent_changeids=0)])

        builders = sautils.Table(
            'builders', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('name', sa.Text, nullable=False),
            sa.Column('description', sa.Text, nullable=True),
            sa.Column('name_hash', sa.String(40), nullable=False),
        )
        builders.create()
        conn.execute(builders.insert(), [
            dict(id=0, name='dummy', name_hash='dummy')])

        buildrequests = sautils.Table(
            'buildrequests', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('buildsetid', sa.Integer, sa.ForeignKey("buildsets.id"),
                      nullable=False),
            sa.Column('builderid', sa.Integer, sa.ForeignKey('builders.id'),
                      nullable=False),
            sa.Column('priority', sa.Integer, nullable=False,
                      server_default=sa.DefaultClause("0")),
            sa.Column('complete', sa.Integer,
                      server_default=sa.DefaultClause("0")),
            sa.Column('results', sa.SmallInteger),
            sa.Column('submitted_at', sa.Integer, nullable=False),
            sa.Column('complete_at', sa.Integer),
            sa.Column('waited_for', sa.SmallInteger,
                      server_default=sa.DefaultClause("0")),
        )
        buildrequests.create()
        conn.execute(buildrequests.insert(), [
            dict(id=0, buildsetid=0, builderid=0, submitted_at=0)])

        workers = sautils.Table(
            "workers", metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String(50), nullable=False),
            sa.Column("info", JsonObject, nullable=False),
        )
        workers.create()
        conn.execute(workers.insert(), [
            dict(id=0, name='dummy', info={'dummy':0})])

        masters = sautils.Table(
            "masters", metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('name', sa.Text, nullable=False),
            sa.Column('name_hash', sa.String(40), nullable=False),
            sa.Column('active', sa.Integer, nullable=False),
            sa.Column('last_active', sa.Integer, nullable=False),
        )
        masters.create()
        conn.execute(masters.insert(), [
            dict(id=0, name='dummy', name_hash='dummy', active=0, last_active=0)])

        builds = sautils.Table(
            'builds', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('number', sa.Integer, nullable=False),
            sa.Column('builderid', sa.Integer, sa.ForeignKey('builders.id')),
            sa.Column('buildrequestid', sa.Integer,
                      sa.ForeignKey(
                          'buildrequests.id', use_alter=True, name='buildrequestid'),
                      nullable=False),
            sa.Column('workerid', sa.Integer, sa.ForeignKey('workers.id')),
            sa.Column('masterid', sa.Integer, sa.ForeignKey('masters.id'),
                      nullable=False),
            sa.Column('started_at', sa.Integer, nullable=False),
            sa.Column('complete_at', sa.Integer),
            sa.Column('state_string', sa.Text, nullable=False),
            sa.Column('results', sa.Integer),
        )
        builds.create()
        conn.execute(builds.insert(), [
            dict(id=0, number=0, builderid=0, buildrequestid=0, wokerid=0, masterid=0, started_at=0, state_string='dummy')])

        buildsets = sautils.Table(
            'buildsets', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('external_idstring', sa.String(256)),
            sa.Column('reason', sa.String(256)),
            sa.Column('submitted_at', sa.Integer, nullable=False),
            sa.Column('complete', sa.SmallInteger, nullable=False,
                      server_default=sa.DefaultClause("0")),
            sa.Column('complete_at', sa.Integer),
            sa.Column('results', sa.SmallInteger),
            sa.Column('parent_buildid', sa.Integer,
                      sa.ForeignKey('builds.id', use_alter=True, name='parent_buildid')),
            sa.Column('parent_relationship', sa.Text),
        )
        buildsets.create()
        conn.execute(buildsets.insert(), [
            dict(id=0, submitted_at=0, complete=0 , parent_buildid=0)])

        change_files = sautils.Table(
            'change_files', metadata,
            sa.Column('changeid', sa.Integer, sa.ForeignKey('changes.changeid'),
                      nullable=False),
            sa.Column('filename', sa.String(1024), nullable=False),
        )
        change_files.create()
        conn.execute(change_files.insert(), [
            dict(changeid=0, filename='foo')])

        buildset_properties = sautils.Table(
            'buildset_properties', metadata,
            sa.Column('buildsetid', sa.Integer, sa.ForeignKey('buildsets.id'),
                      nullable=False),
            sa.Column('property_name', sa.String(256), nullable=False),
            sa.Column('property_value', sa.Text, nullable=False),
        )
        buildset_properties.create()
        conn.execute(buildset_properties.insert(), [
            dict(buildsetid=0, property_name='foo', property_value='bar')])

        build_properties = sautils.Table(
            'build_properties', metadata,
            sa.Column('buildid', sa.Integer, sa.ForeignKey('builds.id'),
                      nullable=False),
            sa.Column('name', sa.String(256), nullable=False),
            sa.Column('value', sa.Text, nullable=False),
            sa.Column('source', sa.String(256), nullable=False),
        )
        build_properties.create()
        conn.execute(build_properties.insert(), [
            dict(buildid=0, name='foo', value='bar', source='baz')])

        change_properties = sautils.Table(
            'change_properties', metadata,
            sa.Column('changeid', sa.Integer, sa.ForeignKey('changes.changeid'),
                      nullable=False),
            sa.Column('property_name', sa.String(256), nullable=False),
            sa.Column('property_value', sa.Text, nullable=False),
        )
        change_properties.create()
        conn.execute(change_properties.insert(), [
            dict(changeid=0, property_name='foo', property_value='bar')])

    def test_update(self):
        def setup_thd(conn):
            self.create_tables_thd(conn)

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            change_files = sautils.Table('change_files', metadata, autoload=True)
            self.assertIsInstance(change_files.c.changefileid.type, sa.Integer)

            buildset_properties = sautils.Table('buildset_properties', metadata, autoload=True)
            self.assertIsInstance(buildset_properties.c.buildsetpropertyid.type, sa.Integer)

            build_properties = sautils.Table('build_properties', metadata, autoload=True)
            self.assertIsInstance(build_properties.c.buildpropertyid.type, sa.Integer)

            change_properties = sautils.Table('change_properties', metadata, autoload=True)
            self.assertIsInstance(change_properties.c.changepropertyid.type, sa.Integer)

        return self.do_test_migration(49, 50, setup_thd, verify_thd)
