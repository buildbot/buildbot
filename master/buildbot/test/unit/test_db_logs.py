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

import base64
import textwrap

from buildbot.db import logs
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import connector_component
from buildbot.test.util import interfaces
from buildbot.test.util import validation
from twisted.internet import defer
from twisted.trial import unittest


class Tests(interfaces.InterfaceTests):

    backgroundData = [
        fakedb.Buildslave(id=47, name='linux'),
        fakedb.Buildset(id=20),
        fakedb.Builder(id=88, name='b1'),
        fakedb.BuildRequest(id=41, buildsetid=20, builderid=88),
        fakedb.Master(id=88),
        fakedb.Build(id=30, buildrequestid=41, number=7, masterid=88,
                     builderid=88, buildslaveid=47),
        fakedb.Step(id=101, buildid=30, number=1, name='one'),
        fakedb.Step(id=102, buildid=30, number=2, name='two'),
    ]

    testLogLines = [
        fakedb.Log(id=201, stepid=101, name=u'stdio', slug=u'stdio',
                   complete=0, num_lines=7, type=u's'),
        fakedb.LogChunk(logid=201, first_line=0, last_line=1, compressed=0,
                        content=textwrap.dedent("""\
                    line zero
                    line 1""" + "x" * 200)),
        fakedb.LogChunk(logid=201, first_line=2, last_line=4, compressed=0,
                        content=textwrap.dedent("""\
                    line TWO

                    line 2**2""")),
        fakedb.LogChunk(logid=201, first_line=5, last_line=5, compressed=0,
                        content="another line"),
        fakedb.LogChunk(logid=201, first_line=6, last_line=6, compressed=0,
                        content="yet another line"),
    ]
    bug3101Content = base64.b64decode("""
        PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0
        9PT09PT09PT09PT09PT09PT09PT09PT09PT09PQpbU0tJUFBFRF0Kbm90IGEgd2luMz
        IgcGxhdGZvcm0KCmJ1aWxkc2xhdmUudGVzdC51bml0LnRlc3RfcnVucHJvY2Vzcy5UZ
        XN0UnVuUHJvY2Vzcy50ZXN0UGlwZVN0cmluZwotLS0tLS0tLS0tLS0tLS0tLS0tLS0t
        LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0
        tLS0tLS0tClJhbiAyNjcgdGVzdHMgaW4gNS4zNzhzCgpQQVNTRUQgKHNraXBzPTEsIH
        N1Y2Nlc3Nlcz0yNjYpCnByb2dyYW0gZmluaXNoZWQgd2l0aCBleGl0IGNvZGUgMAplb
        GFwc2VkVGltZT04LjI0NTcwMg==""")

    bug3101Rows = [
        fakedb.Log(id=1470, stepid=101, name=u'problems', slug=u'problems',
                   complete=1, num_lines=11, type=u't'),
        fakedb.LogChunk(logid=1470, first_line=0, last_line=10, compressed=0,
                        content=bug3101Content),
    ]

    @defer.inlineCallbacks
    def checkTestLogLines(self):
        expLines = ['line zero', 'line 1' + "x" * 200, 'line TWO', '', 'line 2**2',
                    'another line', 'yet another line']
        for first_line in range(0, 7):
            for last_line in range(first_line, 7):
                got_lines = yield self.db.logs.getLogLines(
                    201, first_line, last_line)
                self.assertEqual(
                    got_lines,
                    "\n".join(expLines[first_line:last_line + 1] + [""]))
        # check overflow
        self.assertEqual((yield self.db.logs.getLogLines(201, 5, 20)),
                         "\n".join(expLines[5:7] + [""]))

    # signature tests

    def test_signature_getLog(self):
        @self.assertArgSpecMatches(self.db.logs.getLog)
        def getLog(self, logid):
            pass

    def test_signature_getLogBySlug(self):
        @self.assertArgSpecMatches(self.db.logs.getLogBySlug)
        def getLogBySlug(self, stepid, slug):
            pass

    def test_signature_getLogs(self):
        @self.assertArgSpecMatches(self.db.logs.getLogs)
        def getLogs(self, stepid=None):
            pass

    def test_signature_getLogLines(self):
        @self.assertArgSpecMatches(self.db.logs.getLogLines)
        def getLogLines(self, logid, first_line, last_line):
            pass

    def test_signature_addLog(self):
        @self.assertArgSpecMatches(self.db.logs.addLog)
        def addLog(self, stepid, name, slug, type):
            pass

    def test_signature_appendLog(self):
        @self.assertArgSpecMatches(self.db.logs.appendLog)
        def appendLog(self, logid, content):
            pass

    def test_signature_finishLog(self):
        @self.assertArgSpecMatches(self.db.logs.finishLog)
        def finishLog(self, logid):
            pass

    def test_signature_compressLog(self):
        @self.assertArgSpecMatches(self.db.logs.compressLog)
        def compressLog(self, logid):
            pass

    # method tests

    @defer.inlineCallbacks
    def test_getLog(self):
        yield self.insertTestData(self.backgroundData + [
            fakedb.Log(id=201, stepid=101, name=u'stdio', slug=u'stdio',
                       complete=0, num_lines=200, type=u's'),
        ])
        logdict = yield self.db.logs.getLog(201)
        validation.verifyDbDict(self, 'logdict', logdict)
        self.assertEqual(logdict, {
            'id': 201,
            'stepid': 101,
            'name': u'stdio',
            'slug': u'stdio',
            'complete': False,
            'num_lines': 200,
            'type': 's',
        })

    @defer.inlineCallbacks
    def test_getLog_missing(self):
        logdict = yield self.db.logs.getLog(201)
        self.assertEqual(logdict, None)

    @defer.inlineCallbacks
    def test_getLogBySlug(self):
        yield self.insertTestData(self.backgroundData + [
            fakedb.Log(id=201, stepid=101, name=u'stdio', slug=u'stdio',
                       complete=0, num_lines=200, type=u's'),
            fakedb.Log(id=202, stepid=101, name=u'dbg.log', slug=u'dbg_log',
                       complete=1, num_lines=200, type=u's'),
        ])
        logdict = yield self.db.logs.getLogBySlug(101, u'dbg_log')
        validation.verifyDbDict(self, 'logdict', logdict)
        self.assertEqual(logdict['id'], 202)

    @defer.inlineCallbacks
    def test_getLogBySlug_missing(self):
        yield self.insertTestData(self.backgroundData + [
            fakedb.Log(id=201, stepid=101, name=u'stdio', slug=u'stdio',
                       complete=0, num_lines=200, type=u's'),
        ])
        logdict = yield self.db.logs.getLogBySlug(102, u'stdio')
        self.assertEqual(logdict, None)

    @defer.inlineCallbacks
    def test_getLogs(self):
        yield self.insertTestData(self.backgroundData + [
            fakedb.Log(id=201, stepid=101, name=u'stdio', slug=u'stdio',
                       complete=0, num_lines=200, type=u's'),
            fakedb.Log(id=202, stepid=101, name=u'dbg.log', slug=u'dbg_log',
                       complete=1, num_lines=300, type=u't'),
            fakedb.Log(id=203, stepid=102, name=u'stdio', slug=u'stdio',
                       complete=0, num_lines=200, type=u's'),
        ])
        logdicts = yield self.db.logs.getLogs(101)
        for logdict in logdicts:
            validation.verifyDbDict(self, 'logdict', logdict)
        self.assertEqual(sorted([ld['id'] for ld in logdicts]), [201, 202])

    @defer.inlineCallbacks
    def test_getLogLines(self):
        yield self.insertTestData(self.backgroundData + self.testLogLines)
        yield self.checkTestLogLines()

        # check line number reversal
        self.assertEqual((yield self.db.logs.getLogLines(201, 6, 3)), '')

    @defer.inlineCallbacks
    def test_getLogLines_empty(self):
        yield self.insertTestData(self.backgroundData + [
            fakedb.Log(id=201, stepid=101, name=u'stdio', slug=u'stdio',
                       complete=0, num_lines=200, type=u's'),
        ])
        self.assertEqual((yield self.db.logs.getLogLines(201, 9, 99)), '')
        self.assertEqual((yield self.db.logs.getLogLines(999, 9, 99)), '')

    @defer.inlineCallbacks
    def test_getLogLines_bug3101(self):
        # regression test for #3101
        content = self.bug3101Content
        yield self.insertTestData(self.backgroundData + self.bug3101Rows)
        # overall content is the same, with '\n' padding at the end
        self.assertEqual((yield self.db.logs.getLogLines(1470, 0, 99)),
                         self.bug3101Content + '\n')
        # try to fetch just one line
        self.assertEqual((yield self.db.logs.getLogLines(1470, 0, 0)),
                         content.split('\n')[0] + '\n')

    @defer.inlineCallbacks
    def test_addLog_getLog(self):
        yield self.insertTestData(self.backgroundData)
        logid = yield self.db.logs.addLog(
            stepid=101, name=u'config.log', slug=u'config_log', type=u't')
        logdict = yield self.db.logs.getLog(logid)
        validation.verifyDbDict(self, 'logdict', logdict)
        self.assertEqual(logdict, {
            'id': logid,
            'stepid': 101,
            'name': u'config.log',
            'slug': u'config_log',
            'complete': False,
            'num_lines': 0,
            'type': 't',
        })

    @defer.inlineCallbacks
    def test_appendLog_getLogLines(self):
        yield self.insertTestData(self.backgroundData + self.testLogLines)
        logid = yield self.db.logs.addLog(
            stepid=102, name=u'another', slug=u'another', type=u's')
        self.assertEqual((yield self.db.logs.appendLog(logid, u'xyz\n')),
                         (0, 0))
        self.assertEqual((yield self.db.logs.appendLog(201, u'abc\ndef\n')),
                         (7, 8))
        self.assertEqual((yield self.db.logs.appendLog(logid, u'XYZ\n')),
                         (1, 1))
        self.assertEqual((yield self.db.logs.getLogLines(201, 6, 7)),
                         u"yet another line\nabc\n")
        self.assertEqual((yield self.db.logs.getLogLines(201, 7, 8)),
                         u"abc\ndef\n")
        self.assertEqual((yield self.db.logs.getLogLines(201, 8, 8)),
                         u"def\n")
        self.assertEqual((yield self.db.logs.getLogLines(logid, 0, 1)),
                         u"xyz\nXYZ\n")
        self.assertEqual((yield self.db.logs.getLog(logid)), {
            'complete': False,
            'id': logid,
            'name': u'another',
            'slug': u'another',
            'num_lines': 2,
            'stepid': 102,
            'type': u's',
        })

    @defer.inlineCallbacks
    def test_compressLog(self):
        yield self.insertTestData(self.backgroundData + self.testLogLines)
        yield self.db.logs.compressLog(201)
        # test log lines should still be readable just the same
        yield self.checkTestLogLines()

    @defer.inlineCallbacks
    def test_addLogLines_big_chunk(self):
        yield self.insertTestData(self.backgroundData + self.testLogLines)
        self.assertEqual(
            (yield self.db.logs.appendLog(201, u'abc\n' * 20000)),  # 80k
            (7, 20006))
        lines = yield self.db.logs.getLogLines(201, 7, 50000)
        self.assertEqual(len(lines), 80000)
        self.assertEqual(lines, (u'abc\n' * 20000))

    @defer.inlineCallbacks
    def test_addLogLines_big_chunk_big_lines(self):
        yield self.insertTestData(self.backgroundData + self.testLogLines)
        line = u'x' * 33000 + '\n'
        self.assertEqual((yield self.db.logs.appendLog(201, line * 3)),
                         (7, 9))  # three long lines, all truncated
        lines = yield self.db.logs.getLogLines(201, 7, 100)
        self.assertEqual(len(lines), 99003)
        self.assertEqual(lines, (line * 3))


class RealTests(Tests):

    @defer.inlineCallbacks
    def test_addLogLines_db(self):
        yield self.insertTestData(self.backgroundData + self.testLogLines)
        self.assertEqual(
            (yield self.db.logs.appendLog(201, u'abc\ndef\nghi\njkl\n')),
            (7, 10))

        def thd(conn):
            res = conn.execute(self.db.model.logchunks.select(
                whereclause=self.db.model.logchunks.c.first_line > 6))
            row = res.fetchone()
            res.close()
            return dict(row)
        newRow = yield self.db.pool.do(thd)
        self.assertEqual(newRow, {
            'logid': 201,
            'first_line': 7,
            'last_line': 10,
            'content': 'abc\ndef\nghi\njkl',
            'compressed': 0})

    @defer.inlineCallbacks
    def test_addLogLines_huge_lines(self):
        yield self.insertTestData(self.backgroundData + self.testLogLines)
        line = u'xy' * 70000 + '\n'
        yield self.db.logs.appendLog(201, line * 3)
        for lineno in 7, 8, 9:
            line = yield self.db.logs.getLogLines(201, lineno, lineno)
            self.assertEqual(len(line), 65537)

    def test_splitBigChunk_unicode_misalignment(self):
        unaligned = (u'a ' + u'\N{SNOWMAN}' * 30000 + '\n').encode('utf-8')
        # the first 65536 bytes of that line are not valid utf-8
        self.assertRaises(UnicodeDecodeError, lambda:
                          unaligned[:65536].decode('utf-8'))
        chunk, remainder = self.db.logs._splitBigChunk(unaligned, 1)
        # see that it was truncated by two bytes, and now properly decodes
        self.assertEqual(len(chunk), 65534)
        chunk.decode('utf-8')

    @defer.inlineCallbacks
    def test_no_compress_small_chunk(self):
        yield self.insertTestData(self.backgroundData + self.testLogLines)
        self.db.master.config.logCompressionMethod = "gz"
        self.assertEqual(
            (yield self.db.logs.appendLog(201, u'abc\n')),
            (7, 7))

        def thd(conn):
            res = conn.execute(self.db.model.logchunks.select(
                whereclause=self.db.model.logchunks.c.first_line > 6))
            row = res.fetchone()
            res.close()
            return dict(row)

        newRow = yield self.db.pool.do(thd)
        self.assertEqual(newRow, {
            'logid': 201,
            'first_line': 7,
            'last_line': 7,
            'content': 'abc',
            'compressed': 0})

    @defer.inlineCallbacks
    def test_raw_compress_big_chunk(self):
        yield self.insertTestData(self.backgroundData + self.testLogLines)
        line = u'xy' * 10000
        self.db.master.config.logCompressionMethod = "raw"
        self.assertEqual(
            (yield self.db.logs.appendLog(201, line + '\n')),
            (7, 7))

        def thd(conn):
            res = conn.execute(self.db.model.logchunks.select(
                whereclause=self.db.model.logchunks.c.first_line > 6))
            row = res.fetchone()
            res.close()
            return dict(row)

        newRow = yield self.db.pool.do(thd)
        self.assertEqual(newRow, {
            'logid': 201,
            'first_line': 7,
            'last_line': 7,
            'content': line,
            'compressed': 0})

    @defer.inlineCallbacks
    def test_gz_compress_big_chunk(self):
        import zlib
        yield self.insertTestData(self.backgroundData + self.testLogLines)
        line = u'xy' * 10000
        self.db.master.config.logCompressionMethod = "gz"
        self.assertEqual(
            (yield self.db.logs.appendLog(201, line + '\n')),
            (7, 7))

        def thd(conn):
            res = conn.execute(self.db.model.logchunks.select(
                whereclause=self.db.model.logchunks.c.first_line > 6))
            row = res.fetchone()
            res.close()
            return dict(row)

        newRow = yield self.db.pool.do(thd)
        self.assertEqual(newRow, {
            'logid': 201,
            'first_line': 7,
            'last_line': 7,
            'content': zlib.compress(line, 9),
            'compressed': 1})

    @defer.inlineCallbacks
    def test_bz2_compress_big_chunk(self):
        import bz2
        yield self.insertTestData(self.backgroundData + self.testLogLines)
        line = u'xy' * 10000
        self.db.master.config.logCompressionMethod = "bz2"
        self.assertEqual(
            (yield self.db.logs.appendLog(201, line + '\n')),
            (7, 7))

        def thd(conn):
            res = conn.execute(self.db.model.logchunks.select(
                whereclause=self.db.model.logchunks.c.first_line > 6))
            row = res.fetchone()
            res.close()
            return dict(row)

        newRow = yield self.db.pool.do(thd)
        self.assertEqual(newRow, {
            'logid': 201,
            'first_line': 7,
            'last_line': 7,
            'content': bz2.compress(line, 9),
            'compressed': 2})

    @defer.inlineCallbacks
    def test_lz4_compress_big_chunk(self):
        try:
            import lz4
        except ImportError:
            raise unittest.SkipTest("lz4 not installed, skip the test")

        yield self.insertTestData(self.backgroundData + self.testLogLines)
        line = u'xy' * 10000
        self.db.master.config.logCompressionMethod = "lz4"
        self.assertEqual(
            (yield self.db.logs.appendLog(201, line + '\n')),
            (7, 7))

        def thd(conn):
            res = conn.execute(self.db.model.logchunks.select(
                whereclause=self.db.model.logchunks.c.first_line > 6))
            row = res.fetchone()
            res.close()
            return dict(row)

        newRow = yield self.db.pool.do(thd)
        self.assertEqual(newRow, {
            'logid': 201,
            'first_line': 7,
            'last_line': 7,
            'content': lz4.dumps(line),
            'compressed': 3})

    # TODO: test compressing with >64k
    # TODO: test compressing compressed size >64k


class TestFakeDB(unittest.TestCase, Tests):

    def setUp(self):
        self.master = fakemaster.make_master(wantDb=True, testcase=self)
        self.db = self.master.db
        self.db.checkForeignKeys = True
        self.insertTestData = self.db.insertTestData


class TestRealDB(unittest.TestCase,
                 connector_component.ConnectorComponentMixin,
                 RealTests):

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['logs', 'logchunks', 'steps', 'builds', 'builders',
                         'masters', 'buildrequests', 'buildsets',
                         'buildslaves'])

        @d.addCallback
        def finish_setup(_):
            self.db.logs = logs.LogsConnectorComponent(self.db)
        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()
