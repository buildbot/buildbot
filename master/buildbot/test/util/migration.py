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

import sqlalchemy as sa
from alembic.runtime.migration import MigrationContext

from twisted.internet import defer
from twisted.python import log

from buildbot.db import connector
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import db
from buildbot.test.util import dirs
from buildbot.test.util import querylog
from buildbot.util import sautils

# test_upgrade vs. migration tests
#
# test_upgrade is an integration test -- it tests the whole upgrade process,
# including the code in model.py.  Migrate tests are unit tests, and test a
# single db upgrade script.


class MigrateTestMixin(TestReactorMixin, db.RealDatabaseMixin, dirs.DirsMixin):

    @defer.inlineCallbacks
    def setUpMigrateTest(self):
        self.setup_test_reactor()
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
    def do_test_migration(self, base_revision, target_revision,
                          setup_thd_cb, verify_thd_cb):

        def setup_thd(conn):
            metadata = sa.MetaData()
            table = sautils.Table(
                'alembic_version', metadata,
                sa.Column("version_num", sa.String(32), nullable=False),
            )
            table.create(bind=conn)
            conn.execute(table.insert(), version_num=base_revision)
            setup_thd_cb(conn)
        yield self.db.pool.do(setup_thd)

        alembic_scripts = self.alembic_get_scripts()

        def upgrade_thd(engine):
            with querylog.log_queries():
                with sautils.withoutSqliteForeignKeys(engine):
                    with engine.connect() as conn:

                        def upgrade(rev, context):
                            log.msg(f'Upgrading from {rev} to {target_revision}')
                            return alembic_scripts._upgrade_revs(target_revision, rev)

                        context = MigrationContext.configure(conn, opts={'fn': upgrade})

                        with context.begin_transaction():
                            context.run_migrations()

        yield self.db.pool.do_with_engine(upgrade_thd)

        def check_table_charsets_thd(engine):
            # charsets are only a problem for MySQL
            if engine.dialect.name != 'mysql':
                return
            dbs = [r[0] for r in engine.execute("show tables")]
            for tbl in dbs:
                r = engine.execute(f"show create table {tbl}")
                create_table = r.fetchone()[1]
                self.assertIn('DEFAULT CHARSET=utf8', create_table,
                              f"table {tbl} does not have the utf8 charset")
        yield self.db.pool.do(check_table_charsets_thd)

        def verify_thd(engine):
            with sautils.withoutSqliteForeignKeys(engine):
                verify_thd_cb(engine)

        yield self.db.pool.do(verify_thd)
