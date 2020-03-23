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


import os

import migrate
import migrate.versioning.api
import sqlalchemy as sa

from twisted.internet import defer
from twisted.python import log

from buildbot.db import connector
from buildbot.test.fake import fakemaster
from buildbot.test.util import db
from buildbot.test.util import dirs
from buildbot.test.util import querylog
from buildbot.test.util.misc import TestReactorMixin
from buildbot.util import sautils

# test_upgrade vs. migration tests
#
# test_upgrade is an integration test -- it tests the whole upgrade process,
# including the code in model.py.  Migrate tests are unit tests, and test a
# single db upgrade script.


class MigrateTestMixin(TestReactorMixin, db.RealDatabaseMixin, dirs.DirsMixin):

    @defer.inlineCallbacks
    def setUpMigrateTest(self):
        self.setUpTestReactor()
        self.basedir = os.path.abspath("basedir")
        self.setUpDirs('basedir')

        yield self.setUpRealDatabase()

        master = fakemaster.make_master(self)
        self.db = connector.DBConnector(self.basedir)
        yield self.db.setServiceParent(master)
        self.db.pool = self.db_pool

    def tearDownMigrateTest(self):
        self.tearDownDirs()
        return self.tearDownRealDatabase()

    @defer.inlineCallbacks
    def do_test_migration(self, base_version, target_version,
                          setup_thd_cb, verify_thd_cb):

        def setup_thd(conn):
            metadata = sa.MetaData()
            table = sautils.Table(
                'migrate_version', metadata,
                sa.Column('repository_id', sa.String(250), primary_key=True),
                sa.Column('repository_path', sa.Text),
                sa.Column('version', sa.Integer),
            )
            table.create(bind=conn)
            conn.execute(table.insert(),
                         repository_id='Buildbot',
                         repository_path=self.db.model.repo_path,
                         version=base_version)
            setup_thd_cb(conn)
        yield self.db.pool.do(setup_thd)

        def upgrade_thd(engine):
            with querylog.log_queries():
                schema = migrate.versioning.schema.ControlledSchema(
                    engine, self.db.model.repo_path)
                changeset = schema.changeset(target_version)
                with sautils.withoutSqliteForeignKeys(engine):
                    for version, change in changeset:
                        log.msg('upgrading to schema version %d' %
                                (version + 1))
                        schema.runchange(version, change, 1)
        yield self.db.pool.do_with_engine(upgrade_thd)

        def check_table_charsets_thd(engine):
            # charsets are only a problem for MySQL
            if engine.dialect.name != 'mysql':
                return
            dbs = [r[0] for r in engine.execute("show tables")]
            for tbl in dbs:
                r = engine.execute("show create table {}".format(tbl))
                create_table = r.fetchone()[1]
                self.assertIn('DEFAULT CHARSET=utf8', create_table,
                              "table {} does not have the utf8 charset".format(tbl))
        yield self.db.pool.do(check_table_charsets_thd)

        def verify_thd(engine):
            with sautils.withoutSqliteForeignKeys(engine):
                verify_thd_cb(engine)

        yield self.db.pool.do(verify_thd)
