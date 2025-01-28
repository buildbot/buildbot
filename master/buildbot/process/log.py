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

import re
from collections import defaultdict

from twisted.internet import defer
from twisted.internet import threads
from twisted.python import log

from buildbot import util
from buildbot.util import lineboundaries
from buildbot.util.twisted import async_to_deferred


class Log:
    _byType: dict[str, type[Log]] = {}

    def __init__(self, master, name, type, logid, decoder):
        self.type = type
        self.logid = logid
        self.master = master
        self.name = name

        self.subPoint = util.subscription.SubscriptionPoint(f"{name!r} log")
        self.subscriptions = {}
        self._finishing = False
        self.finished = False
        self.finishWaiters = []
        self._had_errors = False
        self.lock = defer.DeferredLock()
        self.decoder = decoder

    @staticmethod
    def _decoderFromString(cfg):
        """
        Return a decoder function.
        If cfg is a string such as 'latin-1' or u'latin-1',
        then we return a new lambda, s.decode().
        If cfg is already a lambda or function, then we return that.
        """
        if isinstance(cfg, (bytes, str)):
            return lambda s: s.decode(cfg, 'replace')
        return cfg

    @classmethod
    def new(cls, master, name, type, logid, logEncoding):
        type = str(type)
        try:
            subcls = cls._byType[type]
        except KeyError as e:
            raise RuntimeError(f"Invalid log type {type!r}") from e
        decoder = Log._decoderFromString(logEncoding)
        return subcls(master, name, type, logid, decoder)

    def getName(self) -> str:
        return self.name

    # subscriptions

    def subscribe(self, callback) -> util.subscription.Subscription:
        return self.subPoint.subscribe(callback)

    # adding lines

    @defer.inlineCallbacks
    def addRawLines(self, lines):
        # used by subclasses to add lines that are already appropriately
        # formatted for the log type, and newline-terminated
        assert lines[-1] == '\n'
        assert not self.finished
        yield self.lock.run(lambda: self.master.data.updates.appendLog(self.logid, lines))

    # completion

    def isFinished(self) -> bool:
        return self.finished

    def waitUntilFinished(self):
        d = defer.Deferred()
        if self.finished:
            d.succeed(None)
        else:
            self.finishWaiters.append(d)
        return d

    def had_errors(self) -> bool:
        return self._had_errors

    @defer.inlineCallbacks
    def finish(self):
        assert not self._finishing, "Did you maybe forget to yield the method?"
        assert not self.finished
        self._finishing = True

        def fToRun():
            self.finished = True
            return self.master.data.updates.finishLog(self.logid)

        yield self.lock.run(fToRun)
        # notify subscribers *after* finishing the log
        self.subPoint.deliver(None, None)

        yield self.subPoint.waitForDeliveriesToFinish()

        # notify those waiting for finish
        for d in self.finishWaiters:
            d.callback(None)

        self._had_errors = len(self.subPoint.pop_exceptions()) > 0

        # start a compressLog call but don't make our caller wait for
        # it to complete
        d = self.master.data.updates.compressLog(self.logid)
        d.addErrback(log.err, f"while compressing log {self.logid} (ignored)")
        self.master.db.run_db_task(d)
        self._finishing = False


class PlainLog(Log):
    def __init__(self, master, name, type, logid, decoder):
        super().__init__(master, name, type, logid, decoder)

        self.lbf = lineboundaries.LineBoundaryFinder()

    @async_to_deferred
    async def addContent(self, text: str | bytes) -> None:
        if not isinstance(text, str):
            text = self.decoder(text)
        # add some text in the log's default stream
        lines = await threads.deferToThread(self.lbf.append, text)
        if lines is not None:
            self.subPoint.deliver(None, lines)
            await self.addRawLines(lines)

    @async_to_deferred
    async def finish(self) -> None:
        lines = await threads.deferToThread(self.lbf.flush)
        if lines is not None:
            self.subPoint.deliver(None, lines)
            await self.addRawLines(lines)
        await super().finish()


class TextLog(PlainLog):
    pass


Log._byType['t'] = TextLog


class HtmlLog(PlainLog):
    pass


Log._byType['h'] = HtmlLog


class StreamLog(Log):
    pat = re.compile('^', re.M)

    def __init__(self, step, name, type, logid, decoder):
        super().__init__(step, name, type, logid, decoder)
        self.lbfs = defaultdict(lineboundaries.LineBoundaryFinder)

    @async_to_deferred
    async def _on_whole_lines(self, stream, lines) -> None:
        # deliver the un-annotated version to subscribers
        self.subPoint.deliver(stream, lines)
        # strip the last character, as the regexp will add a
        # prefix character after the trailing newline
        lines = await threads.deferToThread(self.pat.sub, stream, lines)
        await self.addRawLines(lines[:-1])

    @async_to_deferred
    async def split_lines(self, stream, text) -> None:
        lines = await threads.deferToThread(self.lbfs[stream].append, text)
        if lines is not None:
            await self._on_whole_lines(stream, lines)

    def addStdout(self, text):
        if not isinstance(text, str):
            text = self.decoder(text)
        return self.split_lines('o', text)

    def addStderr(self, text):
        if not isinstance(text, str):
            text = self.decoder(text)
        return self.split_lines('e', text)

    def addHeader(self, text):
        if not isinstance(text, str):
            text = self.decoder(text)
        return self.split_lines('h', text)

    def add_stdout_lines(self, text):
        if not isinstance(text, str):
            text = self.decoder(text)
        return self._on_whole_lines('o', text)

    def add_stderr_lines(self, text):
        if not isinstance(text, str):
            text = self.decoder(text)
        return self._on_whole_lines('e', text)

    def add_header_lines(self, text):
        if not isinstance(text, str):
            text = self.decoder(text)
        return self._on_whole_lines('h', text)

    @async_to_deferred
    async def finish(self) -> None:
        async def _process(stream, lbf: lineboundaries.LineBoundaryFinder) -> None:
            lines = await threads.deferToThread(lbf.flush)
            if lines is not None:
                await self._on_whole_lines(stream, lines)

        await defer.DeferredList(
            (
                defer.Deferred.fromCoroutine(_process(stream, lbf))
                for stream, lbf in self.lbfs.items()
            )
        )
        await super().finish()


Log._byType['s'] = StreamLog
