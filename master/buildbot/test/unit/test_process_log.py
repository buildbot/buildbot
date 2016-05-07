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
import mock
from twisted.internet import defer
from twisted.internet import reactor
from twisted.trial import unittest

from buildbot.process import log
from buildbot.test.fake import logfile as fakelogfile
from buildbot.test.fake import fakemaster
from buildbot.test.util import interfaces


class Tests(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self,
                                             wantData=True)

    @defer.inlineCallbacks
    def makeLog(self, type, logEncoding='utf-8'):
        logid = yield self.master.data.updates.addLog(
            stepid=27, name=u'testlog', type=unicode(type))
        defer.returnValue(log.Log.new(self.master, u'testlog', type,
                                      logid, logEncoding))

    @defer.inlineCallbacks
    def test_creation(self):
        for type in 'ths':
            yield self.makeLog(type)

    def test_logDecodeFunctionFromConfig(self):
        otilde = u'\u00f5'
        otilde_utf8 = otilde.encode('utf-8')
        otilde_latin1 = otilde.encode('latin1')
        invalid_utf8 = '\xff'
        replacement = u'\ufffd'

        f = log.Log._decoderFromString('latin-1')
        self.assertEqual(f(otilde_latin1), otilde)

        f = log.Log._decoderFromString('utf-8')
        self.assertEqual(f(otilde_utf8), otilde)
        self.assertEqual(f(invalid_utf8), replacement)

        f = log.Log._decoderFromString(lambda s: unicode(s[::-1]))
        self.assertEqual(f('abc'), u'cba')

    @defer.inlineCallbacks
    def test_updates_plain(self):
        l = yield self.makeLog('t')

        l.addContent(u'hello\n')
        l.addContent(u'hello ')
        l.addContent(u'cruel ')
        l.addContent(u'world\nthis is a second line')  # unfinished
        l.finish()

        self.assertEqual(self.master.data.updates.logs[l.logid], {
            'content': [u'hello\n', u'hello cruel world\n',
                        u'this is a second line\n'],
            'finished': True,
            'type': u't',
            'name': u'testlog',
        })

    @defer.inlineCallbacks
    def test_updates_different_encoding(self):
        l = yield self.makeLog('t', logEncoding='latin-1')
        l.addContent('$ and \xa2\n')  # 0xa2 is latin-1 encoding for CENT SIGN
        l.finish()

        self.assertEqual(self.master.data.updates.logs[l.logid]['content'],
                         [u'$ and \N{CENT SIGN}\n'])

    @defer.inlineCallbacks
    def test_updates_unicode_input(self):
        l = yield self.makeLog('t', logEncoding='something-invalid')
        l.addContent(u'\N{SNOWMAN}\n')
        l.finish()

        self.assertEqual(self.master.data.updates.logs[l.logid]['content'],
                         [u'\N{SNOWMAN}\n'])

    @defer.inlineCallbacks
    def test_subscription_plain(self):
        l = yield self.makeLog('t')
        calls = []
        l.subscribe(lambda stream, content: calls.append((stream, content)))
        self.assertEqual(calls, [])

        yield l.addContent(u'hello\n')
        self.assertEqual(calls, [(None, u'hello\n')])
        calls = []

        yield l.addContent(u'hello ')
        self.assertEqual(calls, [])
        yield l.addContent(u'cruel ')
        self.assertEqual(calls, [])
        yield l.addContent(u'world\nthis is a second line\n')
        self.assertEqual(calls, [
            (None, u'hello cruel world\nthis is a second line\n')])
        calls = []

        yield l.finish()
        self.assertEqual(calls, [(None, None)])

    @defer.inlineCallbacks
    def test_subscription_unsubscribe(self):
        l = yield self.makeLog('t')
        sub_fn = mock.Mock()
        sub = l.subscribe(sub_fn)
        sub.unsubscribe()
        yield l.finish()
        sub_fn.assert_not_called()

    @defer.inlineCallbacks
    def test_subscription_stream(self):
        l = yield self.makeLog('s')
        calls = []
        l.subscribe(lambda stream, content: calls.append((stream, content)))
        self.assertEqual(calls, [])

        yield l.addStdout(u'hello\n')
        self.assertEqual(calls, [('o', u'hello\n')])
        calls = []

        yield l.addStdout(u'hello ')
        self.assertEqual(calls, [])
        yield l.addStdout(u'cruel ')
        self.assertEqual(calls, [])
        yield l.addStderr(u'!!\n')
        self.assertEqual(calls, [('e', '!!\n')])
        calls = []

        yield l.addHeader(u'**\n')
        self.assertEqual(calls, [('h', '**\n')])
        calls = []

        yield l.addStdout(u'world\nthis is a second line')  # unfinished
        self.assertEqual(calls, [
            ('o', u'hello cruel world\n')])
        calls = []

        yield l.finish()
        self.assertEqual(calls, [
            ('o', u'this is a second line\n'),
            (None, None)])

    @defer.inlineCallbacks
    def test_updates_stream(self):
        l = yield self.makeLog('s')

        l.addStdout(u'hello\n')
        l.addStdout(u'hello ')
        l.addStderr(u'oh noes!\n')
        l.addStdout(u'cruel world\n')
        l.addStderr(u'bad things!')  # unfinished
        l.finish()

        self.assertEqual(self.master.data.updates.logs[l.logid], {
            'content': [u'ohello\n', u'eoh noes!\n', u'ohello cruel world\n',
                        u'ebad things!\n'],
            'finished': True,
            'name': u'testlog',
            'type': u's',
        })

    @defer.inlineCallbacks
    def test_isFinished(self):
        l = yield self.makeLog('s')
        self.assertFalse(l.isFinished())
        yield l.finish()
        self.assertTrue(l.isFinished())

    @defer.inlineCallbacks
    def test_waitUntilFinished(self):
        l = yield self.makeLog('s')
        d = l.waitUntilFinished()
        self.assertFalse(d.called)
        yield l.finish()
        self.assertTrue(d.called)


class InterfaceTests(interfaces.InterfaceTests):

    # for compatibility between old-style and new-style steps, both
    # buildbot.status.logfile.LogFile and buildbot.process.log.StreamLog must
    # meet this interace, at least until support for old-style steps is
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

    # IStatusLog

    def test_signature_getName(self):
        @self.assertArgSpecMatches(self.log.getName)
        def getName(self):
            pass

    def test_getName(self):
        self.assertEqual(self.log.getName(), 'stdio')

    def test_signature_isFinished(self):
        @self.assertArgSpecMatches(self.log.isFinished)
        def isFinished(self):
            pass

    def test_signature_waitUntilFinished(self):
        @self.assertArgSpecMatches(self.log.waitUntilFinished)
        def waitUntilFinished(self):
            pass

    def test_signature_subscribe(self):
        @self.assertArgSpecMatches(self.log.subscribe)
        def subscribe(self, callback):
            pass

    def test_signature_unsubscribe(self):
        # method has been removed
        self.failIf(hasattr(self.log, 'unsubscribe'))

    def test_signature_getStep_removed(self):
        self.failIf(hasattr(self.log, 'getStep'))

    def test_signature_subscribeConsumer_removed(self):
        self.failIf(hasattr(self.log, 'subscribeConsumer'))

    def test_signature_hasContents_removed(self):
        self.failIf(hasattr(self.log, 'hasContents'))

    def test_signature_getText_removed(self):
        self.failIf(hasattr(self.log, 'getText'))

    def test_signature_readlines_removed(self):
        self.failIf(hasattr(self.log, 'readlines'))

    def test_signature_getTextWithHeaders_removed(self):
        self.failIf(hasattr(self.log, 'getTextWithHeaders'))

    def test_signature_getChunks_removed(self):
        self.failIf(hasattr(self.log, 'getChunks'))


class TestProcessItfc(unittest.TestCase, InterfaceTests):

    def setUp(self):
        self.log = log.StreamLog(mock.Mock(name='master'), 'stdio', 's',
                                 101, unicode)


class TestFakeLogFile(unittest.TestCase, InterfaceTests):

    def setUp(self):
        step = mock.Mock(name='fake step')
        step.logobservers = []
        self.log = fakelogfile.FakeLogFile('stdio', step)


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
            log.StreamLog(mock.Mock(name='master'), 'stdio', 's',
                          101, unicode))

        correct_error_raised = False
        try:
            yield tested_log.addStdout('msg\n')
        except Exception as e:
            correct_error_raised = 'DB has gone away' in str(e)
        self.assertTrue(correct_error_raised)

    @defer.inlineCallbacks
    def testErrorOnPlainLog(self):
        tested_log = self.instrumentTestedLoggerForError(
            log.PlainLog(mock.Mock(name='master'), 'stdio', 's',
                         101, unicode))
        correct_error_raised = False
        try:
            yield tested_log.addContent('msg\n')
        except Exception as e:
            correct_error_raised = 'DB has gone away' in str(e)
        self.assertTrue(correct_error_raised)

    @defer.inlineCallbacks
    def testErrorOnPlainLogFlush(self):
        tested_log = self.instrumentTestedLoggerForError(
            log.PlainLog(mock.Mock(name='master'), 'stdio', 's',
                         101, unicode))
        correct_error_raised = False
        try:
            yield tested_log.addContent('msg')
            yield tested_log.finish()
        except Exception as e:
            correct_error_raised = 'DB has gone away' in str(e)
        self.assertTrue(correct_error_raised)
