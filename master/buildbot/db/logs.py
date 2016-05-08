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
import sqlalchemy as sa
from future.utils import itervalues
from twisted.internet import defer
from twisted.python import log

from buildbot.db import base


def dumps_gzip(data):
    import zlib
    return zlib.compress(data, 9)


def read_gzip(data):
    import zlib
    return zlib.decompress(data)


def dumps_lz4(data):
    import lz4
    return lz4.dumps(data)


def read_lz4(data):
    import lz4
    return lz4.loads(data)


def dumps_bz2(data):
    import bz2
    return bz2.compress(data, 9)


def read_bz2(data):
    import bz2
    return bz2.decompress(data)


class LogsConnectorComponent(base.DBConnectorComponent):

    # Postgres and MySQL will both allow bigger sizes than this.  The limit
    # for MySQL appears to be max_packet_size (default 1M).
    MAX_CHUNK_SIZE = 65536
    COMPRESSION_MODE = {"raw": {"id": 0, "dumps": lambda x: x, "read": lambda x: x},
                        "gz": {"id": 1, "dumps": dumps_gzip, "read": read_gzip},
                        "bz2": {"id": 2, "dumps": dumps_bz2, "read": read_bz2},
                        "lz4": {"id": 3, "dumps": dumps_lz4, "read": read_lz4}}
    COMPRESSION_BYID = dict((x["id"], x) for x in itervalues(COMPRESSION_MODE))
    total_raw_bytes = 0
    total_compressed_bytes = 0

    def _getLog(self, whereclause):
        def thd(conn):
            q = self.db.model.logs.select(whereclause=whereclause)
            res = conn.execute(q)
            row = res.fetchone()

            rv = None
            if row:
                rv = self._logdictFromRow(row)
            res.close()
            return rv
        return self.db.pool.do(thd)

    def getLog(self, logid):
        return self._getLog(self.db.model.logs.c.id == logid)

    def getLogBySlug(self, stepid, slug):
        tbl = self.db.model.logs
        return self._getLog((tbl.c.slug == slug) & (tbl.c.stepid == stepid))

    def getLogs(self, stepid=None):
        def thd(conn):
            tbl = self.db.model.logs
            q = tbl.select()
            if stepid is not None:
                q = q.where(tbl.c.stepid == stepid)
            q = q.order_by(tbl.c.id)
            res = conn.execute(q)
            return [self._logdictFromRow(row) for row in res.fetchall()]
        return self.db.pool.do(thd)

    def getLogLines(self, logid, first_line, last_line):
        def thd(conn):
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
                data = self.COMPRESSION_BYID[
                    row.compressed]["read"](row.content)
                content = data.decode('utf-8')

                if row.first_line < first_line:
                    idx = -1
                    count = first_line - row.first_line
                    for _ in xrange(count):
                        idx = content.index('\n', idx + 1)
                    content = content[idx + 1:]
                if row.last_line > last_line:
                    idx = len(content) + 1
                    count = row.last_line - last_line
                    for _ in xrange(count):
                        idx = content.rindex('\n', 0, idx)
                    content = content[:idx]
                rv.append(content)
            return u'\n'.join(rv) + u'\n' if rv else u''
        return self.db.pool.do(thd)

    def addLog(self, stepid, name, slug, type):
        assert type in 'tsh', "Log type must be one of t, s, or h"

        def thd(conn):
            try:
                r = conn.execute(self.db.model.logs.insert(),
                                 dict(name=name, slug=slug, stepid=stepid,
                                      complete=0, num_lines=0, type=type))
                return r.inserted_primary_key[0]
            except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                raise KeyError(
                    "log with slug '%r' already exists in this step" % (slug,))
        return self.db.pool.do(thd)

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
            last_line = chunk_first_line + chunk.count('\n')

            chunk, compressed_id = self.thdCompressChunk(chunk)
            conn.execute(self.db.model.logchunks.insert(),
                         dict(logid=logid, first_line=chunk_first_line,
                              last_line=last_line, content=chunk,
                              compressed=compressed_id))
            chunk_first_line = last_line + 1

        conn.execute(self.db.model.logs.update(whereclause=(self.db.model.logs.c.id == logid)),
                     num_lines=last_line + 1)
        return first_line, last_line

    def thdAppendLog(self, conn, logid, content):
        # check for trailing newline and strip it for storage -- chunks omit
        # the trailing newline
        assert content[-1] == u'\n'
        content = content[:-1]
        q = sa.select([self.db.model.logs.c.num_lines])
        q = q.where(self.db.model.logs.c.id == logid)
        res = conn.execute(q)
        row = res.fetchone()
        res.close()
        if not row:
            return  # ignore a missing log

        return self.thdSplitAndAppendChunk(conn=conn,
                                           logid=logid,
                                           content=content.encode('utf-8'),
                                           first_line=row[0])

    def appendLog(self, logid, content):
        def thd(conn):
            return self.thdAppendLog(conn, logid, content)

        return self.db.pool.do(thd)

    def _splitBigChunk(self, content, logid):
        """
        Split CONTENT on a line boundary into a prefix smaller than 64k and
        a suffix containing the remainder, omitting the splitting newline.
        """
        # if it's small enough, just return it
        if len(content) < self.MAX_CHUNK_SIZE:
            return content, None

        # find the last newline before the limit
        i = content.rfind('\n', 0, self.MAX_CHUNK_SIZE)
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
        i = content.find('\n', self.MAX_CHUNK_SIZE)
        if i == -1:
            return truncline, None
        else:
            return truncline, content[i + 1:]

    def finishLog(self, logid):
        def thd(conn):
            tbl = self.db.model.logs
            q = tbl.update(whereclause=(tbl.c.id == logid))
            conn.execute(q, complete=1)
        return self.db.pool.do(thd)

    @defer.inlineCallbacks
    def compressLog(self, logid):
        def thd(conn):
            # get the set of chunks
            tbl = self.db.model.logchunks
            q = sa.select([tbl.c.first_line, tbl.c.last_line, sa.func.length(tbl.c.content),
                           tbl.c.compressed])
            q = q.where(tbl.c.logid == logid)
            q = q.order_by(tbl.c.first_line)
            rows = conn.execute(q)
            uncompressed_length = 0
            numchunks = 0
            totlength = 0
            for row in rows:
                if row.compressed == 0:
                    uncompressed_length += row.length_1
                totlength += row.length_1
                numchunks += 1

            # do nothing if its not worth.
            # if uncompressed_length < 200 and numchunks < 4:
            #    return
            q = sa.select(
                [tbl.c.first_line, tbl.c.last_line, tbl.c.content, tbl.c.compressed])
            q = q.where(tbl.c.logid == logid)
            q = q.order_by(tbl.c.first_line)
            rows = conn.execute(q)
            wholelog = ""
            for row in rows:
                wholelog += self.COMPRESSION_BYID[row.compressed][
                    "read"](row.content).decode('utf-8') + "\n"

            if len(wholelog) == 0:
                return 0

            transaction = conn.begin()
            d = tbl.delete()
            d = d.where(tbl.c.logid == logid)
            conn.execute(d)
            conn.execute(self.db.model.logs.update(whereclause=(self.db.model.logs.c.id == logid)),
                         num_lines=0)
            self.thdAppendLog(conn, logid, wholelog)
            transaction.commit()
            q = sa.select([sa.func.sum(sa.func.length(tbl.c.content))])
            q = q.where(tbl.c.logid == logid)
            newsize = conn.execute(q).fetchone()[0]
            return len(wholelog) - newsize

        saved = yield self.db.pool.do(thd)
        defer.returnValue(saved)

    def _logdictFromRow(self, row):
        rv = dict(row)
        rv['complete'] = bool(rv['complete'])
        return rv
