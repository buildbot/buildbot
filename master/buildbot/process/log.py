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
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable

from twisted.internet import defer
from twisted.python import log

from buildbot import util
from buildbot.util import lineboundaries

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class Log:
    _byType: dict[str, type[Log]] = {}

    def __init__(
        self,
        master: Any,
        name: str,
        type: str,
        logid: int,
        decoder: Callable[[bytes], str],
    ) -> None:
        self.type = type
        self.logid = logid
        self.master = master
        self.name = name

        self.subPoint = util.subscription.SubscriptionPoint(f"{name!r} log")
        self.subscriptions: dict[Any, Any] = {}
        self._finishing = False
        self.finished = False
        self._had_errors = False
        self.lock = defer.DeferredLock()
        self.decoder = decoder

    @staticmethod
    def _decoderFromString(cfg: str | bytes | Callable[[bytes], str]) -> Callable[[bytes], str]:
        """
        Return a decoder function.
        If cfg is a string such as 'latin-1' or u'latin-1',
        then we return a new lambda, s.decode().
        If cfg is already a lambda or function, then we return that.
        """
        if isinstance(cfg, (bytes, str)):
            return lambda s: s.decode(cfg, 'replace')  # type: ignore[arg-type]
        return cfg

    @classmethod
    def new(cls, master: Any, name: str, type: str, logid: int, logEncoding: Any) -> Log:
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

    def subscribe(self, callback: Callable[..., Any]) -> util.subscription.Subscription:
        return self.subPoint.subscribe(callback)

    # adding lines

    @defer.inlineCallbacks
    def addRawLines(self, lines: str) -> InlineCallbacksType[None]:
        # used by subclasses to add lines that are already appropriately
        # formatted for the log type, and newline-terminated
        assert lines[-1] == '\n'
        assert not self.finished
        yield self.lock.run(lambda: self.master.data.updates.appendLog(self.logid, lines))

    # completion

    def had_errors(self) -> bool:
        return self._had_errors

    def flush(self) -> defer.Deferred[None]:
        return defer.succeed(None)

    @defer.inlineCallbacks
    def finish(self) -> InlineCallbacksType[None]:
        assert not self._finishing, "Did you maybe forget to yield the method?"
        assert not self.finished
        self._finishing = True

        def fToRun() -> defer.Deferred[None]:
            self.finished = True
            return self.master.data.updates.finishLog(self.logid)

        yield self.lock.run(fToRun)
        # notify subscribers *after* finishing the log
        self.subPoint.deliver(None, None)

        yield self.subPoint.waitForDeliveriesToFinish()

        self._had_errors = len(self.subPoint.pop_exceptions()) > 0  # type: ignore[arg-type]

        # start a compressLog call but don't make our caller wait for
        # it to complete
        d = self.master.data.updates.compressLog(self.logid)
        d.addErrback(log.err, f"while compressing log {self.logid} (ignored)")
        self.master.db.run_db_task(d)
        self._finishing = False


class PlainLog(Log):
    def __init__(
        self,
        master: Any,
        name: str,
        type: str,
        logid: int,
        decoder: Callable[[bytes], str],
    ) -> None:
        super().__init__(master, name, type, logid, decoder)

        self.lbf = lineboundaries.LineBoundaryFinder()

    def addContent(self, text: str | bytes) -> defer.Deferred[None]:
        if not isinstance(text, str):
            text = self.decoder(text)
        # add some text in the log's default stream
        lines = self.lbf.append(text)
        if lines is None:
            return defer.succeed(None)
        self.subPoint.deliver(None, lines)
        return self.addRawLines(lines)

    @defer.inlineCallbacks
    def flush(self) -> InlineCallbacksType[None]:
        lines = self.lbf.flush()
        if lines is not None:
            self.subPoint.deliver(None, lines)
            yield self.addRawLines(lines)

    @defer.inlineCallbacks
    def finish(self) -> InlineCallbacksType[None]:
        yield self.flush()
        yield super().finish()


class TextLog(PlainLog):
    pass


Log._byType['t'] = TextLog


class HtmlLog(PlainLog):
    pass


Log._byType['h'] = HtmlLog


class StreamLog(Log):
    pat = re.compile('^', re.M)

    def __init__(
        self,
        step: Any,
        name: str,
        type: str,
        logid: int,
        decoder: Callable[[bytes], str],
    ) -> None:
        super().__init__(step, name, type, logid, decoder)
        self.lbfs: dict[str, lineboundaries.LineBoundaryFinder] = {}

    def _getLbf(self, stream: str) -> lineboundaries.LineBoundaryFinder:
        try:
            return self.lbfs[stream]
        except KeyError:
            lbf = self.lbfs[stream] = lineboundaries.LineBoundaryFinder()
            return lbf

    def _on_whole_lines(self, stream: str, lines: str) -> defer.Deferred[None]:
        # deliver the un-annotated version to subscribers
        self.subPoint.deliver(stream, lines)
        # strip the last character, as the regexp will add a
        # prefix character after the trailing newline
        return self.addRawLines(self.pat.sub(stream, lines)[:-1])

    def split_lines(self, stream: str, text: str) -> defer.Deferred[None]:
        lbf = self._getLbf(stream)
        lines = lbf.append(text)
        if lines is None:
            return defer.succeed(None)
        return self._on_whole_lines(stream, lines)

    def addStdout(self, text: str | bytes) -> defer.Deferred[None]:
        if not isinstance(text, str):
            text = self.decoder(text)
        return self.split_lines('o', text)

    def addStderr(self, text: str | bytes) -> defer.Deferred[None]:
        if not isinstance(text, str):
            text = self.decoder(text)
        return self.split_lines('e', text)

    def addHeader(self, text: str | bytes) -> defer.Deferred[None]:
        if not isinstance(text, str):
            text = self.decoder(text)
        return self.split_lines('h', text)

    def add_stdout_lines(self, text: str | bytes) -> defer.Deferred[None]:
        if not isinstance(text, str):
            text = self.decoder(text)
        return self._on_whole_lines('o', text)

    def add_stderr_lines(self, text: str | bytes) -> defer.Deferred[None]:
        if not isinstance(text, str):
            text = self.decoder(text)
        return self._on_whole_lines('e', text)

    def add_header_lines(self, text: str | bytes) -> defer.Deferred[None]:
        if not isinstance(text, str):
            text = self.decoder(text)
        return self._on_whole_lines('h', text)

    def flush(self) -> defer.Deferred[None]:
        for stream, lbf in self.lbfs.items():
            lines = lbf.flush()
            if lines is not None:
                self._on_whole_lines(stream, lines)
        return defer.succeed(None)

    @defer.inlineCallbacks
    def finish(self) -> InlineCallbacksType[None]:
        yield self.flush()
        yield super().finish()


Log._byType['s'] = StreamLog
