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

from buildbot.db import base
from twisted.internet import defer
from twisted.python import log


class LogsConnectorComponent(base.DBConnectorComponent):

    # Postgres and MySQL will both allow bigger sizes than this.  The limit
    # for MySQL appears to be max_packet_size (default 1M).
    MAX_CHUNK_SIZE = 65536

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

    def getLogByName(self, stepid, name):
        tbl = self.db.model.logs
        return self._getLog((tbl.c.name == name) & (tbl.c.stepid == stepid))

    def getLogs(self, stepid):
        def thd(conn):
            tbl = self.db.model.logs
            q = tbl.select()
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
                assert not row.compressed, "compressed rows not supported yet"
                content = row.content.decode('utf-8')
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
                        idx = content.rindex('\n', 0, idx - 1)
                    content = content[:idx]
                rv.append(content)
            return u'\n'.join(rv) + u'\n' if rv else u''
        return self.db.pool.do(thd)

    def addLog(self, stepid, name, type):
        assert type in 'tsh', "Log type must be one of t, s, or h"

        def thd(conn):
            try:
                r = conn.execute(self.db.model.logs.insert(),
                                 dict(name=name, stepid=stepid, complete=0,
                                      num_lines=0, type=type))
                return r.inserted_primary_key[0]
            except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                raise KeyError("log with name '%r' already exists in this step" % (name,))
        return self.db.pool.do(thd)

    def appendLog(self, logid, content):
        # check for trailing newline and strip it for storage -- chunks omit
        # the trailing newline
        assert content[-1] == u'\n'
        content = content[:-1]

        def thd(conn):
            q = sa.select([self.db.model.logs.c.num_lines])
            q = q.where(self.db.model.logs.c.id == logid)
            res = conn.execute(q)
            row = res.fetchone()
            res.close()
            if not row:
                return  # ignore a missing log

            # Break the content up into chunks.  This takes advantage of the
            # fact that no character but u'\n' maps to b'\n' in UTF-8.

            first_line = chunk_first_line = row[0]
            remaining = content.encode('utf-8')
            while remaining:
                chunk, remaining = self._splitBigChunk(remaining, logid)

                last_line = chunk_first_line + chunk.count('\n')
                conn.execute(self.db.model.logchunks.insert(),
                             dict(logid=logid, first_line=chunk_first_line,
                                  last_line=last_line, content=chunk,
                                  compressed=0))
                chunk_first_line = last_line + 1

            conn.execute(self.db.model.logs.update(whereclause=(self.db.model.logs.c.id == logid)),
                         num_lines=last_line + 1)
            return (first_line, last_line)
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

    def compressLog(self, logid):
        # TODO: compression not supported yet
        return defer.succeed(None)

    def _logdictFromRow(self, row):
        rv = dict(row)
        rv['complete'] = bool(rv['complete'])
        return rv
