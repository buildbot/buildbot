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

from twisted.trial import unittest

from buildbot.process import log
from buildbot.process import logobserver
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin


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
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self, wantData=True)

    async def test_sequence(self):
        logid = await self.master.data.updates.addLog(1, 'mine', 's')
        _log = log.Log.new(self.master, 'mine', 's', logid, 'utf-8')
        lo = MyLogObserver()
        lo.setLog(_log)

        await _log.addStdout('hello\n')
        await _log.addStderr('cruel\n')
        await _log.addStdout('world\n')
        await _log.addStdout('multi\nline\nchunk\n')
        await _log.addHeader('HDR\n')
        await _log.finish()

        self.assertEqual(
            lo.obs,
            [
                ('out', 'hello\n'),
                ('err', 'cruel\n'),
                ('out', 'world\n'),
                ('out', 'multi\nline\nchunk\n'),
                ('hdr', 'HDR\n'),
                ('fin',),
            ],
        )


class MyLogLineObserver(logobserver.LogLineObserver):
    def __init__(self):
        super().__init__()
        self.obs = []

    def outLineReceived(self, line):
        self.obs.append(('out', line))

    def errLineReceived(self, line):
        self.obs.append(('err', line))

    def headerLineReceived(self, line):
        self.obs.append(('hdr', line))

    def finishReceived(self):
        self.obs.append(('fin',))


class TestLineConsumerLogObesrver(TestReactorMixin, unittest.TestCase):
    def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self, wantData=True)

    async def do_test_sequence(self, consumer):
        logid = await self.master.data.updates.addLog(1, 'mine', 's')
        _log = log.Log.new(self.master, 'mine', 's', logid, 'utf-8')
        lo = logobserver.LineConsumerLogObserver(consumer)
        lo.setLog(_log)

        await _log.addStdout('hello\n')
        await _log.addStderr('cruel\n')
        await _log.addStdout('multi\nline\nchunk\n')
        await _log.addHeader('H1\nH2\n')
        await _log.finish()

    async def test_sequence_finish(self):
        results = []

        def consumer():
            while True:
                try:
                    stream, line = yield
                    results.append((stream, line))
                except GeneratorExit:
                    results.append('finish')
                    raise

        await self.do_test_sequence(consumer)

        self.assertEqual(
            results,
            [
                ('o', 'hello'),
                ('e', 'cruel'),
                ('o', 'multi'),
                ('o', 'line'),
                ('o', 'chunk'),
                ('h', 'H1'),
                ('h', 'H2'),
                'finish',
            ],
        )

    async def test_sequence_no_finish(self):
        results = []

        def consumer():
            while True:
                stream, line = yield
                results.append((stream, line))

        await self.do_test_sequence(consumer)

        self.assertEqual(
            results,
            [
                ('o', 'hello'),
                ('e', 'cruel'),
                ('o', 'multi'),
                ('o', 'line'),
                ('o', 'chunk'),
                ('h', 'H1'),
                ('h', 'H2'),
            ],
        )


class TestLogLineObserver(TestReactorMixin, unittest.TestCase):
    def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self, wantData=True)

    async def test_sequence(self):
        logid = await self.master.data.updates.addLog(1, 'mine', 's')
        _log = log.Log.new(self.master, 'mine', 's', logid, 'utf-8')
        lo = MyLogLineObserver()
        lo.setLog(_log)

        await _log.addStdout('hello\n')
        await _log.addStderr('cruel\n')
        await _log.addStdout('multi\nline\nchunk\n')
        await _log.addHeader('H1\nH2\n')
        await _log.finish()

        self.assertEqual(
            lo.obs,
            [
                ('out', 'hello'),
                ('err', 'cruel'),
                ('out', 'multi'),
                ('out', 'line'),
                ('out', 'chunk'),
                ('hdr', 'H1'),
                ('hdr', 'H2'),
                ('fin',),
            ],
        )

    def test_old_setMaxLineLength(self):
        # this method is gone, but used to be documented, so it's still
        # callable.  Just don't fail.
        lo = MyLogLineObserver()
        lo.setMaxLineLength(120939403)


class TestOutputProgressObserver(TestReactorMixin, unittest.TestCase):
    def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self, wantData=True)

    async def test_sequence(self):
        logid = await self.master.data.updates.addLog(1, 'mine', 's')
        _log = log.Log.new(self.master, 'mine', 's', logid, 'utf-8')
        lo = logobserver.OutputProgressObserver('stdio')
        step = mock.Mock()
        lo.setStep(step)
        lo.setLog(_log)

        await _log.addStdout('hello\n')
        step.setProgress.assert_called_with('stdio', 6)
        await _log.finish()


class TestBufferObserver(TestReactorMixin, unittest.TestCase):
    def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self, wantData=True)

    async def do_test_sequence(self, lo):
        logid = await self.master.data.updates.addLog(1, 'mine', 's')
        _log = log.Log.new(self.master, 'mine', 's', logid, 'utf-8')
        lo.setLog(_log)

        await _log.addStdout('hello\n')
        await _log.addStderr('cruel\n')
        await _log.addStdout('multi\nline\nchunk\n')
        await _log.addHeader('H1\nH2\n')
        await _log.finish()

    async def test_stdout_only(self):
        lo = logobserver.BufferLogObserver(wantStdout=True, wantStderr=False)
        await self.do_test_sequence(lo)
        self.assertEqual(lo.getStdout(), 'hello\nmulti\nline\nchunk\n')
        self.assertEqual(lo.getStderr(), '')

    async def test_both(self):
        lo = logobserver.BufferLogObserver(wantStdout=True, wantStderr=True)
        await self.do_test_sequence(lo)
        self.assertEqual(lo.getStdout(), 'hello\nmulti\nline\nchunk\n')
        self.assertEqual(lo.getStderr(), 'cruel\n')
