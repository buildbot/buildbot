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

import dataclasses
import io
import os
import threading
from functools import partial
from typing import TYPE_CHECKING

import sqlalchemy as sa
from twisted.internet import defer
from twisted.internet import threads
from twisted.python import log
from twisted.python import threadpool
from twisted.python.failure import Failure

from buildbot import util
from buildbot.config.master import get_is_in_unit_tests
from buildbot.db import base
from buildbot.db.compression import BrotliCompressor
from buildbot.db.compression import BZipCompressor
from buildbot.db.compression import CompressorInterface
from buildbot.db.compression import GZipCompressor
from buildbot.db.compression import LZ4Compressor
from buildbot.db.compression import ZStdCompressor
from buildbot.db.compression.protocol import CompressObjInterface
from buildbot.util.twisted import async_to_deferred
from buildbot.warnings import warn_deprecated

if TYPE_CHECKING:
    from typing import AsyncGenerator
    from typing import Callable
    from typing import Generator
    from typing import Literal
    from typing import TypeVar

    from sqlalchemy.engine import Connection as SAConnection
    from twisted.internet.interfaces import IReactorThreads
    from typing_extensions import ParamSpec

    _T = TypeVar('_T')
    _P = ParamSpec('_P')

    LogType = Literal['s', 't', 'h', 'd']


class LogSlugExistsError(KeyError):
    pass


class LogCompressionFormatUnavailableError(LookupError):
    pass


@dataclasses.dataclass
class LogModel:
    id: int
    name: str
    slug: str
    stepid: int
    complete: bool
    num_lines: int
    type: LogType

    # For backward compatibility
    def __getitem__(self, key: str):
        warn_deprecated(
            '4.1.0',
            (
                'LogsConnectorComponent '
                'getLog, getLogBySlug, and getLogs '
                'no longer return Log as dictionnaries. '
                'Usage of [] accessor is deprecated: please access the member directly'
            ),
        )

        if hasattr(self, key):
            return getattr(self, key)

        raise KeyError(key)


class RawCompressor(CompressorInterface):
    name = "raw"

    @staticmethod
    def dumps(data: bytes) -> bytes:
        return data

    @staticmethod
    def read(data: bytes) -> bytes:
        return data

    class CompressObj(CompressObjInterface):
        def compress(self, data: bytes) -> bytes:
            return data

        def flush(self) -> bytes:
            return b''


class LogsConnectorComponent(base.DBConnectorComponent):
    # Postgres and MySQL will both allow bigger sizes than this.  The limit
    # for MySQL appears to be max_packet_size (default 1M).
    # note that MAX_CHUNK_SIZE is equal to BUFFER_SIZE in buildbot_worker.runprocess
    MAX_CHUNK_SIZE = 65536  # a chunk may not be bigger than this
    MAX_CHUNK_LINES = 1000  # a chunk may not have more lines than this

    NO_COMPRESSION_ID = 0
    COMPRESSION_BYID: dict[int, type[CompressorInterface]] = {
        NO_COMPRESSION_ID: RawCompressor,
        1: GZipCompressor,
        2: BZipCompressor,
        3: LZ4Compressor,
        4: ZStdCompressor,
        5: BrotliCompressor,
    }

    COMPRESSION_MODE = {
        compressor.name: (compressor_id, compressor)
        for compressor_id, compressor in COMPRESSION_BYID.items()
    }

    def __init__(self, connector: base.DBConnector):
        super().__init__(connector)

        max_threads = 1
        if cpu_count := os.cpu_count():
            # use at most half cpu available to avoid oversubscribing
            # the master on other processes
            max_threads = max(int(cpu_count / 2), max_threads)

        self._compression_pool = util.twisted.ThreadPool(
            minthreads=1,
            maxthreads=max_threads,
            name='DBLogCompression',
        )

    @defer.inlineCallbacks
    def startService(self):
        yield super().startService()
        self._compression_pool.start()

    @defer.inlineCallbacks
    def stopService(self):
        yield super().stopService()
        self._compression_pool.stop()

    def _defer_to_compression_pool(
        self,
        callable: Callable[_P, _T],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> defer.Deferred[_T]:
        return threads.deferToThreadPool(
            self.master.reactor, self._compression_pool, callable, *args, **kwargs
        )

    def _get_compressor(self, compressor_id: int) -> type[CompressorInterface]:
        compressor = self.COMPRESSION_BYID.get(compressor_id)
        if compressor is None:
            msg = f"Unknown compression method ID {compressor_id}"
            raise LogCompressionFormatUnavailableError(msg)
        if not compressor.available:
            msg = (
                f"Log compression method {compressor.name} is not available. "
                "You might be missing a dependency."
            )
            raise LogCompressionFormatUnavailableError(msg)
        return compressor

    def _getLog(self, whereclause) -> defer.Deferred[LogModel | None]:
        def thd_getLog(conn) -> LogModel | None:
            q = self.db.model.logs.select()
            if whereclause is not None:
                q = q.where(whereclause)
            res = conn.execute(q).mappings()
            row = res.fetchone()

            rv = None
            if row:
                rv = self._model_from_row(row)
            res.close()
            return rv

        return self.db.pool.do(thd_getLog)

    def getLog(self, logid: int) -> defer.Deferred[LogModel | None]:
        return self._getLog(self.db.model.logs.c.id == logid)

    def getLogBySlug(self, stepid: int, slug: str) -> defer.Deferred[LogModel | None]:
        tbl = self.db.model.logs
        return self._getLog((tbl.c.slug == slug) & (tbl.c.stepid == stepid))

    def getLogs(self, stepid: int | None = None) -> defer.Deferred[list[LogModel]]:
        def thdGetLogs(conn) -> list[LogModel]:
            tbl = self.db.model.logs
            q = tbl.select()
            if stepid is not None:
                q = q.where(tbl.c.stepid == stepid)
            q = q.order_by(tbl.c.id)
            res = conn.execute(q).mappings()
            return [self._model_from_row(row) for row in res.fetchall()]

        return self.db.pool.do(thdGetLogs)

    async def iter_log_lines(
        self,
        logid: int,
        first_line: int = 0,
        last_line: int | None = None,
    ) -> AsyncGenerator[str, None]:
        def _thd_get_chunks(
            conn: SAConnection,
            first_line: int,
            last_line: int | None,
            batch: int,
        ) -> list[tuple[int, int, int, bytes]]:
            tbl = self.db.model.logchunks
            q = sa.select(tbl.c.first_line, tbl.c.last_line, tbl.c.content, tbl.c.compressed)
            q = q.where(tbl.c.logid == logid)
            if last_line is not None:
                q = q.where(tbl.c.first_line <= last_line)
            q = q.where(tbl.c.last_line >= first_line)

            q = q.order_by(tbl.c.first_line)
            if batch > 0:
                q = q.limit(batch)

            return [
                (row.first_line, row.last_line, row.compressed, row.content)
                for row in conn.execute(q)
            ]

        async def _iter_chunks_batched():
            CHUNK_BATCH_SIZE = 100
            batch_first_line = first_line
            while chunks := await self.db.pool.do(
                _thd_get_chunks,
                batch_first_line,
                last_line,
                CHUNK_BATCH_SIZE,
            ):
                for chunk in chunks:
                    yield chunk

                _, chunk_last_line, _, _ = chunks[-1]
                batch_first_line = max(batch_first_line, chunk_last_line) + 1

        def _iter_uncompress_lines(
            chunk_first_line: int,
            compressed: int,
            content: bytes,
        ) -> Generator[str, None, None]:
            # Retrieve associated "reader" and extract the data
            # Note that row.content is stored as bytes, and our caller expects unicode
            data = self._get_compressor(compressed).read(content)
            # NOTE: we need a streaming decompression interface
            with io.BytesIO(data) as data_buffer, io.TextIOWrapper(
                data_buffer,
                encoding='utf-8',
            ) as reader:
                # last line-ending is stripped from chunk on insert
                # add it back here to simplify handling after
                data_buffer.seek(0, os.SEEK_END)
                data_buffer.write(b'\n')
                data_buffer.seek(0, os.SEEK_SET)

                line_idx = chunk_first_line

                # need to skip some lines
                while line_idx < first_line and reader.readline():
                    line_idx += 1

                while (last_line is None or line_idx <= last_line) and (line := reader.readline()):
                    yield line
                    line_idx += 1

        async for chunk_first_line, _, compressed, content in _iter_chunks_batched():
            async for line in _async_iter_on_pool(
                partial(
                    _iter_uncompress_lines,
                    chunk_first_line=chunk_first_line,
                    compressed=compressed,
                    content=content,
                ),
                reactor=self.master.reactor,
                provider_threadpool=self._compression_pool,
                # disable limit as we process one chunk at a time
                max_backlog=0,
            ):
                yield line

    @async_to_deferred
    async def getLogLines(self, logid: int, first_line: int, last_line: int) -> str:
        lines: list[str] = []
        async for line in self.iter_log_lines(
            logid=logid,
            first_line=first_line,
            last_line=last_line,
        ):
            lines.append(line)

        return ''.join(lines)

    def addLog(self, stepid: int, name: str, slug: str, type: LogType) -> defer.Deferred[int]:
        assert type in 'tsh', "Log type must be one of t, s, or h"

        def thdAddLog(conn) -> int:
            try:
                r = conn.execute(
                    self.db.model.logs.insert(),
                    {
                        "name": name,
                        "slug": slug,
                        "stepid": stepid,
                        "complete": 0,
                        "num_lines": 0,
                        "type": type,
                    },
                )
                conn.commit()
                return r.inserted_primary_key[0]
            except (sa.exc.IntegrityError, sa.exc.ProgrammingError) as e:
                conn.rollback()
                raise LogSlugExistsError(
                    f"log with slug '{slug!r}' already exists in this step"
                ) from e

        return self.db.pool.do(thdAddLog)

    def _get_configured_compressor(self) -> tuple[int, type[CompressorInterface]]:
        compress_method: str = self.master.config.logCompressionMethod
        return self.COMPRESSION_MODE.get(compress_method, (self.NO_COMPRESSION_ID, RawCompressor))

    @async_to_deferred
    async def appendLog(self, logid: int, content: str) -> tuple[int, int] | None:
        def _thd_get_numlines(conn: SAConnection) -> int | None:
            q = sa.select(self.db.model.logs.c.num_lines)
            q = q.where(self.db.model.logs.c.id == logid)
            res = conn.execute(q)
            num_lines = res.fetchone()
            res.close()
            return num_lines[0] if num_lines else None

        def _thd_insert_chunk(
            conn: SAConnection,
            first_line: int,
            last_line: int,
            content: bytes,
            compressed_id: int,
        ) -> None:
            res = conn.execute(
                self.db.model.logchunks.insert(),
                {
                    "logid": logid,
                    "first_line": first_line,
                    "last_line": last_line,
                    "content": content,
                    "compressed": compressed_id,
                },
            )
            conn.commit()
            res.close()

        def _thd_update_num_lines(conn: SAConnection, num_lines: int) -> None:
            res = conn.execute(
                self.db.model.logs.update()
                .where(self.db.model.logs.c.id == logid)
                .values(num_lines=num_lines)
            )
            conn.commit()
            res.close()

        def _thd_compress_chunk(
            compress_obj: CompressObjInterface,
            compressor_id: int,
            lines: list[bytes],
        ) -> tuple[bytes, int, int]:
            # check for trailing newline and strip it for storage
            # chunks omit the trailing newline
            assert lines and lines[-1][-1:] == b'\n'
            lines[-1] = lines[-1][:-1]

            compressed_bytes: list[bytes] = []
            uncompressed_size = 0
            for line in lines:
                uncompressed_size += len(line)
                compressed_bytes.append(compress_obj.compress(line))
            compressed_bytes.append(compress_obj.flush())
            compressed_chunk = b''.join(compressed_bytes)

            # Is it useful to compress the chunk?
            if uncompressed_size <= len(compressed_chunk):
                return b''.join(lines), self.NO_COMPRESSION_ID, len(lines)

            return compressed_chunk, compressor_id, len(lines)

        def _thd_iter_chunk_compress(
            content: str,
        ) -> Generator[tuple[bytes, int, int], None]:
            """
            Split content into chunk delimited by line-endings.
            Try our best to keep chunks smaller than MAX_CHUNK_SIZE
            """

            def _truncate_line(line: bytes) -> bytes:
                log.msg(f'truncating long line for log {logid}')
                line = line[: self.MAX_CHUNK_SIZE - 1]
                while line:
                    try:
                        line.decode('utf-8')
                        break
                    except UnicodeDecodeError:
                        line = line[:-1]
                return line + b'\n'

            compressor_id, compressor = self._get_configured_compressor()
            compress_obj = compressor.CompressObj()

            with io.StringIO(content) as buffer:
                lines: list[bytes] = []
                lines_size = 0
                while line := buffer.readline():
                    line_bytes = line.encode('utf-8')
                    line_size = len(line_bytes)
                    # would this go over limit?
                    if lines and lines_size + line_size > self.MAX_CHUNK_SIZE:
                        # flush lines
                        yield _thd_compress_chunk(compress_obj, compressor_id, lines)
                        del lines[:]
                        lines_size = 0

                    if line_size > self.MAX_CHUNK_SIZE:
                        compressed = _thd_compress_chunk(compress_obj, compressor_id, [line_bytes])
                        compressed_chunk, _, _ = compressed
                        # check if compressed size is compliant with DB row limit
                        if len(compressed_chunk) > self.MAX_CHUNK_SIZE:
                            compressed = _thd_compress_chunk(
                                compress_obj, compressor_id, [_truncate_line(line_bytes)]
                            )
                        yield compressed
                    else:
                        lines.append(line_bytes)

                if lines:
                    yield _thd_compress_chunk(compress_obj, compressor_id, lines)

        assert content[-1] == '\n'

        num_lines = await self.db.pool.do(_thd_get_numlines)
        if num_lines is None:
            # ignore a missing log
            return None

        # Break the content up into chunks
        chunk_first_line = last_line = num_lines
        async for (
            compressed_chunk,
            compressed_id,
            chunk_lines_count,
        ) in _async_iter_on_pool(
            partial(
                _thd_iter_chunk_compress,
                content=content,
            ),
            reactor=self.master.reactor,
            provider_threadpool=self._compression_pool,
            # In theory, memory usage could grow to:
            # MAX_CHUNK_SIZE * max_backlog PER thread (capped by _compression_pool.maxthreads)
            # with:
            #   - MAX_CHUNK_SIZE = 64KB
            #   - max_backlog = 100
            # ~6MB per thread
            max_backlog=100,
        ):
            last_line = chunk_first_line + chunk_lines_count - 1

            await self.db.pool.do(
                _thd_insert_chunk,
                first_line=chunk_first_line,
                last_line=last_line,
                content=compressed_chunk,
                compressed_id=compressed_id,
            )

            chunk_first_line = last_line + 1

        await self.db.pool.do(_thd_update_num_lines, last_line + 1)
        return num_lines, last_line

    def finishLog(self, logid: int) -> defer.Deferred[None]:
        def thdfinishLog(conn) -> None:
            tbl = self.db.model.logs
            q = tbl.update().where(tbl.c.id == logid)
            conn.execute(q.values(complete=1))

        return self.db.pool.do_with_transaction(thdfinishLog)

    @async_to_deferred
    async def compressLog(self, logid: int, force: bool = False) -> int:
        """
        returns the size (in bytes) saved.
        """
        tbl = self.db.model.logchunks

        def _thd_gather_chunks_to_process(conn: SAConnection) -> list[tuple[int, int]]:
            """
            returns the total size of chunks and a list of chunks to group.
            chunks list is empty if not force, and no chunks would be grouped.
            """
            q = (
                sa.select(
                    tbl.c.first_line,
                    tbl.c.last_line,
                    sa.func.length(tbl.c.content),
                )
                .where(tbl.c.logid == logid)
                .order_by(tbl.c.first_line)
            )

            rows = conn.execute(q)

            # get the first chunk to seed new_chunks list
            first_chunk = next(rows, None)
            if first_chunk is None:
                # no chunks in log, early out
                return []

            grouped_chunks: list[tuple[int, int]] = [
                (first_chunk.first_line, first_chunk.last_line)
            ]

            # keep track of how many chunks we use now
            # to compare with grouped chunks and
            # see if we need to do some work
            # start at 1 since we already queries one above
            current_chunk_count = 1

            current_group_new_size = first_chunk.length_1
            # first pass, we fetch the full list of chunks (without content) and find out
            # the chunk groups which could use some gathering.
            for row in rows:
                current_chunk_count += 1

                chunk_first_line: int = row.first_line
                chunk_last_line: int = row.last_line
                chunk_size: int = row.length_1

                group_first_line, _group_last_line = grouped_chunks[-1]

                can_merge_chunks = (
                    # note that we count the compressed size for efficiency reason
                    # unlike to the on-the-flow chunk splitter
                    current_group_new_size + chunk_size <= self.MAX_CHUNK_SIZE
                    and (chunk_last_line - group_first_line) <= self.MAX_CHUNK_LINES
                )
                if can_merge_chunks:
                    # merge chunks, since we ordered the query by 'first_line'
                    # and we assume that chunks are contiguous, it's pretty easy
                    grouped_chunks[-1] = (group_first_line, chunk_last_line)
                    current_group_new_size += chunk_size
                else:
                    grouped_chunks.append((chunk_first_line, chunk_last_line))
                    current_group_new_size = chunk_size

            rows.close()

            if not force and current_chunk_count <= len(grouped_chunks):
                return []

            return grouped_chunks

        def _thd_get_chunks_content(
            conn: SAConnection,
            first_line: int,
            last_line: int,
        ) -> list[tuple[int, bytes]]:
            q = (
                sa.select(tbl.c.content, tbl.c.compressed)
                .where(tbl.c.logid == logid)
                .where(tbl.c.first_line >= first_line)
                .where(tbl.c.last_line <= last_line)
                .order_by(tbl.c.first_line)
            )
            rows = conn.execute(q)
            content = [(row.compressed, row.content) for row in rows]
            rows.close()
            return content

        def _thd_replace_chunks_by_new_grouped_chunk(
            conn: SAConnection,
            first_line: int,
            last_line: int,
            new_compressed_id: int,
            new_content: bytes,
        ) -> None:
            # Transaction is necessary so that readers don't see disappeared chunks
            with conn.begin():
                # we remove the chunks that we are compressing
                deletion_query = (
                    tbl.delete()
                    .where(tbl.c.logid == logid)
                    .where(tbl.c.first_line >= first_line)
                    .where(tbl.c.last_line <= last_line)
                )
                conn.execute(deletion_query).close()

                # and we recompress them in one big chunk
                conn.execute(
                    tbl.insert(),
                    {
                        "logid": logid,
                        "first_line": first_line,
                        "last_line": last_line,
                        "content": new_content,
                        "compressed": new_compressed_id,
                    },
                ).close()

                conn.commit()

        def _thd_recompress_chunks(
            compressed_chunks: list[tuple[int, bytes]],
            compress_obj: CompressObjInterface,
        ) -> tuple[bytes, int]:
            """This has to run in the compression thread pool"""
            # decompress this group of chunks. Note that the content is binary bytes.
            # no need to decode anything as we are going to put in back stored as bytes anyway
            chunks: list[bytes] = []
            bytes_saved = 0
            for idx, (chunk_compress_id, chunk_content) in enumerate(compressed_chunks):
                bytes_saved += len(chunk_content)

                # trailing line-ending is stripped from chunks
                # need to add it back, except for the last one
                if idx != 0:
                    chunks.append(compress_obj.compress(b'\n'))

                uncompressed_content = self._get_compressor(chunk_compress_id).read(chunk_content)
                chunks.append(compress_obj.compress(uncompressed_content))

            chunks.append(compress_obj.flush())
            new_content = b''.join(chunks)
            bytes_saved -= len(new_content)
            return new_content, bytes_saved

        chunk_groups = await self.db.pool.do(_thd_gather_chunks_to_process)
        if not chunk_groups:
            return 0

        total_bytes_saved: int = 0

        compressed_id, compressor = self._get_configured_compressor()
        compress_obj = compressor.CompressObj()
        for group_first_line, group_last_line in chunk_groups:
            compressed_chunks = await self.db.pool.do(
                _thd_get_chunks_content,
                first_line=group_first_line,
                last_line=group_last_line,
            )

            new_content, bytes_saved = await self._defer_to_compression_pool(
                _thd_recompress_chunks,
                compressed_chunks=compressed_chunks,
                compress_obj=compress_obj,
            )

            total_bytes_saved += bytes_saved

            await self.db.pool.do(
                _thd_replace_chunks_by_new_grouped_chunk,
                first_line=group_first_line,
                last_line=group_last_line,
                new_compressed_id=compressed_id,
                new_content=new_content,
            )

        return total_bytes_saved

    def deleteOldLogChunks(self, older_than_timestamp: int) -> defer.Deferred[int]:
        def thddeleteOldLogs(conn) -> int:
            model = self.db.model
            res = conn.execute(sa.select(sa.func.count(model.logchunks.c.logid)))
            count1 = res.fetchone()[0]
            res.close()

            # update log types older than timestamps
            # we do it first to avoid having UI discrepancy

            # N.B.: we utilize the fact that steps.id is auto-increment, thus steps.started_at
            # times are effectively sorted and we only need to find the steps.id at the upper
            # bound of steps to update.

            # SELECT steps.id from steps WHERE steps.started_at < older_than_timestamp ORDER BY
            # steps.id DESC LIMIT 1;
            res = conn.execute(
                sa.select(model.steps.c.id)
                .where(model.steps.c.started_at < older_than_timestamp)
                .order_by(model.steps.c.id.desc())
                .limit(1)
            )
            res_list = res.fetchone()
            stepid_max = None
            if res_list:
                stepid_max = res_list[0]
            res.close()

            # UPDATE logs SET logs.type = 'd' WHERE logs.stepid <= stepid_max AND type != 'd';
            if stepid_max:
                res = conn.execute(
                    model.logs.update()
                    .where(sa.and_(model.logs.c.stepid <= stepid_max, model.logs.c.type != 'd'))
                    .values(type='d')
                )
                conn.commit()
                res.close()

            # query all logs with type 'd' and delete their chunks.
            if self.db._engine.dialect.name == 'sqlite':
                # sqlite does not support delete with a join, so for this case we use a subquery,
                # which is much slower
                q = sa.select(model.logs.c.id)
                q = q.select_from(model.logs)
                q = q.where(model.logs.c.type == 'd')

                # delete their logchunks
                q = model.logchunks.delete().where(model.logchunks.c.logid.in_(q))
            else:
                q = model.logchunks.delete()
                q = q.where(model.logs.c.id == model.logchunks.c.logid)
                q = q.where(model.logs.c.type == 'd')

            res = conn.execute(q)
            conn.commit()
            res.close()
            res = conn.execute(sa.select(sa.func.count(model.logchunks.c.logid)))
            count2 = res.fetchone()[0]
            res.close()
            return count1 - count2

        return self.db.pool.do(thddeleteOldLogs)

    def _model_from_row(self, row):
        return LogModel(
            id=row.id,
            name=row.name,
            slug=row.slug,
            stepid=row.stepid,
            complete=bool(row.complete),
            num_lines=row.num_lines,
            type=row.type,
        )


async def _async_iter_on_pool(
    generator_sync: Callable[[], Generator[_T, None, None]],
    *,
    reactor: IReactorThreads,
    provider_threadpool: threadpool.ThreadPool | None = None,
    max_backlog: int = 1,
    wait_backlog_consuption: bool = True,
) -> AsyncGenerator[_T, None]:
    """
    Utility to transform a sync `Generator` function into an `AsyncGenerator`
    by executing it on a threadpool.

    :param generator_sync:
        sync Generator function (if arguments are necessary, use functools.partial)

    :param reactor: Twisted reactor to use

    :param provider_threadpool:
        Threadpool to run the Generator on (default to reactor's ThreadPool)

    :param max_backlog:
        Maximum size of the buffer used to communicate between sync and async Generators.

        A value of 0 or less means unlimited.

        When the buffer contains `max_backlog` items,
        the threaded sync Generator will wait until at least one element is consumed.

        Note: this is forced to `0` if in unit tests and `provider_threadpool` is a `NonThreadPool`.

    :param wait_backlog_consuption:
        If `True`, will wait until all items in the buffer are consumed.

        This is used to prevent a new threadpool task to run,
        potentially creating a new buffer consuming memory
        while the previous buffer is still in use.

        Note: this is forced to `False` if in unit tests and `provider_threadpool` is a `NonThreadPool`.
    """

    if provider_threadpool is None:
        provider_threadpool = reactor.getThreadPool()

    # create a single element queue as to
    # occupy a thread of the pool
    # avoiding too many compressed chunks in memory awaiting DB insert
    # use 0 (unlimited) in tests as there isn't really a threadpool / reactor running
    if get_is_in_unit_tests():
        from buildbot.test.fake.reactor import NonThreadPool

        if isinstance(provider_threadpool, NonThreadPool):
            max_backlog = 0
            wait_backlog_consuption = False

    queue: defer.DeferredQueue[_T | _CloseObj] = defer.DeferredQueue()

    condition = threading.Condition()

    # dummy object that resolve the callback of the task.
    # Needed as we can't know what the callable will provide,
    # so None, False, ... can't be used.
    # But, we know that callback will return None, so we can
    # override it's callback result
    class _CloseObj:
        pass

    close_obj = _CloseObj()

    def _can_put_in_queue():
        return max_backlog <= 0 or len(queue.pending) < max_backlog

    def _provider_wrapped() -> None:
        try:
            for item in generator_sync():
                with condition:
                    condition.wait_for(_can_put_in_queue)
                reactor.callFromThread(queue.put, item)
        finally:
            if wait_backlog_consuption:
                with condition:
                    condition.wait_for(lambda: len(queue.pending) <= 0)

    def _put_close(res: None | Failure) -> None | Failure:
        queue.put(close_obj)
        return res

    worker_task = threads.deferToThreadPool(
        reactor,
        provider_threadpool,
        _provider_wrapped,
    ).addBoth(callback=_put_close)

    while (item := await queue.get()) is not close_obj:
        assert not isinstance(item, _CloseObj)
        with condition:
            condition.notify()
        yield item

    assert worker_task.called
    # so that if task ended in exception, it's correctly propagated
    # but only if error, as await a successfully resolved Deferred will
    # never finish
    if isinstance(worker_task.result, Failure):
        await worker_task
