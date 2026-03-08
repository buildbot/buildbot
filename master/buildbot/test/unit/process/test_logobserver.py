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


from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process import log
from buildbot.process import logobserver
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Generator

    from buildbot.process.logobserver import BufferLogObserver
    from buildbot.util.twisted import InlineCallbacksType


class MyLogObserver(logobserver.LogObserver):
    def __init__(self) -> None:
        self.obs = []  # type: ignore[var-annotated]

    def outReceived(self, data: str) -> None:
        self.obs.append(('out', data))

    def errReceived(self, data: str) -> None:
        self.obs.append(('err', data))

    def headerReceived(self, data: str) -> None:
        self.obs.append(('hdr', data))

    def finishReceived(self) -> None:
        self.obs.append(('fin',))


class TestLogObserver(TestReactorMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantData=True)
        yield self.master.db.insert_test_data([
            fakedb.Master(id=fakedb.FakeDBConnector.MASTER_ID),
            fakedb.Worker(id=400, name='linux'),
            fakedb.Builder(id=100),
            fakedb.Buildset(id=200),
            fakedb.BuildRequest(id=300, buildsetid=200, builderid=100),
            fakedb.Build(
                id=92,
                buildrequestid=300,
                number=7,
                masterid=fakedb.FakeDBConnector.MASTER_ID,
                builderid=100,
                workerid=400,
            ),
            fakedb.Step(id=1, buildid=92),
        ])

    @defer.inlineCallbacks
    def test_sequence(self) -> InlineCallbacksType[None]:
        logid = yield self.master.data.updates.addLog(1, 'mine', 's')
        _log = log.Log.new(self.master, 'mine', 's', logid, 'utf-8')
        lo = MyLogObserver()
        lo.setLog(_log)

        yield _log.addStdout('hello\n')  # type: ignore[attr-defined]
        yield _log.addStderr('cruel\n')  # type: ignore[attr-defined]
        yield _log.addStdout('world\n')  # type: ignore[attr-defined]
        yield _log.addStdout('multi\nline\nchunk\n')  # type: ignore[attr-defined]
        yield _log.addHeader('HDR\n')  # type: ignore[attr-defined]
        yield _log.finish()

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
    def __init__(self) -> None:
        super().__init__()
        self.obs = []  # type: ignore[var-annotated]

    def outLineReceived(self, line: str) -> None:
        self.obs.append(('out', line))

    def errLineReceived(self, line: str) -> None:
        self.obs.append(('err', line))

    def headerLineReceived(self, line: str) -> None:
        self.obs.append(('hdr', line))

    def finishReceived(self) -> None:
        self.obs.append(('fin',))


class TestLineConsumerLogObesrver(TestReactorMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantData=True)
        yield self.master.db.insert_test_data([
            fakedb.Master(id=fakedb.FakeDBConnector.MASTER_ID),
            fakedb.Worker(id=400, name='linux'),
            fakedb.Builder(id=100),
            fakedb.Buildset(id=200),
            fakedb.BuildRequest(id=300, buildsetid=200, builderid=100),
            fakedb.Build(
                id=92,
                buildrequestid=300,
                number=7,
                masterid=fakedb.FakeDBConnector.MASTER_ID,
                builderid=100,
                workerid=400,
            ),
            fakedb.Step(id=1, buildid=92),
        ])

    @defer.inlineCallbacks
    def do_test_sequence(
        self, consumer: Callable[[], Generator[None, tuple[str, str], None]]
    ) -> InlineCallbacksType[None]:
        logid = yield self.master.data.updates.addLog(1, 'mine', 's')
        _log = log.Log.new(self.master, 'mine', 's', logid, 'utf-8')
        lo = logobserver.LineConsumerLogObserver(consumer)
        lo.setLog(_log)

        yield _log.addStdout('hello\n')  # type: ignore[attr-defined]
        yield _log.addStderr('cruel\n')  # type: ignore[attr-defined]
        yield _log.addStdout('multi\nline\nchunk\n')  # type: ignore[attr-defined]
        yield _log.addHeader('H1\nH2\n')  # type: ignore[attr-defined]
        yield _log.finish()

    @defer.inlineCallbacks
    def test_sequence_finish(self) -> InlineCallbacksType[None]:
        results = []

        def consumer() -> Generator[None, tuple[str, str], None]:
            while True:
                try:
                    stream, line = yield
                    results.append((stream, line))
                except GeneratorExit:
                    results.append('finish')  # type: ignore[arg-type]
                    raise

        yield self.do_test_sequence(consumer)

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

    @defer.inlineCallbacks
    def test_sequence_no_finish(self) -> InlineCallbacksType[None]:
        results = []

        def consumer() -> Generator[None, tuple[str, str], None]:
            while True:
                stream, line = yield
                results.append((stream, line))

        yield self.do_test_sequence(consumer)

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
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantData=True)
        yield self.master.db.insert_test_data([
            fakedb.Master(id=fakedb.FakeDBConnector.MASTER_ID),
            fakedb.Worker(id=400, name='linux'),
            fakedb.Builder(id=100),
            fakedb.Buildset(id=200),
            fakedb.BuildRequest(id=300, buildsetid=200, builderid=100),
            fakedb.Build(
                id=92,
                buildrequestid=300,
                number=7,
                masterid=fakedb.FakeDBConnector.MASTER_ID,
                builderid=100,
                workerid=400,
            ),
            fakedb.Step(id=1, buildid=92),
        ])

    @defer.inlineCallbacks
    def test_sequence(self) -> InlineCallbacksType[None]:
        logid = yield self.master.data.updates.addLog(1, 'mine', 's')
        _log = log.Log.new(self.master, 'mine', 's', logid, 'utf-8')
        lo = MyLogLineObserver()
        lo.setLog(_log)

        yield _log.addStdout('hello\n')  # type: ignore[attr-defined]
        yield _log.addStderr('cruel\n')  # type: ignore[attr-defined]
        yield _log.addStdout('multi\nline\nchunk\n')  # type: ignore[attr-defined]
        yield _log.addHeader('H1\nH2\n')  # type: ignore[attr-defined]
        yield _log.finish()

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

    def test_old_setMaxLineLength(self) -> None:
        # this method is gone, but used to be documented, so it's still
        # callable.  Just don't fail.
        lo = MyLogLineObserver()
        lo.setMaxLineLength(120939403)


class TestOutputProgressObserver(TestReactorMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantData=True)
        yield self.master.db.insert_test_data([
            fakedb.Master(id=fakedb.FakeDBConnector.MASTER_ID),
            fakedb.Worker(id=400, name='linux'),
            fakedb.Builder(id=100),
            fakedb.Buildset(id=200),
            fakedb.BuildRequest(id=300, buildsetid=200, builderid=100),
            fakedb.Build(
                id=92,
                buildrequestid=300,
                number=7,
                masterid=fakedb.FakeDBConnector.MASTER_ID,
                builderid=100,
                workerid=400,
            ),
            fakedb.Step(id=1, buildid=92),
        ])

    @defer.inlineCallbacks
    def test_sequence(self) -> InlineCallbacksType[None]:
        logid = yield self.master.data.updates.addLog(1, 'mine', 's')
        _log = log.Log.new(self.master, 'mine', 's', logid, 'utf-8')
        lo = logobserver.OutputProgressObserver('stdio')
        step = mock.Mock()
        lo.setStep(step)
        lo.setLog(_log)

        yield _log.addStdout('hello\n')  # type: ignore[attr-defined]
        step.setProgress.assert_called_with('stdio', 6)
        yield _log.finish()


class TestBufferObserver(TestReactorMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantData=True)
        yield self.master.db.insert_test_data([
            fakedb.Master(id=fakedb.FakeDBConnector.MASTER_ID),
            fakedb.Worker(id=400, name='linux'),
            fakedb.Builder(id=100),
            fakedb.Buildset(id=200),
            fakedb.BuildRequest(id=300, buildsetid=200, builderid=100),
            fakedb.Build(
                id=92,
                buildrequestid=300,
                number=7,
                masterid=fakedb.FakeDBConnector.MASTER_ID,
                builderid=100,
                workerid=400,
            ),
            fakedb.Step(id=1, buildid=92),
        ])

    @defer.inlineCallbacks
    def do_test_sequence(self, lo: BufferLogObserver) -> InlineCallbacksType[None]:
        logid = yield self.master.data.updates.addLog(1, 'mine', 's')
        _log = log.Log.new(self.master, 'mine', 's', logid, 'utf-8')
        lo.setLog(_log)

        yield _log.addStdout('hello\n')  # type: ignore[attr-defined]
        yield _log.addStderr('cruel\n')  # type: ignore[attr-defined]
        yield _log.addStdout('multi\nline\nchunk\n')  # type: ignore[attr-defined]
        yield _log.addHeader('H1\nH2\n')  # type: ignore[attr-defined]
        yield _log.finish()

    @defer.inlineCallbacks
    def test_stdout_only(self) -> InlineCallbacksType[None]:
        lo = logobserver.BufferLogObserver(wantStdout=True, wantStderr=False)
        yield self.do_test_sequence(lo)
        self.assertEqual(lo.getStdout(), 'hello\nmulti\nline\nchunk\n')
        self.assertEqual(lo.getStderr(), '')

    @defer.inlineCallbacks
    def test_both(self) -> InlineCallbacksType[None]:
        lo = logobserver.BufferLogObserver(wantStdout=True, wantStderr=True)
        yield self.do_test_sequence(lo)
        self.assertEqual(lo.getStdout(), 'hello\nmulti\nline\nchunk\n')
        self.assertEqual(lo.getStderr(), 'cruel\n')
