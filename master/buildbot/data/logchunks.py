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

from twisted.internet import defer

from buildbot.data import base
from buildbot.data import types

if TYPE_CHECKING:
    from typing import Any
    from typing import AsyncGenerator

    from buildbot.db.logs import LogModel


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

        async for line in self.master.db.logs.iter_log_lines(log_dict.id):
            if is_stdio_log:
                # for stdio logs, the first char is the stream type
                # ref: https://buildbot.readthedocs.io/en/latest/developer/raml/logchunk.html#logchunk
                line = line[1:]

            yield line

    @defer.inlineCallbacks
    def get_log_lines_raw_data(self, kwargs):
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
    def get(self, resultSpec, kwargs):
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
    def get(self, resultSpec, kwargs):
        data = yield defer.Deferred.fromCoroutine(self.stream(resultSpec, kwargs))
        if data is None:
            return None

        data["raw"] = yield defer.Deferred.fromCoroutine(
            self.get_raw_log_lines(log_lines_generator=data["raw"])
        )
        return data

    async def stream(self, resultSpec: base.ResultSpec, kwargs: dict[str, Any]):
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
    def get(self, resultSpec, kwargs):
        data = yield defer.Deferred.fromCoroutine(self.stream(resultSpec, kwargs))

        if data is None:
            return None

        data["raw"] = yield defer.Deferred.fromCoroutine(
            self.get_raw_log_lines(log_lines_generator=data["raw"])
        )

        return data

    async def stream(self, resultSpec: base.ResultSpec, kwargs: dict[str, Any]):
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
