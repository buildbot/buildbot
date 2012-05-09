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

from __future__ import with_statement

import os
import cPickle
import tarfile
import shutil
import textwrap
from twisted.python import util
from twisted.persisted import styles
from twisted.internet import defer
from twisted.trial import unittest
import sqlalchemy as sa
from sqlalchemy.engine import reflection
import migrate
import migrate.versioning.api
from migrate.versioning import schemadiff
from buildbot.db import connector
from buildbot.test.util import change_import, db, querylog
from buildbot.test.fake import fakemaster

# monkey-patch for "compare_model_to_db gets confused by sqlite_sequence",
# http://code.google.com/p/sqlalchemy-migrate/issues/detail?id=124
def getDiffMonkeyPatch(metadata, engine, excludeTables=None):
    """
    Return differences of model against database.

    :return: object which will evaluate to :keyword:`True` if there \
      are differences else :keyword:`False`.
    """
    db_metadata = sa.MetaData(engine, reflect=True)

    # sqlite will include a dynamically generated 'sqlite_sequence' table if
    # there are autoincrement sequences in the database; this should not be
    # compared.
    if engine.dialect.name == 'sqlite':
        if 'sqlite_sequence' in db_metadata.tables:
            db_metadata.remove(db_metadata.tables['sqlite_sequence'])

    return schemadiff.SchemaDiff(metadata, db_metadata,
                      labelA='model',
                      labelB='database',
                      excludeTables=excludeTables)

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

        master = fakemaster.make_master()
        master.config.db['db_url'] = self.db_url
        self.db = connector.DBConnector(master, self.basedir)
        yield self.db.setup(check_version=False)

        querylog.log_from_engine(self.db.pool.engine)

    @defer.inlineCallbacks
    def tearDownUpgradeTest(self):
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
        # this patch only applies to sqlalchemy-migrate-0.7.x.  We prefer to
        # skip the remainder of the test, even though some significant testing
        # has already occcurred (verify_thd), to indicate that the test was not
        # complete.
        if (not hasattr(migrate, '__version__')
            or not migrate.__version__.startswith('0.7.')):
            raise unittest.SkipTest("model comparison skipped: unsupported "
                                    "version of sqlalchemy-migrate")
        self.patch(schemadiff, 'getDiffOfModelAgainstDatabase',
                                getDiffMonkeyPatch)
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
                         column_names=sorted([ c.name for c in idx.columns ]))
                    for idx in tbl.indexes ])

                # include implied indexes on postgres and mysql
                if engine.dialect.name == 'mysql':
                    implied = [ idx for (tname, idx)
                                in self.db.model.implied_indexes
                                if tname == tbl.name ]
                    exp = sorted(exp + implied)

                got = sorted(insp.get_indexes(tbl.name))
                if exp != got:
                    got_names = set([ idx['name'] for idx in got ])
                    exp_names = set([ idx['name'] for idx in exp ])
                    got_info = dict( (idx['name'],idx) for idx in got )
                    exp_info = dict( (idx['name'],idx) for idx in exp )
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
        def catch_TypeError(f):
            f.trap(TypeError)
            raise unittest.SkipTest("model comparison skipped: bugs in schema "
                                    "reflection on this sqlite version")
        d.addErrback(catch_TypeError)

        def check(diff):
            if diff:
                self.fail(str(diff))
        d.addCallback(check)
        return d

    def do_test_upgrade(self, pre_callbacks=[]):
        d = defer.succeed(None)
        for cb in pre_callbacks:
            d.addCallback(cb)
        d.addCallback(lambda _ : self.db.model.upgrade())
        d.addCallback(lambda _ : self.db.pool.do(self.verify_thd))
        d.addCallback(lambda _ : self.assertModelMatches())
        return d


class UpgradeTestEmpty(UpgradeTestMixin, unittest.TestCase):

    use_real_db = True

    def test_emptydb_modelmatches(self):
        d = self.db.model.upgrade()
        d.addCallback(lambda r : self.assertModelMatches())
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
        self.failUnlessEqual(ch.author, u'the snowman <\N{SNOWMAN}@norpole.net>')
        self.failUnlessEqual(ch.comments, u'shooting star or \N{COMET}?')
        self.failUnlessEqual(ch.revision, u'\N{BLACK STAR}-devel')
        self.failUnlessEqual(ch.branch, u'\N{COMET}')
        ch = r.fetchone()
        self.failUnlessEqual(ch.changeid, 2)
        self.failUnlessEqual(ch.author, u"dustin <dustin@v.igoro.us>")
        self.failUnlessEqual(ch.comments, u'on-branch change')
        self.failUnlessEqual(ch.revision, u'1234')
        self.failUnlessEqual(ch.branch, u'') # arguably a bug - should be None?

        r = conn.execute(
            sa.select([model.change_files]))
        # use a set to avoid depending on db collation
        filenames = set([ row.filename for row in r ])
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
            changemgr = cPickle.load(fp)
        changemgr.recode_changes(old_encoding, quiet=True)
        with open(changes_file, "w") as fp:
            cPickle.dump(changemgr, fp)

    def test_upgrade(self):
        # this tarball contains some unicode changes, encoded as utf8, so it
        # needs fix_pickle_encoding invoked before we can get started
        return self.do_test_upgrade(pre_callbacks=[
            lambda _ : self.fix_pickle_encoding('utf8'),
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
        self.failUnlessEqual(ch.comments, u'some failing tests in check_downgrade and metapackage_version')
        self.failUnlessEqual(ch.revision, u'2ce0c33b7e10cce98e8d9c5b734b8c133ee4d320')
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
        self.failUnlessEqual(ch.comments, u'Dependency changed, sending dummy commit')
        self.failUnlessEqual(ch.revision, u'HEAD')
        self.failUnlessEqual(ch.branch, u'master')

        r = conn.execute(
            sa.select([model.change_files.c.filename],
            whereclause=model.change_files.c.changeid == 77))
        self.assertEqual(r.scalar(), 'CHANGELOG')

    def test_upgrade(self):
        return self.do_test_upgrade()


class UpgradeTestV082(UpgradeTestMixin, unittest.TestCase):

    source_tarball = "v082.tgz"

    def verify_thd(self, conn):
        "partially verify the contents of the db - run in a thread"
        model = self.db.model

        tbl = model.buildrequests
        r = conn.execute(tbl.select(order_by=tbl.c.id))
        buildreqs = [ (br.id, br.buildsetid,
                       br.complete, br.results)
                      for br in r.fetchall() ]
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
        objects = model.objects
        r = conn.execute(sa.select([ br_claims.outerjoin(objects,
                    br_claims.c.objectid == objects.c.id)]))
        # the int() is required here because sqlalchemy stores floats in an
        # INTEGER column(!)
        buildreqs = [ (brc.brid, int(brc.claimed_at), brc.name, brc.class_name)
                      for brc in r.fetchall() ]
        objname = 'euclid:/home/dustin/code/buildbot/t/buildbot/sand27/master'
        self.assertEqual(buildreqs, [
            (1, 1310337746, objname, 'buildbot.master.BuildMaster'),
            (2, 1310337757, objname, 'buildbot.master.BuildMaster'),
            (3, 1310337757, objname, 'buildbot.master.BuildMaster'),
            (4, 1310337757, objname, 'buildbot.master.BuildMaster'),
            (5, 1310337779, objname, 'buildbot.master.BuildMaster'),
            (6, 1310337779, objname, 'buildbot.master.BuildMaster'),
            (7, 1310337779, objname, 'buildbot.master.BuildMaster'),
        ])

    def test_upgrade(self):
        return self.do_test_upgrade()


class UpgradeTestV083(UpgradeTestMixin, unittest.TestCase):

    source_tarball = "v083.tgz"

    def verify_thd(self, conn):
        "partially verify the contents of the db - run in a thread"
        model = self.db.model

        tbl = model.buildrequests
        r = conn.execute(tbl.select(order_by=tbl.c.id))
        buildreqs = [ (br.id, br.buildsetid,
                       br.complete, br.results)
                      for br in r.fetchall() ]
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
        objects = model.objects
        r = conn.execute(sa.select([ br_claims.outerjoin(objects,
                    br_claims.c.objectid == objects.c.id)]))
        # the int() is required here because sqlalchemy stores floats in an
        # INTEGER column(!)
        buildreqs = [ (brc.brid, int(brc.claimed_at), brc.name, brc.class_name)
                      for brc in r.fetchall() ]
        objname = 'euclid:/home/dustin/code/buildbot/t/buildbot/sand27/master'
        self.assertEqual(buildreqs, [
            (1, 1310326850, objname, 'buildbot.master.BuildMaster'),
            (2, 1310326862, objname, 'buildbot.master.BuildMaster'),
            (3, 1310326872, objname, 'buildbot.master.BuildMaster'),
            (4, 1310326872, objname, 'buildbot.master.BuildMaster'),
            (5, 1310326872, objname, 'buildbot.master.BuildMaster'),
            (6, 1310326872, objname, 'buildbot.master.BuildMaster'),
            (7, 1310326872, objname, 'buildbot.master.BuildMaster'),
            (8, 1310326872, objname, 'buildbot.master.BuildMaster'),
            (9, 1310326872, objname, 'buildbot.master.BuildMaster'),
            (10, 1310326872, objname, 'buildbot.master.BuildMaster'),
            (11, 1310326895, objname, 'buildbot.master.BuildMaster'),
            (12, 1310326900, objname, 'buildbot.master.BuildMaster'),
            (13, 1310326900, objname, 'buildbot.master.BuildMaster'),
            (14, 1310326900, objname, 'buildbot.master.BuildMaster'),
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
        buildreqs = [ (br.id, br.buildsetid,
                       br.complete, br.results)
                      for br in r.fetchall() ]
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
        objects = model.objects
        r = conn.execute(sa.select([ br_claims.outerjoin(objects,
                    br_claims.c.objectid == objects.c.id)]))
        # the int() is required here because sqlalchemy stores floats in an
        # INTEGER column(!)
        buildreqs = [ (brc.brid, int(brc.claimed_at), brc.name, brc.class_name)
                      for brc in r.fetchall() ]
        objname = 'euclid:/home/dustin/code/buildbot/t/buildbot/sand27/master'
        self.assertEqual(buildreqs, [
            (1, 1310406744, objname, 'buildbot.master.BuildMaster'),
            (2, 1310406863, objname, 'buildbot.master.BuildMaster'),
            (3, 1310406863, objname, 'buildbot.master.BuildMaster'),
            (4, 1310406863, objname, 'buildbot.master.BuildMaster'),
            (5, 1310406863, objname, 'buildbot.master.BuildMaster'),
            # 6, 7 aren't claimed yet
        ])

    def test_upgrade(self):
        return self.do_test_upgrade()


class TestWeirdChanges(change_import.ChangeImportMixin, unittest.TestCase):
    def setUp(self):
        d = self.setUpChangeImport()
        def make_dbc(_):
            master = fakemaster.make_master()
            self.db = connector.DBConnector(master, self.basedir)
            return self.db.setup(check_version=False)
        d.addCallback(make_dbc)
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
                    files=[["foo","bar"], ['bing'], 'baz'],
                    comments=u"hello",
                    branch="b1",
                    revision=12345))

        d = self.db.model.upgrade()
        d.addCallback(lambda _ : self.db.changes.getChange(1))
        def check(c):
            self.failIf(c is None)
            self.assertEquals(sorted(c['files']),
                              sorted([u"foo", u"bar", u"bing", u"baz"]))
        d.addCallback(check)
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
        d.addCallback(lambda _ : self.db.changes.getChange(1))
        def check(c):
            self.failIf(c is None)
            self.assertEquals(c['properties'].get('list')[1], 'Change')
            self.assertEquals(c['properties'].get('list')[0], ['a', 'b'])
            self.assertEquals(c['properties'].get('num')[0], 13)
            self.assertEquals(c['properties'].get('str')[0], u'SNOW\N{SNOWMAN}MAN')
            self.assertEquals(c['properties'].get('d')[0], dict(a=1, b=2))
        d.addCallback(check)
        return d

    def testUpgradeChangeNoRevision(self):
        # test a change with no revision (which shouldn't be imported)
        self.make_pickle(
                self.make_change(
                    who=u'author',
                    comments='simple',
                    files=['foo.c']))

        d = self.db.model.upgrade()
        d.addCallback(lambda _ : self.db.changes.getChange(1))
        def check(c):
            self.failUnless(c is None)
        d.addCallback(check)
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
        ss = cPickle.loads(pkl)
        self.assertTrue(ss.revision is None)
        self.assertTrue(hasattr(ss, '_addSourceStampToDatabase_lock'))

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
        ss = cPickle.loads(pkl)
        styles.doUpgrade()
        self.assertEqual(ss.codebase, '')
