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

import locale
import os
import shutil
import sqlite3
import tarfile

import migrate
import migrate.versioning.api
from sqlalchemy.engine import reflection
from sqlalchemy.exc import DatabaseError

from twisted.internet import defer
from twisted.python import util
from twisted.trial import unittest

from buildbot.db import connector
from buildbot.db.model import EightUpgradeError
from buildbot.test.fake import fakemaster
from buildbot.test.util import db
from buildbot.test.util import querylog


class UpgradeTestMixin(db.RealDatabaseMixin):

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
                    "'%s' not found (normal when not building from Git)"
                    % tarball)

            tf = tarfile.open(tarball)
            prefixes = set()
            for inf in tf:
                tf.extract(inf)
                prefixes.add(inf.name.split('/', 1)[0])
            tf.close()
            # (note that tf.extractall isn't available in py2.4)

            # get the top-level dir from the tarball
            assert len(prefixes) == 1, "tarball has multiple top-level dirs!"
            self.basedir = prefixes.pop()
        else:
            if not os.path.exists("basedir"):
                os.makedirs("basedir")
            self.basedir = os.path.abspath("basedir")

        self.master = master = fakemaster.make_master()
        master.config.db['db_url'] = self.db_url
        self.db = connector.DBConnector(self.basedir)
        self.db.setServiceParent(master)
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
        return self.setUpUpgradeTest()

    def tearDown(self):
        return self.tearDownUpgradeTest()

    def assertModelMatches(self):
        def comp(engine):
            # use compare_model_to_db, which gets everything but foreign
            # keys and indexes
            diff = migrate.versioning.api.compare_model_to_db(
                engine,
                self.db.model.repo_path,
                self.db.model.metadata)
            if diff:
                return diff

            # check indexes manually
            insp = reflection.Inspector.from_engine(engine)
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
                    exp = sorted(exp + implied)

                got = sorted(insp.get_indexes(tbl.name),
                             key=lambda x: x['name'])
                if exp != got:
                    got_names = set([idx['name'] for idx in got])
                    exp_names = set([idx['name'] for idx in exp])
                    got_info = dict((idx['name'], idx) for idx in got)
                    exp_info = dict((idx['name'], idx) for idx in exp)
                    for name in got_names - exp_names:
                        diff.append("got unexpected index %s on table %s: %r"
                                    % (name, tbl.name, got_info[name]))
                    for name in exp_names - got_names:
                        diff.append("missing index %s on table %s"
                                    % (name, tbl.name))
                    for name in got_names & exp_names:
                        gi = dict(name=name,
                                  unique=got_info[name]['unique'] and 1 or 0,
                                  column_names=sorted(got_info[name]['column_names']))
                        ei = exp_info[name]
                        if gi != ei:
                            diff.append(
                                "index %s on table %s differs: got %s; exp %s"
                                % (name, tbl.name, gi, ei))
            if diff:
                return "\n".join(diff)

        d = self.db.pool.do_with_engine(comp)

        # older sqlites cause failures in reflection, which manifest as a
        # TypeError.  Reflection is only used for tests, so we can just skip
        # this test on such platforms.  We still get the advantage of trying
        # the upgrade, at any rate.
        @d.addErrback
        def catch_TypeError(f):
            f.trap(TypeError)
            raise unittest.SkipTest("model comparison skipped: bugs in schema "
                                    "reflection on this sqlite version")

        @d.addCallback
        def check(diff):
            if diff:
                self.fail("\n" + str(diff))
        return d

    def gotError(self, e):
        e.trap(sqlite3.DatabaseError, DatabaseError)
        if "file is encrypted or is not a database" in str(e):
            self.flushLoggedErrors(sqlite3.DatabaseError)
            self.flushLoggedErrors(DatabaseError)
            raise unittest.SkipTest(
                "sqlite dump not readable on this machine %s"
                % str(e))
        return e

    def do_test_upgrade(self, pre_callbacks=[]):
        d = defer.succeed(None)
        for cb in pre_callbacks:
            d.addCallback(cb)
        d.addCallback(lambda _: self.db.model.upgrade())
        d.addErrback(self.gotError)
        d.addCallback(lambda _: self.db.pool.do(self.verify_thd))
        d.addCallback(lambda _: self.assertModelMatches())
        return d


class UpgradeTestEmpty(UpgradeTestMixin, unittest.TestCase):

    use_real_db = True

    def test_emptydb_modelmatches(self):
        os_encoding = locale.getpreferredencoding()
        try:
            u'\N{SNOWMAN}'.encode(os_encoding)
        except UnicodeEncodeError:
            # Default encoding of Windows console is 'cp1252'
            # which cannot encode the snowman.
            raise(unittest.SkipTest("Cannot encode weird unicode "
                "on this platform with {}".format(os_encoding)))

        d = self.db.model.upgrade()
        d.addCallback(lambda r: self.assertModelMatches())
        return d


class UpgradeTestV090b4(UpgradeTestMixin, unittest.TestCase):

    source_tarball = "v090b4.tgz"

    def test_upgrade(self):
        return self.do_test_upgrade()

    def verify_thd(self, conn):
        pass

    def test_gotError(self):
        def upgrade():
            return defer.fail(sqlite3.DatabaseError('file is encrypted or is not a database'))
        self.db.model.upgrade = upgrade
        self.failureResultOf(self.do_test_upgrade(), unittest.SkipTest)

    def test_gotError2(self):
        def upgrade():
            return defer.fail(DatabaseError('file is encrypted or is not a database', None, None))
        self.db.model.upgrade = upgrade
        self.failureResultOf(self.do_test_upgrade(), unittest.SkipTest)


class UpgradeTestV087p1(UpgradeTestMixin, unittest.TestCase):

    source_tarball = "v087p1.tgz"

    def gotError(self, e):
        self.flushLoggedErrors(EightUpgradeError)

    def verify_thd(self, conn):
        "partially verify the contents of the db - run in a thread"
        r = conn.execute("select version from migrate_version limit 1")
        version = r.scalar()
        self.assertEqual(version, 22)

    def assertModelMatches(self):
        pass

    def test_upgrade(self):
        return self.do_test_upgrade()
