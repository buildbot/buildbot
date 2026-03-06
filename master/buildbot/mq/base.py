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
from typing import Callable

from twisted.internet import defer
from twisted.python import log

from buildbot.util import deferwaiter
from buildbot.util import service

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class MQBase(service.AsyncService):
    name = 'mq-implementation'

    def __init__(self) -> None:
        super().__init__()
        self._deferwaiter: deferwaiter.DeferWaiter[None] = deferwaiter.DeferWaiter()

    @defer.inlineCallbacks
    def stopService(self) -> InlineCallbacksType[None]:
        yield self._deferwaiter.wait()
        yield super().stopService()

    @defer.inlineCallbacks
    def waitUntilEvent(
        self,
        filter: tuple[str | None, ...],
        check_callback: Callable[[], defer.Deferred[bool]],
    ) -> InlineCallbacksType[tuple[tuple[str, ...], Any] | None]:
        d: defer.Deferred[tuple[tuple[str, ...], Any]] = defer.Deferred()
        buildCompleteConsumer = yield self.startConsuming(
            lambda key, value: d.callback((key, value)), filter
        )
        check = yield check_callback()
        # we only wait if the check callback return true
        if not check:
            res = yield d
        else:
            res = None
        yield buildCompleteConsumer.stopConsuming()
        return res

    def produce(self, routingKey: tuple[str, ...], data: dict[str, Any]) -> None:
        raise NotImplementedError

    def startConsuming(
        self,
        callback: Callable[..., Any],
        filter: tuple[str | None, ...],
        persistent_name: str | None = None,
    ) -> defer.Deferred[QueueRef]:
        raise NotImplementedError

    def invokeQref(self, qref: QueueRef, routingKey: tuple[str, ...], data: dict[str, Any]) -> None:
        self._deferwaiter.add(qref.invoke(routingKey, data))


class QueueRef:
    __slots__ = ['callback']

    def __init__(self, callback: Callable[..., Any] | None) -> None:
        self.callback = callback

    def invoke(self, routing_key: tuple[str, ...], data: dict[str, Any]) -> Any:
        # Potentially returns a Deferred
        if not self.callback:
            return None

        try:
            x = self.callback(routing_key, data)
        except Exception as e:
            log.err(e, f'while invoking {self.callback!r}')
            return None
        if isinstance(x, defer.Deferred):
            x.addErrback(log.err, f'while invoking {self.callback!r}')
        return x

    def stopConsuming(self) -> Any:
        # This method may return a Deferred.
        # subclasses should set self.callback to None in this method.
        raise NotImplementedError
