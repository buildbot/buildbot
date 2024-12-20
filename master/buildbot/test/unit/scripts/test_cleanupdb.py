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

from buildbot.scripts import cleanupdb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.unit.db import test_logs
from buildbot.test.util import dirs
from buildbot.test.util import misc
from buildbot.util.twisted import async_to_deferred

try:
    import lz4

    _ = lz4
    hasLz4 = True
except ImportError:
    hasLz4 = False

try:
    import zstandard

    _ = zstandard
    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False

try:
    import brotli

    _ = brotli
    HAS_BROTLI = True
except ImportError:
    HAS_BROTLI = False


def mkconfig(**kwargs):
    config = {"quiet": False, "basedir": os.path.abspath('basedir'), "force": True}
    config.update(kwargs)
    return config


def write_buildbot_tac(path):
    with open(path, "w", encoding='utf-8') as f:
        f.write(
            textwrap.dedent("""
            from twisted.application import service
            application = service.Application('buildmaster')
        """)
        )


def write_master_cfg(path, db_url, extraconfig):
    with open(path, "w", encoding='utf-8') as f:
        f.write(
            textwrap.dedent(f"""
            from buildbot.plugins import *
            c = BuildmasterConfig = dict()
            c['db_url'] = {db_url!r}
            c['buildbotNetUsageData'] = None
            c['multiMaster'] = True  # don't complain for no builders
            {extraconfig}
        """)
        )


class TestCleanupDb(
    misc.StdoutAssertionsMixin, dirs.DirsMixin, TestReactorMixin, unittest.TestCase
):
    def setUp(self):
        self.setup_test_reactor()
        self.setUpDirs('basedir')
        write_buildbot_tac(os.path.join('basedir', 'buildbot.tac'))
        self.setUpStdoutAssertions()

    def createMasterCfg(self, extraconfig=""):
        write_master_cfg(os.path.join('basedir', 'master.cfg'), 'sqlite://', extraconfig)

    @async_to_deferred
    async def test_cleanup_not_basedir(self):
        res = await cleanupdb._cleanupDatabase(mkconfig(basedir='doesntexist'))
        self.assertEqual(res, 1)
        self.assertInStdout('invalid buildmaster directory')

    @async_to_deferred
    async def test_cleanup_bad_config(self):
        res = await cleanupdb._cleanupDatabase(mkconfig(basedir='basedir'))
        self.assertEqual(res, 1)
        self.assertInStdout("master.cfg' does not exist")

    @async_to_deferred
    async def test_cleanup_bad_config2(self):
        self.createMasterCfg(extraconfig="++++ # syntaxerror")
        res = await cleanupdb._cleanupDatabase(mkconfig(basedir='basedir'))
        self.assertEqual(res, 1)
        self.assertInStdout("encountered a SyntaxError while parsing config file:")
        # config logs an error via log.err, we must eat it or trial will
        # complain
        self.flushLoggedErrors()


class TestCleanupDbRealDb(
    misc.StdoutAssertionsMixin, dirs.DirsMixin, TestReactorMixin, unittest.TestCase
):
    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.setUpDirs('basedir')
        write_buildbot_tac(os.path.join('basedir', 'buildbot.tac'))
        self.setUpStdoutAssertions()

        self.master = yield fakemaster.make_master(
            self, wantDb=True, wantRealReactor=True, sqlite_memory=False
        )

    def createMasterCfg(self, db_url, extraconfig=""):
        write_master_cfg(os.path.join('basedir', 'master.cfg'), db_url, extraconfig)

    @async_to_deferred
    async def test_cleanup(self):
        # we reuse the fake db background data from db.logs unit tests
        await self.master.db.insert_test_data(test_logs.Tests.backgroundData)

        # insert a log with lots of redundancy
        LOGDATA = "xx\n" * 2000
        logid = await self.master.db.logs.addLog(102, "x", "x", "s")
        await self.master.db.logs.appendLog(logid, LOGDATA)

        db_url = self.master.db.configured_url

        # test all methods
        lengths = {}
        for mode in self.master.db.logs.COMPRESSION_MODE:
            if mode == "lz4" and not hasLz4:
                # ok.. lz4 is not installed, don't fail
                lengths["lz4"] = 40
                continue
            if mode == "zstd" and not HAS_ZSTD:
                # zstandard is not installed, don't fail
                lengths["zstd"] = 20
                continue
            if mode == "br" and not HAS_BROTLI:
                # brotli is not installed, don't fail
                lengths["br"] = 14
                continue
            # create a master.cfg with different compression method
            self.createMasterCfg(db_url, f"c['logCompressionMethod'] = '{mode}'")
            res = await cleanupdb._cleanupDatabase(mkconfig(basedir='basedir'))
            self.assertEqual(res, 0)

            # make sure the compression don't change the data we can retrieve
            # via api
            res = await self.master.db.logs.getLogLines(logid, 0, 2000)
            self.assertEqual(res, LOGDATA)

            # retrieve the actual data size in db using raw sqlalchemy
            def thd(conn):
                tbl = self.master.db.model.logchunks
                q = sa.select(sa.func.sum(sa.func.length(tbl.c.content)))
                q = q.where(tbl.c.logid == logid)
                return conn.execute(q).fetchone()[0]

            lengths[mode] = await self.master.db.pool.do(thd)

        self.assertDictAlmostEqual(
            lengths,
            {
                'raw': 5999,
                'bz2': 44,
                'lz4': 40,
                'gz': 31,
                'zstd': 20,
                'br': 14,
            },
        )

    def assertDictAlmostEqual(self, d1, d2):
        # The test shows each methods return different size
        # but we still make a fuzzy comparison to resist if underlying libraries
        # improve efficiency
        self.assertEqual(len(d1), len(d2))
        for k in d2.keys():
            self.assertApproximates(d1[k], d2[k], 10)
