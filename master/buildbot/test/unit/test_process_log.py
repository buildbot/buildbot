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
from buildbot.process import log
from buildbot.status import logfile
from buildbot.test.fake import fakemaster
from buildbot.test.util import interfaces
from buildbot.test.fake import logfile as fakelogfile
from twisted.internet import defer
from twisted.trial import unittest


class Tests(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self,
                                             wantData=True)

    @defer.inlineCallbacks
    def makeLog(self, type):
        logid = yield self.master.data.updates.newLog(stepid=27,
                                                      name=u'testlog', type=unicode(type))
        defer.returnValue(log.Log.new(self.master, u'testlog', type, logid))

    @defer.inlineCallbacks
    def test_creation(self):
        for type in 'ths':
            yield self.makeLog(type)

    @defer.inlineCallbacks
    def test_updates_plain(self):
        l = yield self.makeLog('t')

        l.addContent(u'hello\n')
        l.addContent(u'hello ')
        l.addContent(u'cruel ')
        l.addContent(u'world\nthis is a second line')  # unfinished
        l.finish()

        self.assertEqual(self.master.data.updates.logs[l.logid], [
            u'hello\n',
            u'hello cruel world\n',
            u'this is a second line\n',
            None])

    @defer.inlineCallbacks
    def test_subscription_plain(self):
        l = yield self.makeLog('t')
        calls = []
        l.subscribe(lambda stream, content: calls.append((stream, content)), False)
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
        l.subscribe(sub_fn, False)
        l.unsubscribe(sub_fn)
        yield l.finish()
        sub_fn.assert_not_called()

    @defer.inlineCallbacks
    def test_subscription_stream(self):
        l = yield self.makeLog('s')
        calls = []
        l.subscribe(lambda stream, content: calls.append((stream, content)), False)
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

        self.assertEqual(self.master.data.updates.logs[l.logid], [
            'ohello\n',
            'eoh noes!\n',
            'ohello cruel world\n',
            'ebad things!\n',
            None])

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


class TestInterface(interfaces.InterfaceTests):

    # for compatibility between old-style and new-style tests, both
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
        def subscribe(self, receiver, catchup):
            pass

    def test_signature_unsubscribe(self):
        @self.assertArgSpecMatches(self.log.unsubscribe)
        def unsubscribe(self, receiver):
            pass

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


class TestStatusInterface(unittest.TestCase, TestInterface):

    def setUp(self):
        step = mock.Mock(name='step')
        step.build.builder.basedir = '.'
        self.log = logfile.LogFile(step, 'stdio', 'stdio')


class TestProcessInterface(unittest.TestCase, TestInterface):

    def setUp(self):
        self.log = log.StreamLog(mock.Mock(name='master'), 'stdio', 's', 101)


class TestFakeLogFile(unittest.TestCase, TestInterface):

    def setUp(self):
        step = mock.Mock(name='fake step')
        step.logobservers = []
        self.log = fakelogfile.FakeLogFile('stdio', step)

    # mark these TODO for the fake, for the moment -- leaving these methods in
    # place lets the tests pass until all of the built-in steps are rewritten
    # to use LogObservers, etc.

    def test_signature_hasContents_removed(self):
        TestInterface.test_signature_hasContents_removed(self)
    test_signature_hasContents_removed.todo = "not removed yet"
    def test_signature_getText_removed(self):
        TestInterface.test_signature_getText_removed(self)
    test_signature_getText_removed.todo = "not removed yet"
    def test_signature_readlines_removed(self):
        TestInterface.test_signature_readlines_removed(self)
    test_signature_readlines_removed.todo = "not removed yet"
    def test_signature_getTextWithHeaders_removed(self):
        TestInterface.test_signature_getTextWithHeaders_removed(self)
    test_signature_getTextWithHeaders_removed.todo = "not removed yet"
    def test_signature_getChunks_removed(self):
        TestInterface.test_signature_getChunks_removed(self)
    test_signature_getChunks_removed.todo = "not removed yet"
