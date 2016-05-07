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
import textwrap

import sqlalchemy as sa
from twisted.internet import defer
from twisted.trial import unittest

import test_db_logs
from buildbot.db.connector import DBConnector
from buildbot.scripts import cleanupdb
from buildbot.test.fake import fakemaster
from buildbot.test.util import db
from buildbot.test.util import dirs
from buildbot.test.util import misc

try:
    import lz4
    [lz4]
    hasLz4 = True
except ImportError:
    hasLz4 = False


def mkconfig(**kwargs):
    config = dict(quiet=False, basedir=os.path.abspath('basedir'))
    config.update(kwargs)
    return config


def patch_environ(case, key, value):
    """
    Add an environment variable for the duration of a test.
    """
    old_environ = os.environ.copy()

    def cleanup():
        os.environ.clear()
        os.environ.update(old_environ)
    os.environ[key] = value
    case.addCleanup(cleanup)


class TestCleanupDb(misc.StdoutAssertionsMixin, dirs.DirsMixin,
                    db.RealDatabaseMixin, unittest.TestCase):

    def setUp(self):
        self.origcwd = os.getcwd()
        self.setUpDirs('basedir')
        with open(os.path.join('basedir', 'buildbot.tac'), 'wt') as f:
            f.write(textwrap.dedent("""
                from twisted.application import service
                application = service.Application('buildmaster')
            """))
        self.setUpStdoutAssertions()

    def tearDown(self):
        os.chdir(self.origcwd)
        self.tearDownDirs()

    def createMasterCfg(self, extraconfig=""):
        os.chdir(self.origcwd)
        with open(os.path.join('basedir', 'master.cfg'), 'wt') as f:
            f.write(textwrap.dedent("""
                from buildbot.plugins import *
                c = BuildmasterConfig = dict()
                c['db_url'] = {dburl}
                c['multiMaster'] = True  # dont complain for no builders
                {extraconfig}
            """.format(dburl=repr(os.environ["BUILDBOT_TEST_DB_URL"]),
                       extraconfig=extraconfig)))

    @defer.inlineCallbacks
    def test_cleanup_not_basedir(self):
        res = yield cleanupdb._cleanupDatabase(mkconfig(basedir='doesntexist'))
        self.assertEqual(res, 1)
        self.assertInStdout('invalid buildmaster directory')

    @defer.inlineCallbacks
    def test_cleanup_bad_config(self):
        res = yield cleanupdb._cleanupDatabase(mkconfig(basedir='basedir'))
        self.assertEqual(res, 1)
        self.assertInStdout("master.cfg' does not exist")

    @defer.inlineCallbacks
    def test_cleanup_bad_config2(self):
        # test may use mysql or pg if configured in env
        if "BUILDBOT_TEST_DB_URL" not in os.environ:

            patch_environ(self, "BUILDBOT_TEST_DB_URL", "sqlite:///" + os.path.join(self.origcwd,
                                                                                    "basedir", "state.sqlite"))

        self.createMasterCfg(extraconfig="++++ # syntaxerror")
        res = yield cleanupdb._cleanupDatabase(mkconfig(basedir='basedir'))
        self.assertEqual(res, 1)
        self.assertInStdout(
            "encountered a SyntaxError while parsing config file:")
        # config logs an error via log.err, we must eat it or trial will
        # complain
        self.flushLoggedErrors()

    @defer.inlineCallbacks
    def test_cleanup(self):

        # test may use mysql or pg if configured in env
        if "BUILDBOT_TEST_DB_URL" not in os.environ:

            patch_environ(self, "BUILDBOT_TEST_DB_URL", "sqlite:///" + os.path.join(self.origcwd,
                                                                                    "basedir", "state.sqlite"))
        # we reuse RealDatabaseMixin to setup the db
        yield self.setUpRealDatabase(table_names=['logs', 'logchunks', 'steps', 'builds', 'builders',
                                                  'masters', 'buildrequests', 'buildsets',
                                                  'workers'])
        master = fakemaster.make_master()
        master.config.db['db_url'] = self.db_url
        self.db = DBConnector(self.basedir)
        self.db.setServiceParent(master)
        self.db.pool = self.db_pool

        # we reuse the fake db background data from db.logs unit tests
        yield self.insertTestData(test_db_logs.Tests.backgroundData)

        # insert a log with lots of redundancy
        LOGDATA = "xx\n" * 2000
        logid = yield self.db.logs.addLog(102, "x", "x", "s")
        yield self.db.logs.appendLog(logid, LOGDATA)

        # test all methods
        lengths = {}
        for mode in self.db.logs.COMPRESSION_MODE.keys():
            if mode == "lz4" and not hasLz4:
                # ok.. lz4 is not installed, dont fail
                lengths["lz4"] = 40
                continue
            # create a master.cfg with different compression method
            self.createMasterCfg("c['logCompressionMethod'] = '%s'" % (mode,))
            res = yield cleanupdb._cleanupDatabase(mkconfig(basedir='basedir'))
            self.assertEqual(res, 0)

            # make sure the compression don't change the data we can retrieve
            # via api
            res = yield self.db.logs.getLogLines(logid, 0, 2000)
            self.assertEqual(res, LOGDATA)

            # retrieve the actual data size in db using raw sqlalchemy
            def thd(conn):
                tbl = self.db.model.logchunks
                q = sa.select([tbl.c.content])
                q = q.where(tbl.c.logid == logid)
                return sum([len(row.content) for row in conn.execute(q)])
            lengths[mode] = yield self.db.pool.do(thd)

        self.assertDictAlmostEqual(
            lengths, {'raw': 5999, 'bz2': 44, 'lz4': 40, 'gz': 31})

    def assertDictAlmostEqual(self, d1, d2):
        # The test shows each methods return different size
        # but we still make a fuzzy comparaison to resist if underlying libraries
        # improve efficiency
        self.assertEqual(len(d1), len(d2))
        for k in d2.keys():
            self.assertApproximates(d1[k], d2[k], 10)
