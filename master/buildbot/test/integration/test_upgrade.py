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
import cPickle
import tarfile
from twisted.python import util
from twisted.internet import defer
from twisted.trial import unittest
import sqlalchemy as sa
import migrate.versioning.api
from buildbot.db import connector
from buildbot.test.util import db

class Thing(object):
    # simple object-with-attributes for use in faking pickled objects
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

class UpgradeTestMixin(object):
    """Supporting code to test upgrading from older versions by untarring a
    basedir tarball and then checking that the results are as expected."""

    # class variables to set in subclasses

    source_tarball = None # filename of the tarball (sibling to this file)
    db_url = "sqlite:///state.sqlite" # db URL to use (usually default is OK)

    def setUpUpgradeTest(self):
        self.basedir = None

        tarball = util.sibpath(__file__, self.source_tarball)
        if not os.path.exists(tarball):
            raise unittest.SkipTest(
                "'%s' not found (normal when not building from Git)" % tarball)

        tf = tarfile.open(tarball)
        prefixes = set()
        for inf in tf:
            tf.extract(inf)
            prefixes.add(inf.name.split('/', 1)[0])
        # (note that tf.extractall isn't available in py2.4)

        # get the top-level dir from the tarball
        assert len(prefixes) == 1, "tarball has multiple top-level dirs!"
        self.basedir = prefixes.pop()

        self.db = connector.DBConnector(self.db_url, self.basedir)

    def tearDownUpgradeTest(self):
        if self.basedir:
            pass #shutil.rmtree(self.basedir)

    # save subclasses the trouble of calling our setUp and tearDown methods

    def setUp(self):
        self.setUpUpgradeTest()

    def tearDown(self):
        self.tearDownUpgradeTest()

class DBUtilsMixin(object):
    """Utilities -- assertions and whatnot -- for classes below"""

    def assertModelMatches(self):
        def comp(engine):
            return migrate.versioning.api.compare_model_to_db(
                engine,
                self.db.model.repo_path,
                self.db.model.metadata)
        d = self.db.pool.do_with_engine(comp)
        def check(diff):
            if diff:
                self.fail(str(diff))
        d.addCallback(check)
        return d

    def fix_pickle_encoding(self, old_encoding):
        """Do the equivalent of master/contrib/fix_pickle_encoding.py"""
        changes_file = os.path.join(self.basedir, "changes.pck")
        fp = open(changes_file)
        changemgr = cPickle.load(fp)
        fp.close()
        changemgr.recode_changes(old_encoding, quiet=True)
        cPickle.dump(changemgr, open(changes_file, "w"))

class UpgradeTestEmpty(db.RealDatabaseMixin, DBUtilsMixin, unittest.TestCase):

    def setUp(self):
        self.setUpRealDatabase()

        self.basedir = os.path.abspath("basedir")
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        os.makedirs(self.basedir)

        self.db = connector.DBConnector(self.db_url, self.basedir)

    def tearDown(self):
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)

        self.tearDownRealDatabase()

    def test_emptydb_modelmatches(self):
        d = self.db.model.upgrade()
        d.addCallback(lambda r : self.assertModelMatches())
        return d

class UpgradeTest075(UpgradeTestMixin, DBUtilsMixin, unittest.TestCase):

    # this tarball contains some unicode changes, encoded as utf8, so it
    # needs fix_pickle_encoding invoked before we can get started
    source_tarball = "master-0-7-5.tgz"

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


    def test_test(self):
        d = defer.succeed(None)
        d.addCallback(lambda _ : self.fix_pickle_encoding('utf8'))
        d.addCallback(lambda _ : self.db.model.upgrade())
        d.addCallback(lambda _ : self.assertModelMatches())
        d.addCallback(lambda _ : self.db.pool.do(self.verify_thd))
        return d

class UpgradeTestCitools(UpgradeTestMixin, DBUtilsMixin, unittest.TestCase):

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


    def test_test(self):
        d = defer.succeed(None)
        d.addCallback(lambda _ : self.db.model.upgrade())
        d.addCallback(lambda _ : self.assertModelMatches())
        d.addCallback(lambda _ : self.db.pool.do(self.verify_thd))
        return d
