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
from twisted.python import log
from twisted.internet import defer
import sqlalchemy as sa
import migrate
import migrate.versioning.api
from buildbot.db import connector
from buildbot.test.util import db, dirs, querylog
from buildbot.test.fake import fakemaster


# test_upgrade vs. migration tests
#
# test_upgrade is an integration test -- it tests the whole upgrade process,
# including the code in model.py.  Migrate tests are unit tests, and test a
# single db upgrade script.

class MigrateTestMixin(db.RealDatabaseMixin, dirs.DirsMixin):

    def setUpMigrateTest(self):
        self.basedir = os.path.abspath("basedir")
        self.setUpDirs('basedir')

        d = self.setUpRealDatabase()
        def make_dbc(_):
            master = fakemaster.make_master()
            self.db = connector.DBConnector(master, self.basedir)
            self.db.pool = self.db_pool
        d.addCallback(make_dbc)
        return d

    def tearDownMigrateTest(self):
        self.tearDownDirs()
        return self.tearDownRealDatabase()

    def do_test_migration(self, base_version, target_version,
                            setup_thd_cb, verify_thd_cb):
        d = defer.succeed(None)
        def setup_thd(conn):
            metadata = sa.MetaData()
            table = sa.Table('migrate_version', metadata,
                    sa.Column('repository_id', sa.String(250),
                                        primary_key=True),
                    sa.Column('repository_path', sa.Text),
                    sa.Column('version', sa.Integer))
            table.create(bind=conn)
            conn.execute(table.insert(),
                    repository_id='Buildbot',
                    repository_path=self.db.model.repo_path,
                    version=base_version)
            setup_thd_cb(conn)
        d.addCallback(lambda _ : self.db.pool.do(setup_thd))

        def upgrade_thd(engine):
            querylog.log_from_engine(engine)
            schema = migrate.versioning.schema.ControlledSchema(engine,
                                                    self.db.model.repo_path)
            changeset = schema.changeset(target_version)
            for version, change in changeset:
                log.msg('upgrading to schema version %d' % (version+1))
                schema.runchange(version, change, 1)
        d.addCallback(lambda _ : self.db.pool.do_with_engine(upgrade_thd))

        d.addCallback(lambda _ : self.db.pool.do(verify_thd_cb))
        return d
