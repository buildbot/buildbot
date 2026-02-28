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

import time
from typing import TYPE_CHECKING

from twisted.internet import defer

from buildbot.util import asyncSleep

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from twisted.internet.interfaces import IReactorTime

    from buildbot.util.twisted import InlineCallbacksType


class BackoffTimeoutExceededError(Exception):
    pass


class ExponentialBackoffEngine:
    def __init__(self, start_seconds: float, multiplier: float, max_wait_seconds: float) -> None:
        if start_seconds < 0:
            raise ValueError('start_seconds cannot be negative')
        if multiplier < 0:
            raise ValueError('multiplier cannot be negative')
        if max_wait_seconds < 0:
            raise ValueError('max_wait_seconds cannot be negative')

        self.start_seconds = start_seconds
        self.multiplier = multiplier
        self.max_wait_seconds = max_wait_seconds

        self.on_success()

    def on_success(self) -> None:
        self.current_total_wait_seconds = 0.0
        self.current_wait_seconds = self.start_seconds

    def wait_on_failure(self) -> Awaitable[None] | None:
        raise NotImplementedError()

    def calculate_wait_on_failure_seconds(self) -> float:
        if self.current_total_wait_seconds >= self.max_wait_seconds:
            raise BackoffTimeoutExceededError()

        seconds = self.current_wait_seconds
        self.current_wait_seconds *= self.multiplier
        if self.current_total_wait_seconds + seconds < self.max_wait_seconds:
            self.current_total_wait_seconds += seconds
        else:
            seconds = self.max_wait_seconds - self.current_total_wait_seconds
            self.current_total_wait_seconds = self.max_wait_seconds
        return seconds


class ExponentialBackoffEngineSync(ExponentialBackoffEngine):
    def wait_on_failure(self) -> None:
        seconds = self.calculate_wait_on_failure_seconds()
        time.sleep(seconds)


class ExponentialBackoffEngineAsync(ExponentialBackoffEngine):
    def __init__(
        self,
        reactor: IReactorTime,
        start_seconds: float,
        multiplier: float,
        max_wait_seconds: float,
    ) -> None:
        super().__init__(
            start_seconds=start_seconds, multiplier=multiplier, max_wait_seconds=max_wait_seconds
        )
        self.reactor = reactor

    @defer.inlineCallbacks
    def wait_on_failure(self) -> InlineCallbacksType[None]:
        seconds = self.calculate_wait_on_failure_seconds()
        yield asyncSleep(seconds, reactor=self.reactor)
