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

    def test_migration(self):
        def setup_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            sautils.Table(
                'builds', metadata,
                sa.Column('id', sa.Integer, primary_key=True),
                # ...
            ).create()

            sautils.Table(
                'builders', metadata,
                sa.Column('id', sa.Integer, primary_key=True),
                # ...
            ).create()

            sautils.Table(
                'steps', metadata,
                sa.Column('id', sa.Integer, primary_key=True),
                # ...
            ).create()

        def verify_thd(conn):
            metadata = sa.MetaData()
            metadata.bind = conn

            test_result_sets = sautils.Table('test_result_sets', metadata, autoload=True)

            q = sa.select([
                test_result_sets.c.builderid,
                test_result_sets.c.buildid,
                test_result_sets.c.stepid,
                test_result_sets.c.description,
                test_result_sets.c.category,
                test_result_sets.c.value_unit,
                test_result_sets.c.tests_passed,
                test_result_sets.c.tests_failed,
                test_result_sets.c.complete,
            ])
            self.assertEqual(conn.execute(q).fetchall(), [])

            test_results = sautils.Table('test_results', metadata, autoload=True)

            q = sa.select([
                test_results.c.builderid,
                test_results.c.test_result_setid,
                test_results.c.test_nameid,
                test_results.c.test_code_pathid,
                test_results.c.line,
                test_results.c.duration_ns,
                test_results.c.value,
            ])
            self.assertEqual(conn.execute(q).fetchall(), [])

            test_names = sautils.Table('test_names', metadata, autoload=True)

            q = sa.select([
                test_names.c.builderid,
                test_names.c.name,
            ])
            self.assertEqual(conn.execute(q).fetchall(), [])

            test_code_paths = sautils.Table('test_code_paths', metadata, autoload=True)

            q = sa.select([
                test_code_paths.c.builderid,
                test_code_paths.c.path,
            ])
            self.assertEqual(conn.execute(q).fetchall(), [])

            insp = sa.inspect(conn)

            indexes = insp.get_indexes('test_names')
            index_names = [item['name'] for item in indexes]
            self.assertTrue('test_names_name' in index_names)

            indexes = insp.get_indexes('test_code_paths')
            index_names = [item['name'] for item in indexes]
            self.assertTrue('test_code_paths_path' in index_names)

        return self.do_test_migration(55, 56, setup_thd, verify_thd)
