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


import locale
import os
import pprint
import shutil
import sqlite3
import tarfile

import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.exc import DatabaseError

from twisted.internet import defer
from twisted.python import util
from twisted.trial import unittest

from buildbot.db import connector
from buildbot.db.model import UpgradeFromBefore0p9Error
from buildbot.db.model import UpgradeFromBefore3p0Error
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import db
from buildbot.test.util import querylog


class UpgradeTestMixin(db.RealDatabaseMixin, TestReactorMixin):

    """Supporting code to test upgrading from older versions by untarring a
    basedir tarball and then checking that the results are as expected."""

    # class variables to set in subclasses

    # filename of the tarball (sibling to this file)
    source_tarball = None

    # set to true in subclasses to set up and use a real DB
    use_real_db = False

    # db URL to use, if not using a real db
    db_url = "sqlite:///state.sqlite"

    # these tests take a long time on platforms where sqlite is slow
    # (e.g., lion, see #2256)
    timeout = 1200

    @defer.inlineCallbacks
    def setUpUpgradeTest(self):
        # set up the "real" db if desired
        if self.use_real_db:
            # note this changes self.db_url
            yield self.setUpRealDatabase(sqlite_memory=False)

        self.basedir = None

        if self.source_tarball:
            tarball = util.sibpath(__file__, self.source_tarball)
            if not os.path.exists(tarball):
                raise unittest.SkipTest(
                    f"'{tarball}' not found (normal when not building from Git)")

            with tarfile.open(tarball) as tf:
                prefixes = set()
                for inf in tf:
                    tf.extract(inf)
                    prefixes.add(inf.name.split('/', 1)[0])

            # (note that tf.extractall isn't available in py2.4)

            # get the top-level dir from the tarball
            assert len(prefixes) == 1, "tarball has multiple top-level dirs!"
            self.basedir = prefixes.pop()
        else:
            if not os.path.exists("basedir"):
                os.makedirs("basedir")
            self.basedir = os.path.abspath("basedir")

        self.master = master = fakemaster.make_master(self)
        master.config.db['db_url'] = self.db_url
        self.db = connector.DBConnector(self.basedir)
        yield self.db.setServiceParent(master)
        yield self.db.setup(check_version=False)

        self._sql_log_handler = querylog.start_log_queries()

    @defer.inlineCallbacks
    def tearDownUpgradeTest(self):
        querylog.stop_log_queries(self._sql_log_handler)

        if self.use_real_db:
            yield self.tearDownRealDatabase()

        if self.basedir:
            shutil.rmtree(self.basedir)

    # save subclasses the trouble of calling our setUp and tearDown methods

    def setUp(self):
        self.setup_test_reactor()
        return self.setUpUpgradeTest()

    def tearDown(self):
        return self.tearDownUpgradeTest()

    @defer.inlineCallbacks
    def assertModelMatches(self):
        def comp(engine):
            # use compare_model_to_db, which gets everything but indexes
            with engine.connect() as conn:
                diff = compare_metadata(MigrationContext.configure(conn), self.db.model.metadata)

            if engine.dialect.name == 'mysql':
                # MySQL/MyISAM does not support foreign keys, which is expected.
                diff = [d for d in diff if d[0] != 'add_fk']

            if diff:
                return diff

            # check indexes manually
            insp = sa.inspect(engine)
            # unique, name, column_names
            diff = []
            for tbl in self.db.model.metadata.sorted_tables:
                exp = sorted([
                    dict(name=idx.name,
                         unique=idx.unique and 1 or 0,
                         column_names=sorted([c.name for c in idx.columns]))
                    for idx in tbl.indexes], key=lambda x: x['name'])

                # include implied indexes on postgres and mysql
                if engine.dialect.name == 'mysql':
                    implied = [idx for (tname, idx)
                               in self.db.model.implied_indexes
                               if tname == tbl.name]
                    exp = sorted(exp + implied, key=lambda k: k["name"])

                got = sorted(insp.get_indexes(tbl.name),
                             key=lambda x: x['name'])
                if exp != got:
                    got_names = {idx['name'] for idx in got}
                    exp_names = {idx['name'] for idx in exp}
                    got_info = dict((idx['name'], idx) for idx in got)
                    exp_info = dict((idx['name'], idx) for idx in exp)
                    for name in got_names - exp_names:
                        diff.append(f"got unexpected index {name} on table {tbl.name}: "
                                    f"{repr(got_info[name])}")
                    for name in exp_names - got_names:
                        diff.append(f"missing index {name} on table {tbl.name}")
                    for name in got_names & exp_names:
                        gi = dict(name=name,
                                  unique=got_info[name]['unique'] and 1 or 0,
                                  column_names=sorted(got_info[name]['column_names']))
                        ei = exp_info[name]
                        if gi != ei:
                            diff.append(f"index {name} on table {tbl.name} differs: "
                                        f"got {gi}; exp {ei}")
            if diff:
                return "\n".join(diff)
            return None

        try:
            diff = yield self.db.pool.do_with_engine(comp)
        except TypeError as e:
            # older sqlites cause failures in reflection, which manifest as a
            # TypeError.  Reflection is only used for tests, so we can just skip
            # this test on such platforms.  We still get the advantage of trying
            # the upgrade, at any rate.
            raise unittest.SkipTest("model comparison skipped: bugs in schema "
                                    "reflection on this sqlite version") from e

        if diff:
            self.fail("\n" + pprint.pformat(diff))

    def gotError(self, e):
        if isinstance(e, (sqlite3.DatabaseError, DatabaseError)):
            if "file is encrypted or is not a database" in str(e):
                self.flushLoggedErrors(sqlite3.DatabaseError)
                self.flushLoggedErrors(DatabaseError)
                raise unittest.SkipTest(f"sqlite dump not readable on this machine {str(e)}")

    @defer.inlineCallbacks
    def do_test_upgrade(self, pre_callbacks=None):
        if pre_callbacks is None:
            pre_callbacks = []

        for cb in pre_callbacks:
            yield cb
        try:
            yield self.db.model.upgrade()
        except Exception as e:
            self.gotError(e)

        yield self.db.pool.do(self.verify_thd)
        yield self.assertModelMatches()


class UpgradeTestEmpty(UpgradeTestMixin, unittest.TestCase):

    use_real_db = True

    @defer.inlineCallbacks
    def test_emptydb_modelmatches(self):
        os_encoding = locale.getpreferredencoding()
        try:
            '\N{SNOWMAN}'.encode(os_encoding)
        except UnicodeEncodeError as e:
            # Default encoding of Windows console is 'cp1252'
            # which cannot encode the snowman.
            raise unittest.SkipTest("Cannot encode weird unicode "
                f"on this platform with {os_encoding}") from e

        yield self.db.model.upgrade()
        yield self.assertModelMatches()


class UpgradeTestV2_10_5(UpgradeTestMixin, unittest.TestCase):

    source_tarball = "v2.10.5.tgz"

    def test_upgrade(self):
        return self.do_test_upgrade()

    def verify_thd(self, conn):
        pass

    @defer.inlineCallbacks
    def test_got_invalid_sqlite_file(self):
        def upgrade():
            return defer.fail(sqlite3.DatabaseError('file is encrypted or is not a database'))
        self.db.model.upgrade = upgrade
        with self.assertRaises(unittest.SkipTest):
            yield self.do_test_upgrade()

    @defer.inlineCallbacks
    def test_got_invalid_sqlite_file2(self):
        def upgrade():
            return defer.fail(DatabaseError('file is encrypted or is not a database', None, None))
        self.db.model.upgrade = upgrade
        with self.assertRaises(unittest.SkipTest):
            yield self.do_test_upgrade()


class UpgradeTestV090b4(UpgradeTestMixin, unittest.TestCase):

    source_tarball = "v090b4.tgz"

    def gotError(self, e):
        self.flushLoggedErrors(UpgradeFromBefore3p0Error)

    def test_upgrade(self):
        return self.do_test_upgrade()

    def verify_thd(self, conn):
        r = conn.execute("select version from migrate_version limit 1")
        version = r.scalar()
        self.assertEqual(version, 44)

    def assertModelMatches(self):
        pass


class UpgradeTestV087p1(UpgradeTestMixin, unittest.TestCase):

    source_tarball = "v087p1.tgz"

    def gotError(self, e):
        self.flushLoggedErrors(UpgradeFromBefore0p9Error)

    def verify_thd(self, conn):
        r = conn.execute("select version from migrate_version limit 1")
        version = r.scalar()
        self.assertEqual(version, 22)

    def assertModelMatches(self):
        pass

    def test_upgrade(self):
        return self.do_test_upgrade()
