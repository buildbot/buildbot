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

from typing import Callable

from twisted.internet import defer

from buildbot import util
from buildbot.util import lineboundaries
from buildbot.util.twisted import async_to_deferred


class FakeLogFile:
    def __init__(self, name: str) -> None:
        self.name = name
        self.header = ''
        self.stdout = ''
        self.stderr = ''
        self.lbfs: dict[str, lineboundaries.LineBoundaryFinder] = {}
        self.finished = False
        self._had_errors = False
        self.subPoint = util.subscription.SubscriptionPoint(f"{name!r} log")

    def getName(self) -> str:
        return self.name

    def subscribe(self, callback: Callable) -> util.subscription.Subscription:
        return self.subPoint.subscribe(callback)

    def _getLbf(self, stream: str) -> lineboundaries.LineBoundaryFinder:
        try:
            return self.lbfs[stream]
        except KeyError:
            lbf = self.lbfs[stream] = lineboundaries.LineBoundaryFinder()
            return lbf

    def _on_whole_lines(self, stream: str | None, lines: str | None) -> None:
        self.subPoint.deliver(stream, lines)
        assert not self.finished

    def _split_lines(self, stream: str, text: str) -> None:
        lbf = self._getLbf(stream)
        lines = lbf.append(text)
        if lines is None:
            return
        self._on_whole_lines(stream, lines)

    def addHeader(self, text: str | bytes) -> defer.Deferred[None]:
        if not isinstance(text, str):
            text = text.decode('utf-8')
        self.header += text
        self._split_lines('h', text)
        return defer.succeed(None)

    def addStdout(self, text: str | bytes) -> defer.Deferred[None]:
        if not isinstance(text, str):
            text = text.decode('utf-8')
        self.stdout += text
        self._split_lines('o', text)
        return defer.succeed(None)

    def addStderr(self, text: str | bytes) -> defer.Deferred[None]:
        if not isinstance(text, str):
            text = text.decode('utf-8')
        self.stderr += text
        self._split_lines('e', text)
        return defer.succeed(None)

    def add_header_lines(self, text: str | bytes) -> defer.Deferred[None]:
        if not isinstance(text, str):
            text = text.decode('utf-8')
        self.header += text
        self._on_whole_lines('h', text)
        return defer.succeed(None)

    def add_stdout_lines(self, text: str | bytes) -> defer.Deferred[None]:
        if not isinstance(text, str):
            text = text.decode('utf-8')
        self.stdout += text
        self._on_whole_lines('o', text)
        return defer.succeed(None)

    def add_stderr_lines(self, text: str | bytes) -> defer.Deferred[None]:
        if not isinstance(text, str):
            text = text.decode('utf-8')
        self.stderr += text
        self._on_whole_lines('e', text)
        return defer.succeed(None)

    def had_errors(self) -> bool:
        return self._had_errors

    def flush(self) -> defer.Deferred[None]:
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
        self._had_errors = len(self.subPoint.pop_exceptions()) > 0  # type: ignore[arg-type]

    def fakeData(self, header: str = '', stdout: str = '', stderr: str = '') -> None:
        if header:
            self.header += header
        if stdout:
            self.stdout += stdout
        if stderr:
            self.stderr += stderr
