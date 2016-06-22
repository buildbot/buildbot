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
import shutil
import tarfile

import migrate
import migrate.versioning.api
import sqlalchemy as sa
from sqlalchemy.engine import reflection
from twisted.internet import defer
from twisted.python import util
from twisted.trial import unittest

from buildbot.db import connector
from buildbot.test.fake import fakemaster
from buildbot.test.util import db
from buildbot.test.util import querylog
from buildbot.util import pickle


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
                    for idx in tbl.indexes])

                # include implied indexes on postgres and mysql
                if engine.dialect.name == 'mysql':
                    implied = [idx for (tname, idx)
                               in self.db.model.implied_indexes
                               if tname == tbl.name]
                    exp = sorted(exp + implied)

                got = sorted(insp.get_indexes(tbl.name))
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

    def do_test_upgrade(self, pre_callbacks=[]):
        d = defer.succeed(None)
        for cb in pre_callbacks:
            d.addCallback(cb)
        d.addCallback(lambda _: self.db.model.upgrade())
        d.addCallback(lambda _: self.db.pool.do(self.verify_thd))
        d.addCallback(lambda _: self.assertModelMatches())
        return d


class UpgradeTestEmpty(UpgradeTestMixin, unittest.TestCase):

    use_real_db = True

    def test_emptydb_modelmatches(self):
        d = self.db.model.upgrade()
        d.addCallback(lambda r: self.assertModelMatches())
        return d


class UpgradeTestV082(UpgradeTestMixin, unittest.TestCase):

    source_tarball = "v082.tgz"

    def verify_thd(self, conn):
        "partially verify the contents of the db - run in a thread"
        model = self.db.model

        tbl = model.buildrequests
        r = conn.execute(tbl.select(order_by=tbl.c.id))
        buildreqs = [(br.id, br.buildsetid,
                      br.complete, br.results)
                     for br in r.fetchall()]
        self.assertEqual(buildreqs, [
            (1, 1, 1, 0),
            (2, 2, 1, 4),
            (3, 3, 1, 4),
            (4, 4, 1, 4),
            (5, 5, 1, 0),
            (6, 6, 1, 0),
            (7, 7, 1, 0),
        ])

        br_claims = model.buildrequest_claims
        masters = model.masters
        r = conn.execute(sa.select([br_claims.outerjoin(masters,
                                                        br_claims.c.masterid == masters.c.id)]))
        # the int() is required here because sqlalchemy stores floats in an
        # INTEGER column(!)
        buildreqs = [(brc.brid, int(brc.claimed_at), brc.name)
                     for brc in r.fetchall()]
        objname = 'euclid:/home/dustin/code/buildbot/t/buildbot/sand27/master'
        self.assertEqual(buildreqs, [
            (1, 1310337746, objname),
            (2, 1310337757, objname),
            (3, 1310337757, objname),
            (4, 1310337757, objname),
            (5, 1310337779, objname),
            (6, 1310337779, objname),
            (7, 1310337779, objname),
        ])

        # There's just one, boring sourcetamp
        r = conn.execute(sa.select([model.sourcestamps]))
        rows = [dict(row) for row in r.fetchall()]
        for row in rows:
            del row['created_at']  # it will be near the current time
        self.assertEqual(rows, [
            {u'branch': None, u'codebase': u'', u'id': 1,
             u'patchid': None, u'project': u'', u'repository': u'',
             u'revision': None,
             'ss_hash': '835fccf6db3694afb48c380997024542c0bc162d'},
        ])

        # ..and all of the buildsets use it.
        bs = model.buildsets
        bss = model.buildset_sourcestamps
        r = conn.execute(
            sa.select([bs.c.id, bss.c.sourcestampid],
                      whereclause=bs.c.id == bss.c.buildsetid))
        rows = map(dict, r.fetchall())
        self.assertEqual([row['sourcestampid'] for row in rows],
                         [1] * 7)

    def test_upgrade(self):
        d = self.do_test_upgrade()

        @d.addCallback
        def check_pickles(_):
            # try to unpickle things down to the level of a logfile
            filename = os.path.join(self.basedir, 'builder', 'builder')
            with open(filename, "rb") as f:
                builder_status = pickle.load(f)
            builder_status.master = self.master
            builder_status.basedir = os.path.join(self.basedir, 'builder')
            b0 = builder_status.loadBuildFromFile(0)
            logs = b0.getLogs()
            log = logs[0]
            text = log.old_getText()
            self.assertIn('HEAD is now at', text)
        return d


class UpgradeTestV083(UpgradeTestMixin, unittest.TestCase):

    source_tarball = "v083.tgz"

    def verify_thd(self, conn):
        "partially verify the contents of the db - run in a thread"
        model = self.db.model

        tbl = model.buildrequests
        r = conn.execute(tbl.select(order_by=tbl.c.id))
        buildreqs = [(br.id, br.buildsetid,
                      br.complete, br.results)
                     for br in r.fetchall()]
        self.assertEqual(buildreqs, [
            (1, 1, 1, 0),
            (2, 2, 1, 0),
            (3, 3, 1, 0),
            (4, 4, 1, 0),
            (5, 5, 1, 0),
            (6, 6, 1, 0),
            (7, 7, 1, 0),
            (8, 8, 1, 0),
            (9, 9, 1, 0),
            (10, 10, 1, 0),
            (11, 11, 1, 4),
            (12, 12, 1, 0),
            (13, 13, 1, 0),
            (14, 14, 1, 0),
        ])

        br_claims = model.buildrequest_claims
        masters = model.masters
        r = conn.execute(sa.select([br_claims.outerjoin(masters,
                                                        br_claims.c.masterid == masters.c.id)]))
        # the int() is required here because sqlalchemy stores floats in an
        # INTEGER column(!)
        buildreqs = [(brc.brid, int(brc.claimed_at), brc.name)
                     for brc in r.fetchall()]
        objname = 'euclid:/home/dustin/code/buildbot/t/buildbot/sand27/master'
        self.assertEqual(buildreqs, [
            (1, 1310326850, objname),
            (2, 1310326862, objname),
            (3, 1310326872, objname),
            (4, 1310326872, objname),
            (5, 1310326872, objname),
            (6, 1310326872, objname),
            (7, 1310326872, objname),
            (8, 1310326872, objname),
            (9, 1310326872, objname),
            (10, 1310326872, objname),
            (11, 1310326895, objname),
            (12, 1310326900, objname),
            (13, 1310326900, objname),
            (14, 1310326900, objname),
        ])

    def test_upgrade(self):
        return self.do_test_upgrade()


class UpgradeTestV084(UpgradeTestMixin, unittest.TestCase):

    source_tarball = "v084.tgz"

    def verify_thd(self, conn):
        "partially verify the contents of the db - run in a thread"
        model = self.db.model

        tbl = model.buildrequests
        r = conn.execute(tbl.select(order_by=tbl.c.id))
        buildreqs = [(br.id, br.buildsetid,
                      br.complete, br.results)
                     for br in r.fetchall()]
        self.assertEqual(buildreqs, [
            (1, 1, 0, -1),
            (2, 2, 0, -1),
            (3, 3, 0, -1),
            (4, 4, 0, -1),
            (5, 5, 0, -1),
            (6, 6, 0, -1),
            (7, 7, 0, -1),
        ])

        br_claims = model.buildrequest_claims
        masters = model.masters
        r = conn.execute(sa.select([br_claims.outerjoin(masters,
                                                        br_claims.c.masterid == masters.c.id)]))
        # the int() is required here because sqlalchemy stores floats in an
        # INTEGER column(!)
        buildreqs = [(brc.brid, int(brc.claimed_at), brc.name)
                     for brc in r.fetchall()]
        objname = 'euclid:/home/dustin/code/buildbot/t/buildbot/sand27/master'
        self.assertEqual(buildreqs, [
            (1, 1310406744, objname),
            (2, 1310406863, objname),
            (3, 1310406863, objname),
            (4, 1310406863, objname),
            (5, 1310406863, objname),
            # 6, 7 aren't claimed yet
        ])

    def test_upgrade(self):
        return self.do_test_upgrade()


class UpgradeTestV085(UpgradeTestMixin, unittest.TestCase):

    source_tarball = "v085.tgz"

    def verify_thd(self, conn):
        "partially verify the contents of the db - run in a thread"
        model = self.db.model

        tbl = model.buildrequests
        r = conn.execute(tbl.select(order_by=tbl.c.id))
        buildreqs = [(br.id, br.buildsetid,
                      br.complete, br.results)
                     for br in r.fetchall()]
        self.assertEqual(buildreqs, [(1, 1, 1, 0), (2, 2, 1, 0)])

        br_claims = model.buildrequest_claims
        masters = model.masters
        r = conn.execute(sa.select([br_claims.outerjoin(masters,
                                                        br_claims.c.masterid == masters.c.id)]))
        buildreqs = [(brc.brid, int(brc.claimed_at), brc.name)
                     for brc in r.fetchall()]
        self.assertEqual(buildreqs, [
            (1, 1338226540, u'euclid.r.igoro.us:/A/bbrun'),
            (2, 1338226574, u'euclid.r.igoro.us:/A/bbrun'),
        ])

    def test_upgrade(self):
        d = self.do_test_upgrade()

        @d.addCallback
        def check_pickles(_):
            # try to unpickle things down to the level of a logfile
            filename = os.path.join(self.basedir, 'builder', 'builder')
            with open(filename, "rb") as f:
                builder_status = pickle.load(f)
            builder_status.master = self.master
            builder_status.basedir = os.path.join(self.basedir, 'builder')
            b1 = builder_status.loadBuildFromFile(1)
            logs = b1.getLogs()
            log = logs[0]
            text = log.old_getText()
            self.assertIn('HEAD is now at', text)
            b2 = builder_status.loadBuildFromFile(1)
            self.assertEqual(b2.getReason(),
                             "The web-page 'rebuild' button was pressed by '<unknown>': \n")
        return d


class UpgradeTestV086p1(UpgradeTestMixin, unittest.TestCase):

    source_tarball = "v086p1.tgz"

    def verify_thd(self, conn):
        "partially verify the contents of the db - run in a thread"
        model = self.db.model

        tbl = model.buildrequests
        r = conn.execute(tbl.select(order_by=tbl.c.id))
        buildreqs = [(br.id, br.buildsetid,
                      br.complete, br.results)
                     for br in r.fetchall()]
        self.assertEqual(buildreqs, [(1, 1, 1, 4)])  # note EXCEPTION status

        br_claims = model.buildrequest_claims
        masters = model.masters
        r = conn.execute(sa.select([br_claims.outerjoin(masters,
                                                        br_claims.c.masterid == masters.c.id)]))
        buildreqs = [(brc.brid, int(brc.claimed_at), brc.name)
                     for brc in r.fetchall()]
        self.assertEqual(buildreqs, [
            (1, 1338229046, u'euclid.r.igoro.us:/A/bbrun'),
        ])

    def test_upgrade(self):
        d = self.do_test_upgrade()

        @d.addCallback
        def check_pickles(_):
            # try to unpickle things down to the level of a logfile
            filename = os.path.join(self.basedir, 'builder', 'builder')
            with open(filename, "rb") as f:
                builder_status = pickle.load(f)
            builder_status.master = self.master
            builder_status.basedir = os.path.join(self.basedir, 'builder')
            b0 = builder_status.loadBuildFromFile(0)
            logs = b0.getLogs()
            log = logs[0]
            text = log.old_getText()
            self.assertIn('HEAD is now at', text)
        return d


class UpgradeTestV087p1(UpgradeTestMixin, unittest.TestCase):

    source_tarball = "v087p1.tgz"

    def verify_thd(self, conn):
        "partially verify the contents of the db - run in a thread"
        model = self.db.model

        tbl = model.buildrequests
        r = conn.execute(tbl.select(order_by=tbl.c.id))
        buildreqs = [(br.id, br.buildsetid,
                      br.complete, br.results)
                     for br in r.fetchall()]
        # two successful builds
        self.assertEqual(buildreqs, [(1, 1, 1, 0), (2, 2, 1, 0)])

        br_claims = model.buildrequest_claims
        masters = model.masters
        r = conn.execute(sa.select([br_claims.outerjoin(masters,
                                                        br_claims.c.masterid == masters.c.id)]))
        buildreqs = [(brc.brid, int(brc.claimed_at), brc.name)
                     for brc in r.fetchall()]
        self.assertEqual(buildreqs, [
            (1, 1363642117,
             u'Eriks-MacBook-Air.local:/Users/erik/buildbot-work/master'),
            (2, 1363642156,
             u'Eriks-MacBook-Air.local:/Users/erik/buildbot-work/master'),
        ])

    def test_upgrade(self):
        # we no longer need a builder pickle since the builder can be
        # re-created without one
        return self.do_test_upgrade()
