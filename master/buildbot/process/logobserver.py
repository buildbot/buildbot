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
from typing import Any

from zope.interface import implementer

from buildbot import interfaces

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Generator

    from buildbot.process.build import Build
    from buildbot.process.log import Log


@implementer(interfaces.ILogObserver)
class LogObserver:
    def setStep(self, step: interfaces.IBuildStep) -> None:
        self.step: Any = step

    def setLog(self, loog: Log) -> None:
        loog.subscribe(self.gotData)

    def gotData(self, stream: str | None, data: str | None) -> None:
        if data is None:
            self.finishReceived()
        elif stream is None or stream == 'o':
            self.outReceived(data)
        elif stream == 'e':
            self.errReceived(data)
        elif stream == 'h':
            self.headerReceived(data)

    def finishReceived(self) -> None:
        pass

    def outReceived(self, data: str) -> None:
        pass

    def errReceived(self, data: str) -> None:
        pass

    def headerReceived(self, data: str) -> None:
        pass

    def logChunk(
        self, build: Build, step: interfaces.IBuildStep, log: Log, channel: str, text: str
    ) -> None:
        pass


class LogLineObserver(LogObserver):
    stdoutDelimiter = "\n"
    stderrDelimiter = "\n"
    headerDelimiter = "\n"

    def __init__(self) -> None:
        super().__init__()
        self.max_length = 16384

    def setMaxLineLength(self, max_length: int) -> None:
        """
        Set the maximum line length: lines longer than max_length are
        dropped.  Default is 16384 bytes.  Use sys.maxint for effective
        infinity.
        """
        self.max_length = max_length

    def _lineReceived(self, data: str, delimiter: str, funcReceived: Callable[[str], None]) -> None:
        for line in data.rstrip().split(delimiter):
            if len(line) > self.max_length:
                continue
            funcReceived(line)

    def outReceived(self, data: str) -> None:
        self._lineReceived(data, self.stdoutDelimiter, self.outLineReceived)

    def errReceived(self, data: str) -> None:
        self._lineReceived(data, self.stderrDelimiter, self.errLineReceived)

    def headerReceived(self, data: str) -> None:
        self._lineReceived(data, self.headerDelimiter, self.headerLineReceived)

    def outLineReceived(self, line: str) -> None:
        """This will be called with complete stdout lines (not including the
        delimiter). Override this in your observer."""

    def errLineReceived(self, line: str) -> None:
        """This will be called with complete lines of stderr (not including
        the delimiter). Override this in your observer."""

    def headerLineReceived(self, line: str) -> None:
        """This will be called with complete lines of stderr (not including
        the delimiter). Override this in your observer."""


class LineConsumerLogObserver(LogLineObserver):
    def __init__(
        self, consumerFunction: Callable[[], Generator[None, tuple[str, str], None]]
    ) -> None:
        super().__init__()
        self.generator: Generator[None, tuple[str, str], None] | None = None
        self.consumerFunction = consumerFunction

    def feed(self, input: tuple[str, str]) -> None:
        # note that we defer starting the generator until the first bit of
        # data, since the observer may be instantiated during configuration as
        # well as for each execution of the step.
        self.generator = self.consumerFunction()
        next(self.generator)
        # shortcut all remaining feed operations
        self.feed = self.generator.send  # type: ignore[assignment]
        self.feed(input)

    def outLineReceived(self, line: str) -> None:
        self.feed(('o', line))

    def errLineReceived(self, line: str) -> None:
        self.feed(('e', line))

    def headerLineReceived(self, line: str) -> None:
        self.feed(('h', line))

    def finishReceived(self) -> None:
        if self.generator:
            self.generator.close()


class OutputProgressObserver(LogObserver):
    length = 0

    def __init__(self, name: str) -> None:
        self.name = name

    def gotData(self, stream: str | None, data: str | None) -> None:
        if data:
            self.length += len(data)
        self.step.setProgress(self.name, self.length)


class BufferLogObserver(LogObserver):
    def __init__(self, wantStdout: bool = True, wantStderr: bool = False) -> None:
        super().__init__()
        self.stdout: list[str] | None = [] if wantStdout else None
        self.stderr: list[str] | None = [] if wantStderr else None

    def outReceived(self, data: str) -> None:
        if self.stdout is not None:
            self.stdout.append(data)

    def errReceived(self, data: str) -> None:
        if self.stderr is not None:
            self.stderr.append(data)

    def _get(self, chunks: list[str] | None) -> str:
        if chunks is None or not chunks:
            return ''
        return ''.join(chunks)

    def getStdout(self) -> str:
        return self._get(self.stdout)

    def getStderr(self) -> str:
        return self._get(self.stderr)
