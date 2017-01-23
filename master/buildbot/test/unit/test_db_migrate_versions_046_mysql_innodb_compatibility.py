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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.util import migration
from buildbot.util import sautils


class Migration(migration.MigrateTestMixin, unittest.TestCase):

    table_columns = {
        'changes': ['author', 'branch', 'revision', 'category'],
        'object_state': ['name'],
        'users': ['identifier']
    }

    def setUp(self):
        return self.setUpMigrateTest()

    def tearDown(self):
        return self.tearDownMigrateTest()

    def _define_old_tables(self, conn):
        metadata = sa.MetaData()
        metadata.bind = conn

        self.changes = sautils.Table(
            'changes', metadata,
            # ...
            sa.Column('changeid', sa.Integer, primary_key=True),
            sa.Column('author', sa.String(256), nullable=False),
            sa.Column('branch', sa.String(256)),
            sa.Column('revision', sa.String(256)),  # CVS uses NULL
            sa.Column('category', sa.String(256)))

        self.object_state = sautils.Table(
            "object_state", metadata,
            # ...
            sa.Column("objectid", sa.Integer,
                      # commented not to add objects table
                      # sa.ForeignKey('objects.id'),
                      nullable=False),
            sa.Column("name", sa.String(length=256), nullable=False))

        self.users = sautils.Table(
            "users", metadata,
            # ...
            sa.Column("uid", sa.Integer, primary_key=True),
            sa.Column("identifier", sa.String(256), nullable=False),
        )

    def create_tables_thd(self, conn):
        self._define_old_tables(conn)
        self.changes.create()
        self.object_state.create()
        self.users.create()

    def test_update(self):
        def setup_thd(conn):
            self.create_tables_thd(conn)

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            conn.execute(self.changes.insert(), [
                dict(changeid=1,
                     author="a" * 255,
                     branch="a",
                     revision="a",
                     category="a")])
            conn.execute(self.object_state.insert(), [
                dict(objectid=1,
                     name="a" * 255)])

            conn.execute(self.users.insert(), [
                dict(uid=1,
                     identifier="a" * 255)])

            # Verify that the columns have been updated to sa.Strint(255)
            for table, columns in self.table_columns.items():
                tbl = sautils.Table(table, metadata, autoload=True)
                for column in columns:
                    self.assertIsInstance(
                        getattr(tbl.c, column).type, sa.String)
                    self.assertEqual(getattr(tbl.c, column).type.length, 255)

        return self.do_test_migration(45, 46, setup_thd, verify_thd)

    @defer.inlineCallbacks
    def assertExpectedMessage(self, d, expected_msg):
        exception = None
        try:
            yield d
        except Exception as e:
            exception = e
        self.flushLoggedErrors()
        self.assertEqual(str(exception), expected_msg)

    def do_invalid_test(self, table, value, expected_msg):

        def setup_thd(conn):
            self.create_tables_thd(conn)
            metadata = sa.MetaData()
            metadata.bind = conn
            conn.execute(getattr(self, table).insert(), [value])
        return self.assertExpectedMessage(self.do_test_migration(45, 46, setup_thd, None),
                                          expected_msg)

    def test_invalid_author_in_changes(self):
        return self.do_invalid_test('changes', dict(changeid=1,
                                                    author="a" * 256,
                                                    branch="a",
                                                    revision="a",
                                                    category="a"),
                                    "\n".join(["",
                                               "- 'changes' table has invalid data:",
                                               "    changes.change=1 has author, branch, revision or category longer than 255"]))

    def test_invalid_branch_in_changes(self):
        return self.do_invalid_test('changes', dict(changeid=1,
                                                    author="a",
                                                    branch="a" * 256,
                                                    revision="a",
                                                    category="a"),
                                    "\n".join(["",
                                               "- 'changes' table has invalid data:",
                                               "    changes.change=1 has author, branch, revision or category longer than 255"]))

    def test_invalid_revision_in_changes(self):
        return self.do_invalid_test('changes', dict(changeid=1,
                                                    author="a",
                                                    branch="a",
                                                    revision="a" * 256,
                                                    category="a"),
                                    "\n".join(["",
                                               "- 'changes' table has invalid data:",
                                               "    changes.change=1 has author, branch, revision or category longer than 255"]))

    def test_invalid_category_in_changes(self):
        return self.do_invalid_test('changes', dict(changeid=1,
                                                    author="a",
                                                    branch="a",
                                                    revision="a",
                                                    category="a" * 256),
                                    "\n".join(["",
                                               "- 'changes' table has invalid data:",
                                               "    changes.change=1 has author, branch, revision or category longer than 255"]))

    def test_invalid_name_in_object_state(self):
        return self.do_invalid_test('object_state', dict(objectid=1,
                                                         name="a" * 256),
                                    "\n".join(["",
                                               "- 'object_state' table has invalid data:",
                                               "    object_state.objectid=1 has name longer than 255"]))

    def test_invalid_identifier_in_users(self):
        return self.do_invalid_test('users', dict(uid=1,
                                                  identifier="a" * 256),
                                    "\n".join(["",
                                               "- 'users_state' table has invalid data:",
                                               "    users.uid=1 has identifier longer than 255"]))

    @defer.inlineCallbacks
    def test_multiple_invalid_values(self):

        def setup_thd(conn):
            self.create_tables_thd(conn)
            metadata = sa.MetaData()
            metadata.bind = conn
            conn.execute(self.users.insert(), [dict(uid=1,
                                                    identifier="a" * 256)])
            conn.execute(self.changes.insert(), [dict(changeid=1,
                                                      author="a",
                                                      branch="a",
                                                      revision="a",
                                                      category="a" * 256),
                                                 dict(changeid=2,
                                                      author="a" * 256,
                                                      branch="a",
                                                      revision="a",
                                                      category="a")])
        yield self.assertExpectedMessage(self.do_test_migration(45, 46, setup_thd, None),
                                         "\n".join(["",
                                                    "- 'changes' table has invalid data:",
                                                    "    changes.change=1 has author, branch, revision or category longer than 255",
                                                    "    changes.change=2 has author, branch, revision or category longer than 255",
                                                    "- 'users_state' table has invalid data:",
                                                    "    users.uid=1 has identifier longer than 255"]))
