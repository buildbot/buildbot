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
import textwrap

import migrate
import migrate.versioning.api
import sqlalchemy as sa
from sqlalchemy.engine import reflection
from twisted.internet import defer
from twisted.persisted import styles
from twisted.python import util
from twisted.trial import unittest

from buildbot.db import connector
from buildbot.test.fake import fakemaster
from buildbot.test.util import change_import
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


class UpgradeTestV075(UpgradeTestMixin,
                      unittest.TestCase):

    source_tarball = "master-0-7-5.tgz"

    # this test can use a real DB because 0.7.5 was pre-DB, so there's no
    # expectation that the MySQL or Postgres DB will have anything in it.
    use_real_db = True

    def verify_thd(self, conn):
        "verify the contents of the db - run in a thread"
        # note that this will all change if we re-create the tarball!
        model = self.db.model

        r = conn.execute(
            sa.select([model.changes], order_by=model.changes.c.changeid))
        ch = r.fetchone()
        self.failUnlessEqual(ch.changeid, 1)
        self.failUnlessEqual(
            ch.author, u'the snowman <\N{SNOWMAN}@norpole.net>')
        self.failUnlessEqual(ch.comments, u'shooting star or \N{COMET}?')
        self.failUnlessEqual(ch.revision, u'\N{BLACK STAR}-devel')
        self.failUnlessEqual(ch.branch, u'\N{COMET}')
        ch = r.fetchone()
        self.failUnlessEqual(ch.changeid, 2)
        self.failUnlessEqual(ch.author, u"dustin <dustin@v.igoro.us>")
        self.failUnlessEqual(ch.comments, u'on-branch change')
        self.failUnlessEqual(ch.revision, u'1234')
        # arguably a bug - should be None?
        self.failUnlessEqual(ch.branch, u'')

        r = conn.execute(
            sa.select([model.change_files]))
        # use a set to avoid depending on db collation
        filenames = set([row.filename for row in r])
        expected = set([
            u'boring/path',
            u'normal/path',
            u'\N{BLACK STAR}/funny_chars/in/a/path',
        ])
        self.failUnlessEqual(filenames, expected)

        # check that the change table's primary-key sequence is correct by
        # trying to insert a new row.  This assumes that other sequences are
        # handled correctly, if this one is.
        r = conn.execute(model.changes.insert(),
                         dict(author='foo', comments='foo', is_dir=0,
                              when_timestamp=123, repository='', project=''))
        self.assertEqual(r.inserted_primary_key[0], 3)

    def fix_pickle_encoding(self, old_encoding):
        """Do the equivalent of master/contrib/fix_pickle_encoding.py"""
        changes_file = os.path.join(self.basedir, "changes.pck")
        with open(changes_file) as fp:
            changemgr = pickle.load(fp)
        changemgr.recode_changes(old_encoding, quiet=True)
        with open(changes_file, "w") as fp:
            pickle.dump(changemgr, fp)

    def test_upgrade(self):
        # this tarball contains some unicode changes, encoded as utf8, so it
        # needs fix_pickle_encoding invoked before we can get started
        return self.do_test_upgrade(pre_callbacks=[
            lambda _: self.fix_pickle_encoding('utf8'),
        ])


class UpgradeTestCitools(UpgradeTestMixin, unittest.TestCase):

    source_tarball = "citools.tgz"

    def verify_thd(self, conn):
        "partially verify the contents of the db - run in a thread"
        model = self.db.model

        # this is a big db, so we only spot-check things -- hopefully any errors
        # will occur on the import
        r = conn.execute(
            sa.select([model.changes],
                      whereclause=model.changes.c.changeid == 70))
        ch = r.fetchone()
        self.failUnlessEqual(ch.changeid, 70)
        self.failUnlessEqual(ch.author, u'Jakub Vysoky <jakub@borka.cz>')
        self.failUnlessEqual(
            ch.comments, u'some failing tests in check_downgrade and metapackage_version')
        self.failUnlessEqual(
            ch.revision, u'2ce0c33b7e10cce98e8d9c5b734b8c133ee4d320')
        self.failUnlessEqual(ch.branch, u'master')

        r = conn.execute(
            sa.select([model.change_files.c.filename],
                      whereclause=model.change_files.c.changeid == 70))
        self.assertEqual(r.scalar(), 'tests/test_debian.py')

        r = conn.execute(
            sa.select([model.changes],
                      whereclause=model.changes.c.changeid == 77))
        ch = r.fetchone()
        self.failUnlessEqual(ch.changeid, 77)
        self.failUnlessEqual(ch.author, u'BuildBot')
        self.failUnlessEqual(
            ch.comments, u'Dependency changed, sending dummy commit')
        self.failUnlessEqual(ch.revision, u'HEAD')
        self.failUnlessEqual(ch.branch, u'master')

        r = conn.execute(
            sa.select([model.change_files.c.filename],
                      whereclause=model.change_files.c.changeid == 77))
        self.assertEqual(r.scalar(), 'CHANGELOG')

        r = conn.execute(
            sa.select([model.sourcestamps],
                      whereclause=model.sourcestamps.c.id == ch.sourcestampid))
        row = r.fetchone()
        r.close()
        exp = {'revision': 'HEAD', 'branch': 'master', 'project': '',
               'repository': '', 'codebase': '', 'patchid': None}
        self.assertEqual(dict((k, row[k]) for k in exp), exp)

    def test_upgrade(self):
        return self.do_test_upgrade()


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


class TestWeirdChanges(change_import.ChangeImportMixin, unittest.TestCase):

    def setUp(self):
        d = self.setUpChangeImport()

        @d.addCallback
        def make_dbc(_):
            master = fakemaster.make_master()
            self.db = connector.DBConnector(self.basedir)
            self.db.setServiceParent(master)
            return self.db.setup(check_version=False)
        # note the connector isn't started, as we're testing upgrades
        return d

    def tearDown(self):
        return self.tearDownChangeImport()

    def testUpgradeListsAsFilenames(self):
        # sometimes the 'filenames' in a Change object are actually lists of files.  I don't
        # know how this happens, but we should be resilient to it.
        self.make_pickle(
            self.make_change(
                who=u"me!",
                files=[["foo", "bar"], ['bing'], 'baz'],
                comments=u"hello",
                branch="b1",
                revision=12345))

        d = self.db.model.upgrade()
        d.addCallback(lambda _: self.db.changes.getChange(1))

        @d.addCallback
        def check(c):
            self.failIf(c is None)
            self.assertEquals(sorted(c['files']),
                              sorted([u"foo", u"bar", u"bing", u"baz"]))
        return d

    def testUpgradeChangeProperties(self):
        # test importing complex properties
        self.make_pickle(
            self.make_change(
                who=u'author',
                comments='simple',
                files=['foo.c'],
                properties=dict(
                    list=['a', 'b'],
                    num=13,
                    str=u'SNOW\N{SNOWMAN}MAN',
                    d=dict(a=1, b=2)),
                branch="b1",
                revision='12345'))

        d = self.db.model.upgrade()
        d.addCallback(lambda _: self.db.changes.getChange(1))

        @d.addCallback
        def check(c):
            self.failIf(c is None)
            self.assertEquals(c['properties'].get('list')[1], 'Change')
            self.assertEquals(c['properties'].get('list')[0], ['a', 'b'])
            self.assertEquals(c['properties'].get('num')[0], 13)
            self.assertEquals(
                c['properties'].get('str')[0], u'SNOW\N{SNOWMAN}MAN')
            self.assertEquals(c['properties'].get('d')[0], dict(a=1, b=2))
        return d

    def testUpgradeChangeNoRevision(self):
        # test a change with no revision (which shouldn't be imported)
        self.make_pickle(
            self.make_change(
                who=u'author',
                comments='simple',
                files=['foo.c']))

        d = self.db.model.upgrade()
        d.addCallback(lambda _: self.db.changes.getChange(1))

        @d.addCallback
        def check(c):
            self.failUnless(c is None)
        return d


class TestPickles(unittest.TestCase):

    def test_sourcestamp_081(self):
        # an empty pickled sourcestamp from 0.8.1
        pkl = textwrap.dedent("""\
                (ibuildbot.sourcestamp
                SourceStamp
                p1
                (dp2
                S'repository'
                p3
                S''
                sS'buildbot.sourcestamp.SourceStamp.persistenceVersion'
                p4
                I2
                sS'patch'
                p5
                NsS'project'
                p6
                S''
                sS'branch'
                p7
                NsS'revision'
                p8
                Nsb.""")
        ss = pickle.loads(pkl)
        self.assertTrue(ss.revision is None)
        self.assertTrue(hasattr(ss, 'codebase'))

    def test_sourcestamp_version3(self):
        pkl = textwrap.dedent("""\
            (ibuildbot.sourcestamp
            SourceStamp
            p1
            (dp2
            S'project'
            p3
            S''
            sS'repository'
            p4
            S''
            sS'patch_info'
            p5
            NsS'buildbot.sourcestamp.SourceStamp.persistenceVersion'
            p6
            I2
            sS'patch'
            Nsb.""")
        ss = pickle.loads(pkl)
        styles.doUpgrade()
        self.assertEqual(ss.codebase, '')
