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
from twisted.trial import unittest

from buildbot.process import log
from buildbot.process import logobserver
from buildbot.test.fake import fakemaster
from buildbot.test.util.misc import TestReactorMixin


class MyLogObserver(logobserver.LogObserver):

    def __init__(self):
        self.obs = []

    def outReceived(self, data):
        self.obs.append(('out', data))

    def errReceived(self, data):
        self.obs.append(('err', data))

    def headerReceived(self, data):
        self.obs.append(('hdr', data))

    def finishReceived(self):
        self.obs.append(('fin',))


class TestLogObserver(TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        self.master = fakemaster.make_master(self, wantData=True)

    @defer.inlineCallbacks
    def test_sequence(self):
        logid = yield self.master.data.updates.addLog(1, 'mine', 's')
        _log = log.Log.new(self.master, 'mine', 's', logid, 'utf-8')
        lo = MyLogObserver()
        lo.setLog(_log)

        yield _log.addStdout('hello\n')
        yield _log.addStderr('cruel\n')
        yield _log.addStdout('world\n')
        yield _log.addStdout('multi\nline\nchunk\n')
        yield _log.addHeader('HDR\n')
        yield _log.finish()

        self.assertEqual(lo.obs, [
            ('out', 'hello\n'),
            ('err', 'cruel\n'),
            ('out', 'world\n'),
            ('out', 'multi\nline\nchunk\n'),
            ('hdr', 'HDR\n'),
            ('fin',),
        ])


class MyLogLineObserver(logobserver.LogLineObserver):

    def __init__(self):
        super().__init__()
        self.obs = []

    def outLineReceived(self, data):
        self.obs.append(('out', data))

    def errLineReceived(self, data):
        self.obs.append(('err', data))

    def headerLineReceived(self, data):
        self.obs.append(('hdr', data))

    def finishReceived(self):
        self.obs.append(('fin',))


class TestLineConsumerLogObesrver(TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        self.master = fakemaster.make_master(self, wantData=True)

    @defer.inlineCallbacks
    def do_test_sequence(self, consumer):
        logid = yield self.master.data.updates.addLog(1, 'mine', 's')
        _log = log.Log.new(self.master, 'mine', 's', logid, 'utf-8')
        lo = logobserver.LineConsumerLogObserver(consumer)
        lo.setLog(_log)

        yield _log.addStdout('hello\n')
        yield _log.addStderr('cruel\n')
        yield _log.addStdout('multi\nline\nchunk\n')
        yield _log.addHeader('H1\nH2\n')
        yield _log.finish()

    @defer.inlineCallbacks
    def test_sequence_finish(self):
        results = []

        def consumer():
            while True:
                try:
                    stream, line = yield
                    results.append((stream, line))
                except GeneratorExit:
                    results.append('finish')
                    raise
        yield self.do_test_sequence(consumer)

        self.assertEqual(results, [
            ('o', 'hello'),
            ('e', 'cruel'),
            ('o', 'multi'),
            ('o', 'line'),
            ('o', 'chunk'),
            ('h', 'H1'),
            ('h', 'H2'),
            'finish',
        ])

    @defer.inlineCallbacks
    def test_sequence_no_finish(self):
        results = []

        def consumer():
            while True:
                stream, line = yield
                results.append((stream, line))
        yield self.do_test_sequence(consumer)

        self.assertEqual(results, [
            ('o', 'hello'),
            ('e', 'cruel'),
            ('o', 'multi'),
            ('o', 'line'),
            ('o', 'chunk'),
            ('h', 'H1'),
            ('h', 'H2'),
        ])


class TestLogLineObserver(TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        self.master = fakemaster.make_master(self, wantData=True)

    @defer.inlineCallbacks
    def test_sequence(self):
        logid = yield self.master.data.updates.addLog(1, 'mine', 's')
        _log = log.Log.new(self.master, 'mine', 's', logid, 'utf-8')
        lo = MyLogLineObserver()
        lo.setLog(_log)

        yield _log.addStdout('hello\n')
        yield _log.addStderr('cruel\n')
        yield _log.addStdout('multi\nline\nchunk\n')
        yield _log.addHeader('H1\nH2\n')
        yield _log.finish()

        self.assertEqual(lo.obs, [
            ('out', 'hello'),
            ('err', 'cruel'),
            ('out', 'multi'),
            ('out', 'line'),
            ('out', 'chunk'),
            ('hdr', 'H1'),
            ('hdr', 'H2'),
            ('fin',),
        ])

    def test_old_setMaxLineLength(self):
        # this method is gone, but used to be documented, so it's still
        # callable.  Just don't fail.
        lo = MyLogLineObserver()
        lo.setMaxLineLength(120939403)


class TestOutputProgressObserver(TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        self.master = fakemaster.make_master(self, wantData=True)

    @defer.inlineCallbacks
    def test_sequence(self):
        logid = yield self.master.data.updates.addLog(1, 'mine', 's')
        _log = log.Log.new(self.master, 'mine', 's', logid, 'utf-8')
        lo = logobserver.OutputProgressObserver('stdio')
        step = mock.Mock()
        lo.setStep(step)
        lo.setLog(_log)

        yield _log.addStdout('hello\n')
        step.setProgress.assert_called_with('stdio', 6)
        yield _log.finish()


class TestBufferObserver(TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        self.master = fakemaster.make_master(self, wantData=True)

    @defer.inlineCallbacks
    def do_test_sequence(self, lo):
        logid = yield self.master.data.updates.addLog(1, 'mine', 's')
        _log = log.Log.new(self.master, 'mine', 's', logid, 'utf-8')
        lo.setLog(_log)

        yield _log.addStdout('hello\n')
        yield _log.addStderr('cruel\n')
        yield _log.addStdout('multi\nline\nchunk\n')
        yield _log.addHeader('H1\nH2\n')
        yield _log.finish()

    @defer.inlineCallbacks
    def test_stdout_only(self):
        lo = logobserver.BufferLogObserver(wantStdout=True, wantStderr=False)
        yield self.do_test_sequence(lo)
        self.assertEqual(lo.getStdout(), 'hello\nmulti\nline\nchunk\n')
        self.assertEqual(lo.getStderr(), '')

    @defer.inlineCallbacks
    def test_both(self):
        lo = logobserver.BufferLogObserver(wantStdout=True, wantStderr=True)
        yield self.do_test_sequence(lo)
        self.assertEqual(lo.getStdout(), 'hello\nmulti\nline\nchunk\n')
        self.assertEqual(lo.getStderr(), 'cruel\n')
