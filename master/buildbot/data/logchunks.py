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

from collections.abc import AsyncGenerator
from collections.abc import AsyncIterable
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
from typing import TYPE_CHECKING

from twisted.internet import defer
from twisted.internet.defer import Deferred
from typing_extensions import Self

from buildbot.data import base
from buildbot.data import types
from buildbot.util.twisted import any_to_async

if TYPE_CHECKING:
    from types import TracebackType
    from typing import Any

    from buildbot.db.logs import LogModel
    from buildbot.master import BuildMaster
    from buildbot.mq.base import QueueRef
    from buildbot.util.twisted import InlineCallbacksType


class _LogLinesIterator(AbstractAsyncContextManager, AsyncIterable[str]):
    def __init__(self, log_dict: LogModel, master: BuildMaster) -> None:
        self._log_dict = log_dict
        self._master = master

        self._is_complete_log = log_dict.complete

        # A deferred that will be resolved when new log arrive
        self._received_new_log_future: Deferred[None] = Deferred()

        self._log_finished_consumer: QueueRef | None = None
        self._log_append_consumer: QueueRef | None = None

    async def __aenter__(self) -> Self:
        if not self._is_complete_log:

            def _on_log_finished(_routing_key: tuple[str, ...], _data: dict[str, Any]) -> None:
                self._is_complete_log = True
                self._signal_log_update()

            # 1. Start listening for end event
            self._log_finished_consumer = await self._master.mq.startConsuming(
                _on_log_finished,
                ('logs', str(self._log_dict.id), 'finished'),
            )

            # 2. Get Log status from DB in case it was completed before we started listening
            db_log = await self._master.db.logs.getLog(self._log_dict.id)
            assert db_log is not None
            if db_log.complete:
                self._is_complete_log = True
                assert self._log_append_consumer is not None
                await any_to_async(self._log_append_consumer.stopConsuming())
                self._log_append_consumer = None

        if not self._is_complete_log:

            def _on_log_append(_routing_key: tuple[str, ...], _data: dict[str, Any]) -> None:
                self._signal_log_update()

            # 3. Start listening on log append
            self._log_append_consumer = await self._master.mq.startConsuming(
                _on_log_append,
                ('logs', str(self._log_dict.id), 'append'),
            )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if self._log_finished_consumer is not None:
            await any_to_async(self._log_finished_consumer.stopConsuming())
        if self._log_append_consumer is not None:
            await any_to_async(self._log_append_consumer.stopConsuming())

        return None

    async def __aiter__(self) -> AsyncIterator:
        async def _iter_log_lines(first_line: int) -> AsyncGenerator[str, None]:
            async for line in self._master.db.logs.iter_log_lines(
                self._log_dict.id,
                first_line=first_line,
            ):
                yield line

        # yield lines already in DB
        last_log_line = 0
        async for line in _iter_log_lines(first_line=last_log_line):
            last_log_line += 1
            yield line

        while not self._is_complete_log:
            await self._received_new_log_future
            # Reset future for next loop iteration
            self._received_new_log_future = Deferred()
            async for line in _iter_log_lines(first_line=last_log_line):
                last_log_line += 1
                yield line

    def _signal_log_update(self) -> None:
        if not self._received_new_log_future.called:
            self._received_new_log_future.callback(None)


class LogChunkEndpointBase(base.BuildNestingMixin, base.Endpoint):
    @staticmethod
    async def get_raw_log_lines(log_lines_generator: AsyncGenerator[str, None]) -> str:
        parts = []
        async for chunk in log_lines_generator:
            parts.append(chunk)
        return ''.join(parts)

    async def get_log_lines(
        self,
        log_dict: LogModel,
        log_prefix: str,
    ) -> AsyncGenerator[str, None]:
        if log_prefix:
            yield log_prefix

        is_stdio_log = log_dict.type == 's'

        async with _LogLinesIterator(log_dict, master=self.master) as iterator:
            async for line in iterator:
                if is_stdio_log:
                    # for stdio logs, the first char is the stream type
                    # ref: https://buildbot.readthedocs.io/en/latest/developer/raml/logchunk.html#logchunk
                    line = line[1:]

                yield line

    @defer.inlineCallbacks
    def get_log_lines_raw_data(
        self, kwargs: dict[str, Any]
    ) -> InlineCallbacksType[tuple[AsyncGenerator[str, None], str, str] | tuple[None, None, None]]:
        retriever = base.NestedBuildDataRetriever(self.master, kwargs)
        log_dict = yield retriever.get_log_dict()
        if log_dict is None:
            return None, None, None

        # The following should be run sequentially instead of in gatherResults(), so that
        # they don't all start a query on step dict each.
        step_dict = yield retriever.get_step_dict()
        build_dict = yield retriever.get_build_dict()
        builder_dict = yield retriever.get_builder_dict()
        worker_dict = yield retriever.get_worker_dict()

        log_prefix = ''
        if log_dict.type == 's':
            if builder_dict is not None:
                log_prefix += f'Builder: {builder_dict.name}\n'
            if build_dict is not None:
                log_prefix += f'Build number: {build_dict.number}\n'
            if worker_dict is not None:
                log_prefix += f'Worker name: {worker_dict.name}\n'

        informative_parts = []
        if builder_dict is not None:
            informative_parts += [builder_dict.name]
        if build_dict is not None:
            informative_parts += ['build', str(build_dict.number)]
        if step_dict is not None:
            informative_parts += ['step', step_dict.name]
        informative_parts += ['log', log_dict.slug]
        informative_slug = '_'.join(informative_parts)

        return self.get_log_lines(log_dict, log_prefix), log_dict.type, informative_slug


class LogChunkEndpoint(LogChunkEndpointBase):
    # Note that this is a singular endpoint, even though it overrides the
    # offset/limit query params in ResultSpec
    kind = base.EndpointKind.SINGLE
    isPseudoCollection = True
    pathPatterns = [
        "/logchunks",
        "/logs/n:logid/contents",
        "/steps/n:stepid/logs/i:log_slug/contents",
        "/builds/n:buildid/steps/i:step_name/logs/i:log_slug/contents",
        "/builds/n:buildid/steps/n:step_number/logs/i:log_slug/contents",
        "/builders/n:builderid/builds/n:build_number/steps/i:step_name/logs/i:log_slug/contents",
        "/builders/n:builderid/builds/n:build_number/steps/n:step_number/logs/i:log_slug/contents",
    ]
    rootLinkName = "logchunks"

    @defer.inlineCallbacks
    def get(
        self, resultSpec: base.ResultSpec, kwargs: dict[str, Any]
    ) -> InlineCallbacksType[dict[str, Any] | None]:
        retriever = base.NestedBuildDataRetriever(self.master, kwargs)
        logid = yield retriever.get_log_id()
        if logid is None:
            return None

        firstline = int(resultSpec.offset or 0)
        lastline = None if resultSpec.limit is None else firstline + int(resultSpec.limit) - 1
        resultSpec.removePagination()

        # get the number of lines, if necessary
        if lastline is None:
            log_dict = yield retriever.get_log_dict()
            if not log_dict:
                return None
            lastline = int(max(0, log_dict.num_lines - 1))

        # bounds checks
        if firstline < 0 or lastline < 0 or firstline > lastline:
            return None

        logLines = yield self.master.db.logs.getLogLines(logid, firstline, lastline)
        return {'logid': logid, 'firstline': firstline, 'content': logLines}


class RawLogChunkEndpoint(LogChunkEndpointBase):
    # Note that this is a singular endpoint, even though it overrides the
    # offset/limit query params in ResultSpec
    kind = base.EndpointKind.RAW
    pathPatterns = [
        "/logs/n:logid/raw",
        "/steps/n:stepid/logs/i:log_slug/raw",
        "/builds/n:buildid/steps/i:step_name/logs/i:log_slug/raw",
        "/builds/n:buildid/steps/n:step_number/logs/i:log_slug/raw",
        "/builders/n:builderid/builds/n:build_number/steps/i:step_name/logs/i:log_slug/raw",
        "/builders/n:builderid/builds/n:build_number/steps/n:step_number/logs/i:log_slug/raw",
    ]

    @defer.inlineCallbacks
    def get(
        self, resultSpec: base.ResultSpec, kwargs: dict[str, Any]
    ) -> InlineCallbacksType[dict[str, Any] | None]:
        data = yield defer.Deferred.fromCoroutine(self.stream(resultSpec, kwargs))
        if data is None:
            return None

        data["raw"] = yield defer.Deferred.fromCoroutine(
            self.get_raw_log_lines(log_lines_generator=data["raw"])
        )
        return data

    async def stream(
        self, resultSpec: base.ResultSpec, kwargs: dict[str, Any]
    ) -> dict[str, Any] | None:
        log_lines_generator, log_type, log_slug = await self.get_log_lines_raw_data(kwargs)

        if log_lines_generator is None:
            return None

        return {
            'raw': log_lines_generator,
            'mime-type': 'text/html' if log_type == 'h' else 'text/plain',
            'filename': log_slug,
        }


class RawInlineLogChunkEndpoint(LogChunkEndpointBase):
    # Note that this is a singular endpoint, even though it overrides the
    # offset/limit query params in ResultSpec
    kind = base.EndpointKind.RAW_INLINE
    pathPatterns = [
        "/logs/n:logid/raw_inline",
        "/steps/n:stepid/logs/i:log_slug/raw_inline",
        "/builds/n:buildid/steps/i:step_name/logs/i:log_slug/raw_inline",
        "/builds/n:buildid/steps/n:step_number/logs/i:log_slug/raw_inline",
        "/builders/n:builderid/builds/n:build_number/steps/i:step_name/logs/i:log_slug/raw_inline",
        "/builders/n:builderid/builds/n:build_number/steps/n:step_number/logs/i:log_slug/raw_inline",
    ]

    @defer.inlineCallbacks
    def get(
        self, resultSpec: base.ResultSpec, kwargs: dict[str, Any]
    ) -> InlineCallbacksType[dict[str, Any] | None]:
        data = yield defer.Deferred.fromCoroutine(self.stream(resultSpec, kwargs))

        if data is None:
            return None

        data["raw"] = yield defer.Deferred.fromCoroutine(
            self.get_raw_log_lines(log_lines_generator=data["raw"])
        )

        return data

    async def stream(
        self, resultSpec: base.ResultSpec, kwargs: dict[str, Any]
    ) -> dict[str, Any] | None:
        log_lines_generator, log_type, _ = await self.get_log_lines_raw_data(kwargs)

        if log_lines_generator is None:
            return None

        return {
            'raw': log_lines_generator,
            'mime-type': 'text/html' if log_type == 'h' else 'text/plain',
        }


class LogChunk(base.ResourceType):
    name = "logchunk"
    plural = "logchunks"
    endpoints = [LogChunkEndpoint, RawLogChunkEndpoint, RawInlineLogChunkEndpoint]

    class EntityType(types.Entity):
        logid = types.Integer()
        firstline = types.Integer()
        content = types.String()

    entityType = EntityType(name)
