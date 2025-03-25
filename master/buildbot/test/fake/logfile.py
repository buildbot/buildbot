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

from buildbot import util
from buildbot.util import lineboundaries
from buildbot.util.twisted import async_to_deferred


class FakeLogFile:
    def __init__(self, name):
        self.name = name
        self.header = ''
        self.stdout = ''
        self.stderr = ''
        self.lbfs = {}
        self.finished = False
        self._had_errors = False
        self.subPoint = util.subscription.SubscriptionPoint(f"{name!r} log")

    def getName(self):
        return self.name

    def subscribe(self, callback):
        return self.subPoint.subscribe(callback)

    def _getLbf(self, stream):
        try:
            return self.lbfs[stream]
        except KeyError:
            lbf = self.lbfs[stream] = lineboundaries.LineBoundaryFinder()
            return lbf

    def _on_whole_lines(self, stream, lines):
        self.subPoint.deliver(stream, lines)
        assert not self.finished

    def _split_lines(self, stream, text):
        lbf = self._getLbf(stream)
        lines = lbf.append(text)
        if lines is None:
            return
        self._on_whole_lines(stream, lines)

    def addHeader(self, text):
        if not isinstance(text, str):
            text = text.decode('utf-8')
        self.header += text
        self._split_lines('h', text)
        return defer.succeed(None)

    def addStdout(self, text):
        if not isinstance(text, str):
            text = text.decode('utf-8')
        self.stdout += text
        self._split_lines('o', text)
        return defer.succeed(None)

    def addStderr(self, text):
        if not isinstance(text, str):
            text = text.decode('utf-8')
        self.stderr += text
        self._split_lines('e', text)
        return defer.succeed(None)

    def add_header_lines(self, text):
        if not isinstance(text, str):
            text = text.decode('utf-8')
        self.header += text
        self._on_whole_lines('h', text)
        return defer.succeed(None)

    def add_stdout_lines(self, text):
        if not isinstance(text, str):
            text = text.decode('utf-8')
        self.stdout += text
        self._on_whole_lines('o', text)
        return defer.succeed(None)

    def add_stderr_lines(self, text):
        if not isinstance(text, str):
            text = text.decode('utf-8')
        self.stderr += text
        self._on_whole_lines('e', text)
        return defer.succeed(None)

    def had_errors(self):
        return self._had_errors

    def flush(self):
        for stream, lbf in self.lbfs.items():
            lines = lbf.flush()
            if lines is not None:
                self.subPoint.deliver(stream, lines)
        return defer.succeed(None)

    @async_to_deferred
    async def finish(self) -> None:
        assert not self.finished

        await self.flush()
        self.finished = True

        # notify subscribers *after* finishing the log
        self.subPoint.deliver(None, None)

        await self.subPoint.waitForDeliveriesToFinish()
        self._had_errors = len(self.subPoint.pop_exceptions()) > 0

    def fakeData(self, header='', stdout='', stderr=''):
        if header:
            self.header += header
        if stdout:
            self.stdout += stdout
        if stderr:
            self.stderr += stderr
