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

import locale
import os
import pprint
import sqlite3
import tarfile

import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.exc import DatabaseError
from twisted.internet import defer
from twisted.python import util
from twisted.trial import unittest

from buildbot.db.model import UpgradeFromBefore0p9Error
from buildbot.db.model import UpgradeFromBefore3p0Error
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import querylog


class UpgradeTestMixin(TestReactorMixin):
    """Supporting code to test upgrading from older versions by untarring a
    basedir tarball and then checking that the results are as expected."""

    # class variables to set in subclasses

    # filename of the tarball (sibling to this file)
    source_tarball: None | str = None

    # these tests take a long time on platforms where sqlite is slow
    # (e.g., lion, see #2256)
    timeout = 1200

    @defer.inlineCallbacks
    def setUpUpgradeTest(self):
        self.basedir = None

        if self.source_tarball:
            tarball = util.sibpath(__file__, self.source_tarball)
            if not os.path.exists(tarball):
                raise unittest.SkipTest(
                    f"'{tarball}' not found (normal when not building from Git)"
                )

            with tarfile.open(tarball) as tf:
                prefixes = set()
                for inf in tf:
                    if hasattr(tarfile, 'data_filter'):
                        tf.extract(inf, filter='data')
                    else:
                        tf.extract(inf)
                    prefixes.add(inf.name.split('/', 1)[0])

            # get the top-level dir from the tarball
            assert len(prefixes) == 1, "tarball has multiple top-level dirs!"
            self.basedir = prefixes.pop()
            db_url = 'sqlite:///' + os.path.abspath(os.path.join(self.basedir, 'state.sqlite'))
        else:
            if not os.path.exists("basedir"):
                os.makedirs("basedir")
            self.basedir = os.path.abspath("basedir")
            db_url = None

        self.master = yield fakemaster.make_master(
            self,
            basedir=self.basedir,
            wantDb=True,
            db_url=db_url,
            sqlite_memory=False,
            auto_upgrade=False,
            check_version=False,
            auto_clean=False if self.source_tarball else True,
        )

        self._sql_log_handler = querylog.start_log_queries()
        self.addCleanup(lambda: querylog.stop_log_queries(self._sql_log_handler))

    # save subclasses the trouble of calling our setUp and tearDown methods

    def setUp(self):
        self.setup_test_reactor()
        return self.setUpUpgradeTest()

    @defer.inlineCallbacks
    def assertModelMatches(self):
        def comp(engine):
            # use compare_model_to_db, which gets everything but indexes
            with engine.connect() as conn:
                opts = None
                if engine.dialect.name == 'mysql':
                    # Disable type comparisons for mysql. Since 1.12.0 it is enabled by default.
                    # https://alembic.sqlalchemy.org/en/latest/changelog.html#change-1.12.0
                    # There is issue with comparison MEDIUMBLOB() vs LargeBinary(length=65536) in logchunks table.
                    opts = {"compare_type": False}
                diff = compare_metadata(
                    MigrationContext.configure(conn, opts=opts), self.master.db.model.metadata
                )

            if engine.dialect.name == 'mysql':
                # MySQL/MyISAM does not support foreign keys, which is expected.
                diff = [d for d in diff if d[0] != 'add_fk']

            if diff:
                return diff

            # check indexes manually
            insp = sa.inspect(engine)
            # unique, name, column_names
            diff = []
            for tbl in self.master.db.model.metadata.sorted_tables:
                exp = sorted(
                    [
                        {
                            "name": idx.name,
                            "unique": (idx.unique and 1) or 0,
                            "column_names": sorted([c.name for c in idx.columns]),
                        }
                        for idx in tbl.indexes
                    ],
                    key=lambda x: x['name'],
                )

                # include implied indexes on postgres and mysql
                if engine.dialect.name == 'mysql':
                    implied = [
                        idx
                        for (tname, idx) in self.master.db.model.implied_indexes
                        if tname == tbl.name
                    ]
                    exp = sorted(exp + implied, key=lambda k: k["name"])

                got = sorted(insp.get_indexes(tbl.name), key=lambda x: x['name'])
                if exp != got:
                    got_names = {idx['name'] for idx in got}
                    exp_names = {idx['name'] for idx in exp}
                    got_info = dict((idx['name'], idx) for idx in got)
                    exp_info = dict((idx['name'], idx) for idx in exp)
                    for name in got_names - exp_names:
                        diff.append(
                            f"got unexpected index {name} on table {tbl.name}: {got_info[name]!r}"
                        )
                    for name in exp_names - got_names:
                        diff.append(f"missing index {name} on table {tbl.name}")
                    for name in got_names & exp_names:
                        gi = {
                            "name": name,
                            "unique": (got_info[name]['unique'] and 1) or 0,
                            "column_names": sorted(got_info[name]['column_names']),
                        }
                        ei = exp_info[name]
                        if gi != ei:
                            diff.append(
                                f"index {name} on table {tbl.name} differs: got {gi}; exp {ei}"
                            )
            if diff:
                return "\n".join(diff)
            return None

        try:
            diff = yield self.master.db.pool.do_with_engine(comp)
        except TypeError as e:
            # older sqlites cause failures in reflection, which manifest as a
            # TypeError.  Reflection is only used for tests, so we can just skip
            # this test on such platforms.  We still get the advantage of trying
            # the upgrade, at any rate.
            raise unittest.SkipTest(
                "model comparison skipped: bugs in schema reflection on this sqlite version"
            ) from e

        if diff:
            self.fail("\n" + pprint.pformat(diff))

    def gotError(self, e):
        if isinstance(e, (sqlite3.DatabaseError, DatabaseError)):
            if "file is encrypted or is not a database" in str(e):
                self.flushLoggedErrors(sqlite3.DatabaseError)
                self.flushLoggedErrors(DatabaseError)
                raise unittest.SkipTest(f"sqlite dump not readable on this machine {e!s}")

    @defer.inlineCallbacks
    def do_test_upgrade(self, pre_callbacks=None):
        if pre_callbacks is None:
            pre_callbacks = []

        yield from pre_callbacks

        try:
            yield self.master.db.model.upgrade()
        except Exception as e:
            self.gotError(e)

        yield self.master.db.pool.do(self.verify_thd)
        yield self.assertModelMatches()


class UpgradeTestEmpty(UpgradeTestMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def test_emptydb_modelmatches(self):
        os_encoding = locale.getpreferredencoding()
        try:
            '\N{SNOWMAN}'.encode(os_encoding)
        except UnicodeEncodeError as e:
            # Default encoding of Windows console is 'cp1252'
            # which cannot encode the snowman.
            raise unittest.SkipTest(
                f"Cannot encode weird unicode on this platform with {os_encoding}"
            ) from e

        yield self.master.db.model.upgrade()
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

        self.master.db.model.upgrade = upgrade
        with self.assertRaises(unittest.SkipTest):
            yield self.do_test_upgrade()

    @defer.inlineCallbacks
    def test_got_invalid_sqlite_file2(self):
        def upgrade():
            return defer.fail(DatabaseError('file is encrypted or is not a database', None, None))

        self.master.db.model.upgrade = upgrade
        with self.assertRaises(unittest.SkipTest):
            yield self.do_test_upgrade()


class UpgradeTestV090b4(UpgradeTestMixin, unittest.TestCase):
    source_tarball = "v090b4.tgz"

    def gotError(self, e):
        self.flushLoggedErrors(UpgradeFromBefore3p0Error)

    def test_upgrade(self):
        return self.do_test_upgrade()

    def verify_thd(self, conn):
        r = conn.execute(sa.text("select version from migrate_version limit 1"))
        version = r.scalar()
        self.assertEqual(version, 44)

    def assertModelMatches(self):
        pass


class UpgradeTestV087p1(UpgradeTestMixin, unittest.TestCase):
    source_tarball = "v087p1.tgz"

    def gotError(self, e):
        self.flushLoggedErrors(UpgradeFromBefore0p9Error)

    def verify_thd(self, conn):
        r = conn.execute(sa.text("select version from migrate_version limit 1"))
        version = r.scalar()
        self.assertEqual(version, 22)

    def assertModelMatches(self):
        pass

    def test_upgrade(self):
        return self.do_test_upgrade()
