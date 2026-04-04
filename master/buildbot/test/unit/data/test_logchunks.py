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

import textwrap
from typing import TYPE_CHECKING
from typing import cast
from unittest import mock

from twisted.internet import defer
from twisted.internet.defer import Deferred
from twisted.trial import unittest
from typing_extensions import override

from buildbot.data import base
from buildbot.data import logchunks
from buildbot.data import resultspec
from buildbot.mq.simple import SimpleMQ
from buildbot.process.buildstep import BuildStep
from buildbot.process.buildstep import create_step_from_step_or_factory
from buildbot.process.log import PlainLog
from buildbot.process.results import SUCCESS
from buildbot.test import fakedb
from buildbot.test.fake.fakebuild import FakeBuild
from buildbot.test.fake.fakedata import FakeDataConnector
from buildbot.test.fake.fakemaster import make_master
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import endpoint
from buildbot.util.twisted import async_to_deferred

if TYPE_CHECKING:
    from buildbot.process.build import Build
    from buildbot.util.twisted import InlineCallbacksType


class LogChunkEndpointBase(endpoint.EndpointMixin, unittest.TestCase):
    endpointClass: type[base.Endpoint] = logchunks.LogChunkEndpoint
    resourceTypeClass: type[base.ResourceType] = logchunks.LogChunk
    endpointname = "contents"
    log60Lines = [
        'line zero',
        'line 1',
        'line TWO',
        'line 3',
        'line 2**2',
        'another line',
        'yet another line',
    ]
    log61Lines = [f'{i:08d}' for i in range(100)]

    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        yield self.setUpEndpoint()
        yield self.master.db.insert_test_data(
            [
                fakedb.Builder(id=77),
                fakedb.Worker(id=13, name='wrk'),
                fakedb.Master(id=88),
                fakedb.Buildset(id=8822),
                fakedb.BuildRequest(id=82, builderid=77, buildsetid=8822),
                fakedb.Build(
                    id=13, builderid=77, masterid=88, workerid=13, buildrequestid=82, number=3
                ),
                fakedb.Step(id=50, buildid=13, number=9, name='make'),
                fakedb.Log(
                    id=60,
                    stepid=50,
                    name='stdio',
                    slug='stdio',
                    type='s',
                    num_lines=7,
                    complete=1,
                ),
                fakedb.LogChunk(
                    logid=60,
                    first_line=0,
                    last_line=1,
                    compressed=0,
                    content=textwrap.dedent("""\
                        line zero
                        line 1"""),
                ),
                fakedb.LogChunk(
                    logid=60,
                    first_line=2,
                    last_line=4,
                    compressed=0,
                    content=textwrap.dedent("""\
                        line TWO
                        line 3
                        line 2**2"""),
                ),
                fakedb.LogChunk(
                    logid=60, first_line=5, last_line=5, compressed=0, content="another line"
                ),
                fakedb.LogChunk(
                    logid=60, first_line=6, last_line=6, compressed=0, content="yet another line"
                ),
                fakedb.Log(
                    id=61,
                    stepid=50,
                    name='errors',
                    slug='errors',
                    type='t',
                    num_lines=100,
                    complete=1,
                ),
            ]
            + [
                fakedb.LogChunk(
                    logid=61, first_line=i, last_line=i, compressed=0, content=f"{i:08d}"
                )
                for i in range(100)
            ]
            + [
                fakedb.Log(
                    id=62,
                    stepid=50,
                    name='notes',
                    slug='notes',
                    type='t',
                    num_lines=0,
                    complete=1,
                ),
                # logid 62 is empty
            ]
        )

    @defer.inlineCallbacks
    def do_test_chunks(
        self, path: tuple[str, ...], logid: int, expLines: list[str]
    ) -> InlineCallbacksType[None]:
        # get the whole thing in one go
        logchunk = yield self.callGet(path)
        self.validateData(logchunk)
        expContent = '\n'.join(expLines) + '\n'
        self.assertEqual(logchunk, {'logid': logid, 'firstline': 0, 'content': expContent})

        # line-by-line
        for i, expLine in enumerate(expLines):
            logchunk = yield self.callGet(path, resultSpec=resultspec.ResultSpec(offset=i, limit=1))
            self.validateData(logchunk)
            self.assertEqual(logchunk, {'logid': logid, 'firstline': i, 'content': expLine + '\n'})

        # half and half
        mid = int(len(expLines) / 2)
        for f, length in (0, mid), (mid, len(expLines) - 1):
            result_spec = resultspec.ResultSpec(offset=f, limit=length - f + 1)
            logchunk = yield self.callGet(path, resultSpec=result_spec)
            self.validateData(logchunk)
            expContent = '\n'.join(expLines[f : length + 1]) + '\n'
            self.assertEqual(logchunk, {'logid': logid, 'firstline': f, 'content': expContent})

        # truncated at EOF
        f = len(expLines) - 2
        length = len(expLines) + 10
        result_spec = resultspec.ResultSpec(offset=f, limit=length - f + 1)
        logchunk = yield self.callGet(path, resultSpec=result_spec)
        self.validateData(logchunk)
        expContent = '\n'.join(expLines[-2:]) + '\n'
        self.assertEqual(logchunk, {'logid': logid, 'firstline': f, 'content': expContent})

        # some illegal stuff
        self.assertEqual(
            (yield self.callGet(path, resultSpec=resultspec.ResultSpec(offset=-1))), None
        )
        self.assertEqual(
            (yield self.callGet(path, resultSpec=resultspec.ResultSpec(offset=10, limit=-1))), None
        )

    def test_get_logid_60(self) -> defer.Deferred[None]:
        return self.do_test_chunks(('logs', 60, self.endpointname), 60, self.log60Lines)  # type: ignore[arg-type]

    def test_get_logid_61(self) -> defer.Deferred[None]:
        return self.do_test_chunks(('logs', 61, self.endpointname), 61, self.log61Lines)  # type: ignore[arg-type]


class LogChunkEndpoint(LogChunkEndpointBase):
    @defer.inlineCallbacks
    def test_get_missing(self) -> InlineCallbacksType[None]:
        logchunk = yield self.callGet(('logs', 99, self.endpointname))
        self.assertEqual(logchunk, None)

    @defer.inlineCallbacks
    def test_get_empty(self) -> InlineCallbacksType[None]:
        logchunk = yield self.callGet(('logs', 62, self.endpointname))
        self.validateData(logchunk)
        self.assertEqual(logchunk['content'], '')

    @defer.inlineCallbacks
    def test_get_by_stepid(self) -> InlineCallbacksType[None]:
        logchunk = yield self.callGet(('steps', 50, 'logs', 'errors', self.endpointname))
        self.validateData(logchunk)
        self.assertEqual(logchunk['logid'], 61)

    @defer.inlineCallbacks
    def test_get_by_buildid(self) -> InlineCallbacksType[None]:
        logchunk = yield self.callGet((
            'builds',
            13,
            'steps',
            9,
            'logs',
            'stdio',
            self.endpointname,
        ))
        self.validateData(logchunk)
        self.assertEqual(logchunk['logid'], 60)

    @defer.inlineCallbacks
    def test_get_by_builder(self) -> InlineCallbacksType[None]:
        logchunk = yield self.callGet((
            'builders',
            77,
            'builds',
            3,
            'steps',
            9,
            'logs',
            'errors',
            self.endpointname,
        ))
        self.validateData(logchunk)
        self.assertEqual(logchunk['logid'], 61)

    @defer.inlineCallbacks
    def test_get_by_builder_step_name(self) -> InlineCallbacksType[None]:
        logchunk = yield self.callGet((
            'builders',
            77,
            'builds',
            3,
            'steps',
            'make',
            'logs',
            'errors',
            self.endpointname,
        ))
        self.validateData(logchunk)
        self.assertEqual(logchunk['logid'], 61)


class RawLogChunkEndpoint(LogChunkEndpointBase):
    endpointClass = logchunks.RawLogChunkEndpoint
    endpointname = "raw"

    def validateData(self, data: dict[str, str]) -> None:
        self.assertIsInstance(data['raw'], str)
        self.assertIsInstance(data['mime-type'], str)
        self.assertIsInstance(data['filename'], str)

    @defer.inlineCallbacks
    def do_test_chunks(
        self, path: tuple[str, ...], logid: int, expLines: list[str]
    ) -> InlineCallbacksType[None]:
        # get the whole thing in one go
        logchunk = yield self.callGet(path)
        self.validateData(logchunk)
        if logid == 60:
            expContent = 'Builder: builder-77\nBuild number: 3\nWorker name: wrk\n'
            expContent += ''.join([f"{line[1:]}\n" for line in expLines])
            expFilename = "builder-77_build_3_step_make_log_stdio"
        else:
            expContent = '\n'.join(expLines) + '\n'
            expFilename = "builder-77_build_3_step_make_log_errors"

        self.assertEqual(
            logchunk, {'filename': expFilename, 'mime-type': "text/plain", 'raw': expContent}
        )


class AsyncLoggingStep(BuildStep):
    def __init__(self) -> None:
        super().__init__(name='fake')
        self.has_produced_initial_logs_future: Deferred[None] = Deferred()
        self.has_produced_additional_logs_future: Deferred[None] = Deferred()

        self._produce_more_log_future: Deferred[None] = Deferred()
        self._finish_log_future: Deferred[None] = Deferred()

        self.initial_lines_count = 10
        self.additional_lines_count = 5

    async def trigger_more_logs(self) -> None:
        self._produce_more_log_future.callback(None)
        await self.has_produced_additional_logs_future

    def trigger_log_finish(self) -> None:
        self._finish_log_future.callback(None)

    @override
    @async_to_deferred
    async def run(self) -> int:
        log = await self.addLog('test-log', type='t')
        assert isinstance(log, PlainLog)

        await log.addContent(''.join(f'line {idx}\n' for idx in range(self.initial_lines_count)))
        await log.flush()

        self.has_produced_initial_logs_future.callback(None)

        await self._produce_more_log_future
        await log.addContent(
            ''.join(f'additional line {idx}\n' for idx in range(self.additional_lines_count))
        )
        await log.flush()

        self.has_produced_additional_logs_future.callback(None)

        await self._finish_log_future
        await log.finish()

        return SUCCESS


class RawLogChunkEndpointFollowUncomplete(TestReactorMixin, unittest.TestCase):
    async def setUp(self) -> None:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = await make_master(
            self,
            wantDb=True,
            # wantData forces wantMq to True
            # but we want a real MQ as FakeMQ
            # does not send events
            wantData=False,
            wantMq=False,
        )

        await self.master.db.insert_test_data([
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
        ])

        self.build = FakeBuild(master=self.master)

        # Needs a real MQ to produce events
        self.mq = self.master.mq = SimpleMQ()  # type: ignore[assignment]
        self.mq.setServiceParent(self.master)
        self.mq.startService()

        self.master.data = FakeDataConnector(self.master, self)

        @async_to_deferred
        async def cleanup() -> None:
            if self.mq.running:
                await self.mq.stopService()

        self.addCleanup(cleanup)

    async def test_raw(self) -> None:
        step = cast(AsyncLoggingStep, create_step_from_step_or_factory(AsyncLoggingStep()))
        step.setBuild(cast("Build", self.build))

        step_run_future = step.startStep(mock.Mock())

        endpoint, kwargs = self.master.data.getEndpoint(
            ('builds', str(self.build.buildid), 'steps', step.number, 'logs', 'test-log', 'raw'),
        )
        assert isinstance(endpoint, logchunks.RawLogChunkEndpoint)
        stream_response = await endpoint.stream(resultSpec=resultspec.ResultSpec(), kwargs=kwargs)
        assert stream_response is not None

        streamed_lines: list[str] = []

        async def _streamed_lines_consumer() -> None:
            async for line in stream_response['raw']:
                streamed_lines.append(line)

        lines_consumer_future = Deferred.fromCoroutine(_streamed_lines_consumer())

        await step.has_produced_initial_logs_future

        initial_lines = [f"line {idx}\n" for idx in range(step.initial_lines_count)]
        self.assertEqual(streamed_lines, initial_lines)
        self.assertFalse(lines_consumer_future.called)

        await step.trigger_more_logs()

        additional_lines = [
            f"additional line {idx}\n" for idx in range(step.additional_lines_count)
        ]
        self.assertEqual(streamed_lines, initial_lines + additional_lines)
        self.assertFalse(lines_consumer_future.called)

        step.trigger_log_finish()
        step_res = await step_run_future

        self.assertEqual(streamed_lines, initial_lines + additional_lines)
        self.assertTrue(lines_consumer_future.called)

        self.assertFalse(step._running)
        errors = self.flushLoggedErrors()
        self.assertEqual(len(errors), 0)
        self.assertEqual(step_res, SUCCESS)
