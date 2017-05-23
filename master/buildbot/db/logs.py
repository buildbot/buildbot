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

from __future__ import absolute_import
from __future__ import print_function
from future.builtins import range
from future.utils import itervalues

import sqlalchemy as sa

from twisted.internet import defer
from twisted.python import log

from buildbot.db import base

try:
    # lz4 > 0.9.0
    from lz4.block import compress as dumps_lz4
    from lz4.block import decompress as read_lz4
except ImportError:
    try:
        # lz4 < 0.9.0
        from lz4 import dumps as dumps_lz4
        from lz4 import loads as read_lz4
    except ImportError:  # pragma: no cover
        # config.py actually forbid this code path
        def dumps_lz4(data):
            return data

        def read_lz4(data):
            return data


def dumps_gzip(data):
    import zlib
    return zlib.compress(data, 9)


def read_gzip(data):
    import zlib
    return zlib.decompress(data)


def dumps_bz2(data):
    import bz2
    return bz2.compress(data, 9)


def read_bz2(data):
    import bz2
    return bz2.decompress(data)


class LogsConnectorComponent(base.DBConnectorComponent):

    # Postgres and MySQL will both allow bigger sizes than this.  The limit
    # for MySQL appears to be max_packet_size (default 1M).
    MAX_CHUNK_SIZE = 65536  # a chunk may not be bigger than this
    MAX_CHUNK_LINES = 1000  # a chunk may not have more lines than this
    COMPRESSION_MODE = {"raw": {"id": 0, "dumps": lambda x: x, "read": lambda x: x},
                        "gz": {"id": 1, "dumps": dumps_gzip, "read": read_gzip},
                        "bz2": {"id": 2, "dumps": dumps_bz2, "read": read_bz2},
                        "lz4": {"id": 3, "dumps": dumps_lz4, "read": read_lz4}}
    COMPRESSION_BYID = dict((x["id"], x) for x in itervalues(COMPRESSION_MODE))
    total_raw_bytes = 0
    total_compressed_bytes = 0

    def _getLog(self, whereclause):
        def thd_getLog(conn):
            q = self.db.model.logs.select(whereclause=whereclause)
            res = conn.execute(q)
            row = res.fetchone()

            rv = None
            if row:
                rv = self._logdictFromRow(row)
            res.close()
            return rv
        return self.db.pool.do(thd_getLog)

    def getLog(self, logid):
        return self._getLog(self.db.model.logs.c.id == logid)

    def getLogBySlug(self, stepid, slug):
        tbl = self.db.model.logs
        return self._getLog((tbl.c.slug == slug) & (tbl.c.stepid == stepid))

    def getLogs(self, stepid=None):
        def thdGetLogs(conn):
            tbl = self.db.model.logs
            q = tbl.select()
            if stepid is not None:
                q = q.where(tbl.c.stepid == stepid)
            q = q.order_by(tbl.c.id)
            res = conn.execute(q)
            return [self._logdictFromRow(row) for row in res.fetchall()]
        return self.db.pool.do(thdGetLogs)

    def getLogLines(self, logid, first_line, last_line):
        def thdGetLogLines(conn):
            # get a set of chunks that completely cover the requested range
            tbl = self.db.model.logchunks
            q = sa.select([tbl.c.first_line, tbl.c.last_line,
                           tbl.c.content, tbl.c.compressed])
            q = q.where(tbl.c.logid == logid)
            q = q.where(tbl.c.first_line <= last_line)
            q = q.where(tbl.c.last_line >= first_line)
            q = q.order_by(tbl.c.first_line)
            rv = []
            for row in conn.execute(q):
                # Retrieve associated "reader" and extract the data
                # Note that row.content is stored as bytes, and our caller expects unicode
                data = self.COMPRESSION_BYID[
                    row.compressed]["read"](row.content)
                content = data.decode('utf-8')

                if row.first_line < first_line:
                    idx = -1
                    count = first_line - row.first_line
                    for _ in range(count):
                        idx = content.index('\n', idx + 1)
                    content = content[idx + 1:]
                if row.last_line > last_line:
                    idx = len(content) + 1
                    count = row.last_line - last_line
                    for _ in range(count):
                        idx = content.rindex('\n', 0, idx)
                    content = content[:idx]
                rv.append(content)
            return u'\n'.join(rv) + u'\n' if rv else u''
        return self.db.pool.do(thdGetLogLines)

    def addLog(self, stepid, name, slug, type):
        assert type in 'tsh', "Log type must be one of t, s, or h"

        def thdAddLog(conn):
            try:
                r = conn.execute(self.db.model.logs.insert(),
                                 dict(name=name, slug=slug, stepid=stepid,
                                      complete=0, num_lines=0, type=type))
                return r.inserted_primary_key[0]
            except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                raise KeyError(
                    "log with slug '%r' already exists in this step" % (slug,))
        return self.db.pool.do(thdAddLog)

    def thdCompressChunk(self, chunk):
        # Set the default compressed mode to "raw" id
        compressed_id = self.COMPRESSION_MODE["raw"]["id"]
        self.total_raw_bytes += len(chunk)
        # Do we have to compress the chunk?
        if self.master.config.logCompressionMethod != "raw":
            compressed_mode = self.COMPRESSION_MODE[
                self.master.config.logCompressionMethod]
            compressed_chunk = compressed_mode["dumps"](chunk)
            # Is it useful to compress the chunk?
            if len(chunk) > len(compressed_chunk):
                compressed_id = compressed_mode["id"]
                chunk = compressed_chunk
        self.total_compressed_bytes += len(chunk)
        return chunk, compressed_id

    def thdSplitAndAppendChunk(self, conn, logid, content, first_line):
        # Break the content up into chunks.  This takes advantage of the
        # fact that no character but u'\n' maps to b'\n' in UTF-8.
        remaining = content
        chunk_first_line = last_line = first_line
        while remaining:
            chunk, remaining = self._splitBigChunk(remaining, logid)
            last_line = chunk_first_line + chunk.count(b'\n')

            chunk, compressed_id = self.thdCompressChunk(chunk)
            conn.execute(self.db.model.logchunks.insert(),
                         dict(logid=logid, first_line=chunk_first_line,
                              last_line=last_line, content=chunk,
                              compressed=compressed_id)).close()
            chunk_first_line = last_line + 1
        conn.execute(self.db.model.logs.update(whereclause=(self.db.model.logs.c.id == logid)),
                     num_lines=last_line + 1).close()
        return first_line, last_line

    def thdAppendLog(self, conn, logid, content):
        # check for trailing newline and strip it for storage -- chunks omit
        # the trailing newline
        assert content[-1] == u'\n'
        # Note that row.content is stored as bytes, and our caller is sending unicode
        content = content[:-1].encode('utf-8')
        q = sa.select([self.db.model.logs.c.num_lines])
        q = q.where(self.db.model.logs.c.id == logid)
        res = conn.execute(q)
        num_lines = res.fetchone()
        res.close()
        if not num_lines:
            return  # ignore a missing log

        return self.thdSplitAndAppendChunk(conn=conn,
                                           logid=logid,
                                           content=content,
                                           first_line=num_lines[0])

    def appendLog(self, logid, content):
        def thdappendLog(conn):
            return self.thdAppendLog(conn, logid, content)

        return self.db.pool.do(thdappendLog)

    def _splitBigChunk(self, content, logid):
        """
        Split CONTENT on a line boundary into a prefix smaller than 64k and
        a suffix containing the remainder, omitting the splitting newline.
        """
        # if it's small enough, just return it
        if len(content) < self.MAX_CHUNK_SIZE:
            return content, None

        # find the last newline before the limit
        i = content.rfind(b'\n', 0, self.MAX_CHUNK_SIZE)
        if i != -1:
            return content[:i], content[i + 1:]

        log.msg('truncating long line for log %d' % logid)

        # first, truncate this down to something that decodes correctly
        truncline = content[:self.MAX_CHUNK_SIZE]
        while truncline:
            try:
                truncline.decode('utf-8')
                break
            except UnicodeDecodeError:
                truncline = truncline[:-1]

        # then find the beginning of the next line
        i = content.find(b'\n', self.MAX_CHUNK_SIZE)
        if i == -1:
            return truncline, None
        return truncline, content[i + 1:]

    def finishLog(self, logid):
        def thdfinishLog(conn):
            tbl = self.db.model.logs
            q = tbl.update(whereclause=(tbl.c.id == logid))
            conn.execute(q, complete=1)
        return self.db.pool.do(thdfinishLog)

    @defer.inlineCallbacks
    def compressLog(self, logid, force=False):
        def thdcompressLog(conn):
            tbl = self.db.model.logchunks
            q = sa.select([tbl.c.first_line, tbl.c.last_line, sa.func.length(tbl.c.content),
                           tbl.c.compressed])
            q = q.where(tbl.c.logid == logid)
            q = q.order_by(tbl.c.first_line)

            rows = conn.execute(q)
            todo_gather_list = []
            numchunks = 0
            totlength = 0
            todo_numchunks = 0
            todo_first_line = 0
            todo_last_line = 0
            todo_length = 0
            # first pass, we fetch the full list of chunks (without content) and find out
            # the chunk groups which could use some gathering.
            for row in rows:
                if (todo_length + row.length_1 > self.MAX_CHUNK_SIZE or
                        (row.last_line - todo_first_line) > self.MAX_CHUNK_LINES):
                    if todo_numchunks > 1 or (force and todo_numchunks):
                        # this group is worth re-compressing
                        todo_gather_list.append((todo_first_line, todo_last_line))
                    todo_first_line = row.first_line
                    todo_length = 0
                    todo_numchunks = 0

                todo_last_line = row.last_line
                # note that we count the compressed size for efficiency reason
                # unlike to the on-the-flow chunk splitter
                todo_length += row.length_1
                totlength += row.length_1
                todo_numchunks += 1
                numchunks += 1
            rows.close()

            if totlength == 0:
                # empty log
                return 0

            if todo_numchunks > 1 or (force and todo_numchunks):
                # last chunk group
                todo_gather_list.append((todo_first_line, todo_last_line))
            for todo_first_line, todo_last_line in todo_gather_list:
                # decompress this group of chunks. Note that the content is binary bytes.
                # no need to decode anything as we are going to put in back stored as bytes anyway
                q = sa.select(
                    [tbl.c.first_line, tbl.c.last_line, tbl.c.content, tbl.c.compressed])
                q = q.where(tbl.c.logid == logid)
                q = q.where(tbl.c.first_line >= todo_first_line)
                q = q.where(tbl.c.last_line <= todo_last_line)
                q = q.order_by(tbl.c.first_line)
                rows = conn.execute(q)
                chunk = b""
                for row in rows:
                    if chunk:
                        chunk += b"\n"
                    chunk += self.COMPRESSION_BYID[row.compressed][
                        "read"](row.content)
                rows.close()

                # Transaction is necessary so that readers don't see disappeared chunks
                transaction = conn.begin()

                # we remove the chunks that we are compressing
                d = tbl.delete()
                d = d.where(tbl.c.logid == logid)
                d = d.where(tbl.c.first_line >= todo_first_line)
                d = d.where(tbl.c.last_line <= todo_last_line)
                conn.execute(d).close()

                # and we recompress them in one big chunk
                chunk, compressed_id = self.thdCompressChunk(chunk)
                conn.execute(tbl.insert(),
                             dict(logid=logid, first_line=todo_first_line,
                                  last_line=todo_last_line, content=chunk,
                                  compressed=compressed_id)).close()
                transaction.commit()

            # calculate how many bytes we saved
            q = sa.select([sa.func.sum(sa.func.length(tbl.c.content))])
            q = q.where(tbl.c.logid == logid)
            newsize = conn.execute(q).fetchone()[0]
            return totlength - newsize

        saved = yield self.db.pool.do(thdcompressLog)
        defer.returnValue(saved)

    def deleteOldLogChunks(self, older_than_timestamp):
        def thddeleteOldLogs(conn):
            model = self.db.model
            res = conn.execute(sa.select([sa.func.count(model.logchunks.c.content)]))
            count1 = res.fetchone()[0]
            res.close()

            # update log types older than timestamps
            # we do it first to avoid having UI discrepancy
            res = conn.execute(
                model.logs.update()
                .where(model.logs.c.stepid.in_(
                    sa.select([model.steps.c.id])
                    .where(model.steps.c.started_at < older_than_timestamp)))
                .values(type='d')
            )
            res.close()

            # query all logs with type 'd' and delete their chunks.
            q = sa.select([model.logs.c.id])
            q = q.select_from(model.logs)
            q = q.where(model.logs.c.type == 'd')

            # delete their logchunks
            res = conn.execute(
                model.logchunks.delete()
                .where(model.logchunks.c.logid.in_(q))
            )
            res.close()
            res = conn.execute(sa.select([sa.func.count(model.logchunks.c.content)]))
            count2 = res.fetchone()[0]
            res.close()
            return count1 - count2
        return self.db.pool.do(thddeleteOldLogs)

    def _logdictFromRow(self, row):
        rv = dict(row)
        rv['complete'] = bool(rv['complete'])
        return rv
