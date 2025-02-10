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

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from twisted.internet import defer
from twisted.python import log

from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import dirs
from buildbot.test.util import querylog
from buildbot.util import sautils

if TYPE_CHECKING:
    from sqlalchemy.future.engine import Connection


# test_upgrade vs. migration tests
#
# test_upgrade is an integration test -- it tests the whole upgrade process,
# including the code in model.py.  Migrate tests are unit tests, and test a
# single db upgrade script.


class MigrateTestMixin(TestReactorMixin, dirs.DirsMixin):
    @defer.inlineCallbacks
    def setUpMigrateTest(self):
        self.setup_test_reactor()
        self.basedir = os.path.abspath("basedir")
        self.setUpDirs('basedir')

        self.master = yield fakemaster.make_master(
            self, wantDb=True, auto_upgrade=False, check_version=False
        )

    @defer.inlineCallbacks
    def do_test_migration(self, base_revision, target_revision, setup_thd_cb, verify_thd_cb):
        def setup_thd(conn):
            metadata = sa.MetaData()
            table = sautils.Table(
                'alembic_version',
                metadata,
                sa.Column("version_num", sa.String(32), nullable=False),
            )
            table.create(bind=conn)
            conn.execute(table.insert().values(version_num=base_revision))
            conn.commit()
            setup_thd_cb(conn)

        yield self.master.db.pool.do(setup_thd)

        alembic_scripts = self.master.db.model.alembic_get_scripts()

        def upgrade_thd(engine):
            with querylog.log_queries():
                with engine.connect() as conn:
                    with sautils.withoutSqliteForeignKeys(conn):

                        def upgrade(rev, context):
                            log.msg(f'Upgrading from {rev} to {target_revision}')
                            return alembic_scripts._upgrade_revs(target_revision, rev)

                        context = MigrationContext.configure(conn, opts={'fn': upgrade})

                        with Operations.context(context):
                            with context.begin_transaction():
                                context.run_migrations()

                        conn.commit()

        yield self.master.db.pool.do_with_engine(upgrade_thd)

        def check_table_charsets_thd(conn: Connection):
            # charsets are only a problem for MySQL
            if conn.dialect.name != 'mysql':
                return

            dbs = [r[0] for r in conn.exec_driver_sql("show tables")]
            for tbl in dbs:
                r = conn.exec_driver_sql(f"show create table {tbl}")
                assert r is not None
                res = r.fetchone()
                assert res is not None
                create_table = res[1]
                self.assertIn(  # type: ignore[attr-defined]
                    'DEFAULT CHARSET=utf8',
                    create_table,
                    f"table {tbl} does not have the utf8 charset",
                )

        yield self.master.db.pool.do(check_table_charsets_thd)

        def verify_thd(conn):
            with sautils.withoutSqliteForeignKeys(conn):
                verify_thd_cb(conn)

        yield self.master.db.pool.do(verify_thd)
