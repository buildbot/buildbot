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


from twisted.internet import defer

from buildbot.test.fakedb.base import FakeDBComponent
from buildbot.test.fakedb.row import Row
from buildbot.test.util import validation


class Log(Row):
    table = "logs"

    defaults = dict(
        id=None,
        name='log29',
        slug='log29',
        stepid=None,
        complete=0,
        num_lines=0,
        type='s')

    id_column = 'id'
    required_columns = ('stepid', )


class LogChunk(Row):
    table = "logchunks"

    defaults = dict(
        logid=None,
        first_line=0,
        last_line=0,
        content='',
        compressed=0)

    required_columns = ('logid', )
    # 'content' column is sa.LargeBinary, it's bytestring.
    binary_columns = ('content',)


class FakeLogsComponent(FakeDBComponent):

    def setUp(self):
        self.logs = {}
        self.log_lines = {}  # { logid : [ lines ] }

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, Log):
                self.logs[row.id] = row.values.copy()
        for row in rows:
            if isinstance(row, LogChunk):
                lines = self.log_lines.setdefault(row.logid, [])
                # make sure there are enough slots in the list
                if len(lines) < row.last_line + 1:
                    lines.append([None] * (row.last_line + 1 - len(lines)))
                row_lines = row.content.decode('utf-8').split('\n')
                lines[row.first_line:row.last_line + 1] = row_lines

    # component methods

    def _newId(self):
        id = 100
        while id in self.logs:
            id += 1
        return id

    def _row2dict(self, row):
        return dict(
            id=row['id'],
            stepid=row['stepid'],
            name=row['name'],
            slug=row['slug'],
            complete=bool(row['complete']),
            num_lines=row['num_lines'],
            type=row['type'])

    def getLog(self, logid):
        row = self.logs.get(logid)
        if not row:
            return defer.succeed(None)
        return defer.succeed(self._row2dict(row))

    def getLogBySlug(self, stepid, slug):
        row = None
        for row in self.logs.values():
            if row['slug'] == slug and row['stepid'] == stepid:
                break
        else:
            return defer.succeed(None)
        return defer.succeed(self._row2dict(row))

    def getLogs(self, stepid=None):
        return defer.succeed([
            self._row2dict(row)
            for row in self.logs.values()
            if row['stepid'] == stepid])

    def getLogLines(self, logid, first_line, last_line):
        if logid not in self.logs or first_line > last_line:
            return defer.succeed('')
        lines = self.log_lines.get(logid, [])
        rv = lines[first_line:last_line + 1]
        return defer.succeed('\n'.join(rv) + '\n' if rv else '')

    def addLog(self, stepid, name, slug, type):
        id = self._newId()
        self.logs[id] = dict(id=id, stepid=stepid,
                             name=name, slug=slug, type=type,
                             complete=0, num_lines=0)
        self.log_lines[id] = []
        return defer.succeed(id)

    def appendLog(self, logid, content):
        validation.verifyType(self.t, 'logid', logid,
                              validation.IntValidator())
        validation.verifyType(self.t, 'content', content,
                              validation.StringValidator())
        self.t.assertEqual(content[-1], '\n')
        content = content[:-1].split('\n')
        lines = self.log_lines[logid]
        lines.extend(content)
        num_lines = self.logs[logid]['num_lines'] = len(lines)
        return defer.succeed((num_lines - len(content), num_lines - 1))

    def finishLog(self, logid):
        if id in self.logs:
            self.logs['id'].complete = 1
        return defer.succeed(None)

    def compressLog(self, logid, force=False):
        return defer.succeed(None)

    def deleteOldLogChunks(self, older_than_timestamp):
        # not implemented
        self._deleted = older_than_timestamp
        return defer.succeed(1)
