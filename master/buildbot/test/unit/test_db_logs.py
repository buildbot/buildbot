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

import textwrap
from twisted.trial import unittest
from twisted.internet import defer
from buildbot.db import logs
from buildbot.test.util import interfaces, connector_component, validation
from buildbot.test.fake import fakedb, fakemaster

class Tests(interfaces.InterfaceTests):

    backgroundData = [
        fakedb.Buildslave(id=47, name='linux'),
        fakedb.Buildset(id=20),
        fakedb.Builder(id=88, name='b1'),
        fakedb.BuildRequest(id=41, buildsetid=20, buildername='b1'),
        fakedb.Master(id=88),
        fakedb.Build(id=30, buildrequestid=41, number=7, masterid=88,
            builderid=88, buildslaveid=47),
        fakedb.Step(id=101, buildid=30, number=1, name='one'),
        fakedb.Step(id=102, buildid=30, number=2, name='two'),
    ]

    testLogLines = [
        fakedb.Log(id=201, stepid=101, name=u'stdio', complete=0,
            num_lines=7, type=u's'),
        fakedb.LogChunk(logid=201, first_line=0, last_line=1, compressed=0,
            content=textwrap.dedent("""\
                    line zero
                    line 1""")),
        fakedb.LogChunk(logid=201, first_line=2, last_line=4, compressed=0,
            content=textwrap.dedent("""\
                    line TWO
                    line 3
                    line 2**2""")),
        fakedb.LogChunk(logid=201, first_line=5, last_line=5, compressed=0,
            content="another line"),
        fakedb.LogChunk(logid=201, first_line=6, last_line=6, compressed=0,
            content="yet another line"),
    ]

    def checkTestLogLines(self):
        expLines = [ 'line zero', 'line 1', 'line TWO', 'line 3', 'line 2**2',
                      'another line', 'yet another line']
        for first_line in range(0, 7):
            for last_line in range(first_line, 7):
                got_lines = yield self.db.logs.getLogLines(201,
                                        first_line, last_line)
                self.assertEqual(got_lines,
                        "\n".join(expLines[first_line:last_line+1]+"\n"))
        # check overflow
        self.assertEqual((yield self.db.logs.getLogLines(201, 5, 20)),
                        "\n".join(expLines[5:7]+"\n"))

    # signature tests

    def test_signature_getLog(self):
        @self.assertArgSpecMatches(self.db.logs.getLog)
        def getLog(self, logid):
            pass

    def test_signature_getLogByName(self):
        @self.assertArgSpecMatches(self.db.logs.getLogByName)
        def getLogByName(self, stepid, name):
            pass

    def test_signature_getLogs(self):
        @self.assertArgSpecMatches(self.db.logs.getLogs)
        def getLogs(self, stepid):
            pass

    def test_signature_getLogLines(self):
        @self.assertArgSpecMatches(self.db.logs.getLogLines)
        def getLogLines(self, logid, first_line, last_line):
            pass

    def test_signature_addLog(self):
        @self.assertArgSpecMatches(self.db.logs.addLog)
        def addLog(self, stepid, name, type):
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
            fakedb.Log(id=201, stepid=101, name=u'stdio', complete=0,
                num_lines=200, type=u's'),
        ])
        logdict = yield self.db.logs.getLog(201)
        validation.verifyDbDict(self, 'logdict', logdict)
        self.assertEqual(logdict, {
            'id': 201,
            'stepid': 101,
            'name': u'stdio',
            'complete': False,
            'num_lines': 200,
            'type': 's',
        })

    @defer.inlineCallbacks
    def test_getLog_missing(self):
        logdict = yield self.db.logs.getLog(201)
        self.assertEqual(logdict, None)

    @defer.inlineCallbacks
    def test_getLogByName(self):
        yield self.insertTestData(self.backgroundData + [
            fakedb.Log(id=201, stepid=101, name=u'stdio', complete=0,
                num_lines=200, type=u's'),
            fakedb.Log(id=202, stepid=101, name=u'debug_log',
                complete=1, num_lines=200, type=u's'),
        ])
        logdict = yield self.db.logs.getLogByName(101, u'debug_log')
        validation.verifyDbDict(self, 'logdict', logdict)
        self.assertEqual(logdict['id'], 202)

    @defer.inlineCallbacks
    def test_getLogByName_missing(self):
        yield self.insertTestData(self.backgroundData + [
            fakedb.Log(id=201, stepid=101, name=u'stdio', complete=0,
                num_lines=200, type=u's'),
        ])
        logdict = yield self.db.logs.getLogByName(102, u'stdio')
        self.assertEqual(logdict, None)

    @defer.inlineCallbacks
    def test_getLogs(self):
        yield self.insertTestData(self.backgroundData + [
            fakedb.Log(id=201, stepid=101, name=u'stdio', complete=0,
                num_lines=200, type=u's'),
            fakedb.Log(id=202, stepid=101, name=u'debug_log', complete=1,
                num_lines=300, type=u't'),
            fakedb.Log(id=203, stepid=102, name=u'stdio', complete=0,
                num_lines=200, type=u's'),
        ])
        logdicts = yield self.db.logs.getLogs(101)
        for logdict in logdicts:
            validation.verifyDbDict(self, 'logdict', logdict)
        self.assertEqual(sorted([ld['id'] for ld in logdicts]), [201, 202])

    @defer.inlineCallbacks
    def test_getLogLines(self):
        yield self.insertTestData(self.backgroundData + self.testLogLines)
        self.checkTestLogLines()

        # check line number reversal
        self.assertEqual((yield self.db.logs.getLogLines(201, 6, 3)), '')

    @defer.inlineCallbacks
    def test_getLogLines_empty(self):
        yield self.insertTestData(self.backgroundData + [
            fakedb.Log(id=201, stepid=101, name=u'stdio', complete=0,
                num_lines=200, type=u's'),
        ])
        self.assertEqual((yield self.db.logs.getLogLines(201, 9, 99)), '')
        self.assertEqual((yield self.db.logs.getLogLines(999, 9, 99)), '')

    @defer.inlineCallbacks
    def test_addLog_getLog(self):
        yield self.insertTestData(self.backgroundData)
        logid = yield self.db.logs.addLog(stepid=101, name=u'config_log',
                                          type=u't')
        logdict = yield self.db.logs.getLog(logid)
        validation.verifyDbDict(self, 'logdict', logdict)
        self.assertEqual(logdict, {
            'id': logid,
            'stepid': 101,
            'name': u'config_log',
            'complete': False,
            'num_lines': 0,
            'type': 't',
        })

    @defer.inlineCallbacks
    def test_appendLog_getLogLines(self):
        yield self.insertTestData(self.backgroundData + self.testLogLines)
        yield self.db.logs.appendLog(201, u'abc\ndef\n')
        self.assertEqual((yield self.db.logs.getLogLines(201, 6, 7)),
                        u"yet another line\nabc\n")
        self.assertEqual((yield self.db.logs.getLogLines(201, 7, 8)),
                        u"abc\ndef\n")
        self.assertEqual((yield self.db.logs.getLogLines(201, 8, 8)),
                        u"def\n")

    @defer.inlineCallbacks
    def test_compressLog(self):
        yield self.insertTestData(self.backgroundData + self.testLogLines)
        yield self.db.logs.compressLog(201)
        # test log lines should still be readable just the same
        self.checkTestLogLines()

    @defer.inlineCallbacks
    def test_addLogLines_big_chunk(self):
        yield self.insertTestData(self.backgroundData + self.testLogLines)
        yield self.db.logs.appendLog(201, u'abc\n' * 20000) # 80k
        lines = yield self.db.logs.getLogLines(201, 7, 50000)
        self.assertEqual(len(lines), 80000)
        self.assertEqual(lines, (u'abc\n' * 20000))

    @defer.inlineCallbacks
    def test_addLogLines_big_chunk_big_lines(self):
        yield self.insertTestData(self.backgroundData + self.testLogLines)
        line = u'x' * 33000 + '\n'
        yield self.db.logs.appendLog(201, line*3)
        lines = yield self.db.logs.getLogLines(201, 7, 100)
        self.assertEqual(len(lines), 99003)
        self.assertEqual(lines, (line*3))


class RealTests(Tests):

    @defer.inlineCallbacks
    def test_addLogLines_db(self):
        yield self.insertTestData(self.backgroundData + self.testLogLines)
        yield self.db.logs.appendLog(201, u'abc\ndef\nghi\njkl\n')
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
        yield self.db.logs.appendLog(201, line*3)
        for lineno in 7, 8, 9:
            line = yield self.db.logs.getLogLines(201, lineno, lineno)
            self.assertEqual(len(line), 65537)

    def test_splitBigChunk_unicode_misalignment(self):
        unaligned = (u'a ' + u'\N{SNOWMAN}' * 30000 + '\n').encode('utf-8')
        # the first 65536 bytes of that line are not valid utf-8
        self.assertRaises(UnicodeDecodeError, lambda :
                unaligned[:65536].decode('utf-8'))
        chunk, remainder = self.db.logs._splitBigChunk(unaligned, 1)
        # see that it was truncated by two bytes, and now properly decodes
        self.assertEqual(len(chunk), 65534)
        chunk.decode('utf-8')

    # TODO: test compressing with >64k
    # TODO: test compressing compressed size >64k


class TestFakeDB(unittest.TestCase, Tests):

    def setUp(self):
        self.master = fakemaster.make_master()
        self.db = fakedb.FakeDBConnector(self.master, self)
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
