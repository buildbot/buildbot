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

from unittest import mock

from twisted.internet import defer
from twisted.internet import reactor
from twisted.trial import unittest

from buildbot.process import log
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.fake import logfile as fakelogfile
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import interfaces


class Tests(TestReactorMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantData=True)

        master_id = fakedb.FakeDBConnector.MASTER_ID
        self.master.db.insert_test_data([
            fakedb.Master(id=master_id),
            fakedb.Worker(id=47),
            fakedb.Buildset(id=20),
            fakedb.Builder(id=80, name='b1'),
            fakedb.BuildRequest(id=41, buildsetid=20, builderid=80),
            fakedb.Build(
                id=30, buildrequestid=41, number=7, masterid=master_id, builderid=80, workerid=47
            ),
            fakedb.Step(id=27, buildid=30, number=1, name='make'),
        ])

    @defer.inlineCallbacks
    def makeLog(self, type, logEncoding='utf-8'):
        logid = yield self.master.data.updates.addLog(stepid=27, name='testlog', type=str(type))
        return log.Log.new(self.master, 'testlog', type, logid, logEncoding)

    @defer.inlineCallbacks
    def test_creation(self):
        for type in 'ths':
            yield self.makeLog(type)

    def test_logDecodeFunctionFromConfig(self):
        otilde = '\u00f5'
        otilde_utf8 = otilde.encode('utf-8')
        otilde_latin1 = otilde.encode('latin1')
        invalid_utf8 = b'\xff'
        replacement = '\ufffd'

        f = log.Log._decoderFromString('latin-1')
        self.assertEqual(f(otilde_latin1), otilde)

        f = log.Log._decoderFromString('utf-8')
        self.assertEqual(f(otilde_utf8), otilde)
        self.assertEqual(f(invalid_utf8), replacement)

        f = log.Log._decoderFromString(lambda s: str(s[::-1]))
        self.assertEqual(f('abc'), 'cba')

    @defer.inlineCallbacks
    def test_updates_plain(self):
        _log = yield self.makeLog('t')

        _log.addContent('hello\n')
        _log.addContent('hello ')
        _log.addContent('cruel ')
        _log.addContent('world\nthis is a second line')  # unfinished
        yield _log.finish()

        log_data = yield self.master.data.get(('logs', _log.logid))
        log_content = yield self.master.data.get(('logs', _log.logid, 'contents'))

        self.assertEqual(
            log_data,
            {
                'complete': True,
                'logid': 1,
                'name': 'testlog',
                'num_lines': 3,
                'slug': 'testlog',
                'stepid': 27,
                'type': 't',
            },
        )
        self.assertEqual(
            log_content['content'], 'hello\nhello cruel world\nthis is a second line\n'
        )

    @defer.inlineCallbacks
    def test_updates_different_encoding(self):
        _log = yield self.makeLog('t', logEncoding='latin-1')
        # 0xa2 is latin-1 encoding for CENT SIGN
        _log.addContent('$ and \xa2\n')
        yield _log.finish()

        log_content = yield self.master.data.get(('logs', _log.logid, 'contents'))
        self.assertEqual(log_content['content'], '$ and \N{CENT SIGN}\n')

    @defer.inlineCallbacks
    def test_updates_unicode_input(self):
        _log = yield self.makeLog('t', logEncoding='something-invalid')
        _log.addContent('\N{SNOWMAN}\n')
        yield _log.finish()

        log_content = yield self.master.data.get(('logs', _log.logid, 'contents'))
        self.assertEqual(log_content['content'], '\N{SNOWMAN}\n')

    @defer.inlineCallbacks
    def test_subscription_plain(self):
        _log = yield self.makeLog('t')
        calls = []
        _log.subscribe(lambda stream, content: calls.append((stream, content)))
        self.assertEqual(calls, [])

        yield _log.addContent('hello\n')
        self.assertEqual(calls, [(None, 'hello\n')])
        calls = []

        yield _log.addContent('hello ')
        self.assertEqual(calls, [])
        yield _log.addContent('cruel ')
        self.assertEqual(calls, [])
        yield _log.addContent('world\nthis is a second line\n')
        self.assertEqual(calls, [(None, 'hello cruel world\nthis is a second line\n')])
        calls = []

        yield _log.finish()
        self.assertEqual(calls, [(None, None)])

    @defer.inlineCallbacks
    def test_subscription_unsubscribe(self):
        _log = yield self.makeLog('t')
        sub_fn = mock.Mock()
        sub = _log.subscribe(sub_fn)
        sub.unsubscribe()
        yield _log.finish()
        sub_fn.assert_not_called()

    @defer.inlineCallbacks
    def test_subscription_stream(self):
        _log = yield self.makeLog('s')
        calls = []
        _log.subscribe(lambda stream, content: calls.append((stream, content)))
        self.assertEqual(calls, [])

        yield _log.addStdout('hello\n')
        self.assertEqual(calls, [('o', 'hello\n')])
        calls = []

        yield _log.addStdout('hello ')
        self.assertEqual(calls, [])
        yield _log.addStdout('cruel ')
        self.assertEqual(calls, [])
        yield _log.addStderr('!!\n')
        self.assertEqual(calls, [('e', '!!\n')])
        calls = []

        yield _log.addHeader('**\n')
        self.assertEqual(calls, [('h', '**\n')])
        calls = []

        yield _log.addStdout('world\nthis is a second line')  # unfinished
        self.assertEqual(calls, [('o', 'hello cruel world\n')])
        calls = []

        yield _log.finish()
        self.assertEqual(calls, [('o', 'this is a second line\n'), (None, None)])

    @defer.inlineCallbacks
    def test_updates_stream(self):
        _log = yield self.makeLog('s')

        _log.addStdout('out1\n')
        _log.addStdout('out2 ')
        _log.addStderr('err2\n')
        _log.addStdout('out3\n')
        _log.addStderr('err3')  # unfinished
        yield _log.finish()

        log_data = yield self.master.data.get(('logs', _log.logid))
        log_content = yield self.master.data.get(('logs', _log.logid, 'contents'))

        self.assertEqual(
            log_data,
            {
                'complete': True,
                'logid': 1,
                'name': 'testlog',
                'num_lines': 4,
                'slug': 'testlog',
                'stepid': 27,
                'type': 's',
            },
        )
        self.assertEqual(log_content['content'], 'oout1\neerr2\noout2 out3\neerr3\n')

    @defer.inlineCallbacks
    def test_updates_flush(self):
        _log = yield self.makeLog('s')

        _log.addStdout('out1\n')
        _log.addStdout('out2 ')
        _log.addStderr('err2\n')
        _log.addStdout('out3')
        _log.addStderr('err3')  # unfinished
        yield _log.flush()

        log_data = yield self.master.data.get(('logs', _log.logid))
        log_content = yield self.master.data.get(('logs', _log.logid, 'contents'))

        self.assertEqual(
            log_data,
            {
                'complete': False,
                'logid': 1,
                'name': 'testlog',
                'num_lines': 4,
                'slug': 'testlog',
                'stepid': 27,
                'type': 's',
            },
        )
        self.assertEqual(log_content['content'], 'oout1\neerr2\noout2 out3\neerr3\n')

    @defer.inlineCallbacks
    def test_unyielded_finish(self):
        _log = yield self.makeLog('s')
        _log.finish()
        with self.assertRaises(AssertionError):
            yield _log.finish()


class InterfaceTests(interfaces.InterfaceTests):
    # for compatibility between old-style and new-style steps, both
    # buildbot.status.logfile.LogFile and buildbot.process.log.StreamLog must
    # meet this interface, at least until support for old-style steps is
    # removed.

    # ILogFile

    def test_signature_addStdout(self):
        @self.assertArgSpecMatches(self.log.addStdout)
        def addStdout(self, text):
            pass

    def test_signature_addStderr(self):
        @self.assertArgSpecMatches(self.log.addStderr)
        def addStderr(self, text):
            pass

    def test_signature_addHeader(self):
        @self.assertArgSpecMatches(self.log.addHeader)
        def addHeader(self, text):
            pass

    def test_signature_finish(self):
        @self.assertArgSpecMatches(self.log.finish)
        def finish(self):
            pass

    def test_signature_getName(self):
        @self.assertArgSpecMatches(self.log.getName)
        def getName(self):
            pass

    def test_getName(self):
        self.assertEqual(self.log.getName(), 'stdio')

    def test_signature_subscribe(self):
        @self.assertArgSpecMatches(self.log.subscribe)
        def subscribe(self, callback):
            pass

    def test_signature_unsubscribe(self):
        # method has been removed
        self.assertFalse(hasattr(self.log, 'unsubscribe'))

    def test_signature_getStep_removed(self):
        self.assertFalse(hasattr(self.log, 'getStep'))

    def test_signature_subscribeConsumer_removed(self):
        self.assertFalse(hasattr(self.log, 'subscribeConsumer'))

    def test_signature_hasContents_removed(self):
        self.assertFalse(hasattr(self.log, 'hasContents'))

    def test_signature_getText_removed(self):
        self.assertFalse(hasattr(self.log, 'getText'))

    def test_signature_readlines_removed(self):
        self.assertFalse(hasattr(self.log, 'readlines'))

    def test_signature_getTextWithHeaders_removed(self):
        self.assertFalse(hasattr(self.log, 'getTextWithHeaders'))

    def test_signature_getChunks_removed(self):
        self.assertFalse(hasattr(self.log, 'getChunks'))


class TestProcessItfc(unittest.TestCase, InterfaceTests):
    def setUp(self):
        self.log = log.StreamLog(mock.Mock(name='master'), 'stdio', 's', 101, str)


class TestFakeLogFile(unittest.TestCase, InterfaceTests):
    def setUp(self):
        self.log = fakelogfile.FakeLogFile('stdio')


class TestErrorRaised(unittest.TestCase):
    def instrumentTestedLoggerForError(self, testedLog):
        def addRawLines(msg):
            d = defer.Deferred()

            def raiseError(_):
                d.errback(RuntimeError('DB has gone away'))

            reactor.callLater(10 ** (-6), raiseError, None)
            return d

        self.patch(testedLog, 'addRawLines', addRawLines)
        return testedLog

    @defer.inlineCallbacks
    def testErrorOnStreamLog(self):
        tested_log = self.instrumentTestedLoggerForError(
            log.StreamLog(mock.Mock(name='master'), 'stdio', 's', 101, str)
        )

        correct_error_raised = False
        try:
            yield tested_log.addStdout('msg\n')
        except Exception as e:
            correct_error_raised = 'DB has gone away' in str(e)
        self.assertTrue(correct_error_raised)

    @defer.inlineCallbacks
    def testErrorOnPlainLog(self):
        tested_log = self.instrumentTestedLoggerForError(
            log.PlainLog(mock.Mock(name='master'), 'stdio', 's', 101, str)
        )
        correct_error_raised = False
        try:
            yield tested_log.addContent('msg\n')
        except Exception as e:
            correct_error_raised = 'DB has gone away' in str(e)
        self.assertTrue(correct_error_raised)

    @defer.inlineCallbacks
    def testErrorOnPlainLogFlush(self):
        tested_log = self.instrumentTestedLoggerForError(
            log.PlainLog(mock.Mock(name='master'), 'stdio', 's', 101, str)
        )
        correct_error_raised = False
        try:
            yield tested_log.addContent('msg')
            yield tested_log.finish()
        except Exception as e:
            correct_error_raised = 'DB has gone away' in str(e)
        self.assertTrue(correct_error_raised)
